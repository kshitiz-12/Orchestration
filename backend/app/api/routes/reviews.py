from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.audit.service import AuditService
from app.connectors.factory import get_email_provider
from app.core.enums import AuditAction, ConversationStatus, ProcessingStage, TaskStatus
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import AIDecision, Conversation, HumanReviewItem, RawEmailEvent
from app.models.org import utcnow
from app.models.outcome import Outcome, Task
from app.schemas.ai import ExtractionResult, MissingInformation
from app.schemas.api import HumanReviewDecision
from app.services.communication import CommunicationService
from app.services.context import ContextRetrievalService
from app.services.thread_facts import meeting_room_gaps, merge_thread_prior_facts

router = APIRouter(prefix="/reviews", tags=["human-review"])


@router.get("")
def list_reviews(session: SessionDep, tenant_id: TenantDep, _user: UserDep, status: str = "PENDING"):
    rows = session.exec(
        select(HumanReviewItem)
        .where(HumanReviewItem.tenant_id == tenant_id, HumanReviewItem.status == status)
        .order_by(HumanReviewItem.created_at.desc())  # type: ignore
    ).all()
    enriched = []
    for r in rows:
        event = session.get(RawEmailEvent, r.event_id)
        decision = session.get(AIDecision, r.ai_decision_id) if r.ai_decision_id else None
        enriched.append({"review": r, "email": event, "ai_decision": decision})
    return enriched


def _continue_after_accept(
    *,
    session,
    tenant_id: str,
    user,
    item: HumanReviewItem,
    decision: AIDecision | None,
    event: RawEmailEvent | None,
    conversation: Conversation | None,
) -> dict:
    """Accept = approve AI output, merge thread facts, continue orchestration."""
    if not conversation or not event:
        return {"continued": False, "reason": "missing_conversation_or_event"}

    prior = merge_thread_prior_facts(
        session,
        tenant_id=tenant_id,
        conversation=conversation,
        exclude_event_id=None,
    )
    prior = {**(conversation.facts or {}), **prior}

    base = dict(decision.output or {}) if decision else {}
    entities = {**prior, **(base.get("entities") or {})}
    event_type = base.get("event_type") or "GENERAL"
    if event_type in {"UNKNOWN", "GENERAL"} and (
        "attendees" in entities or "preferred_time" in entities or "meeting" in (event.subject or "").lower()
    ):
        event_type = "MEETING_ROOM"

    missing_raw: list[dict] = []
    if event_type == "MEETING_ROOM":
        missing_raw = meeting_room_gaps(entities)
    else:
        missing_raw = list(base.get("missing_information") or [])

    extraction = ExtractionResult(
        event_type=event_type,
        category=event_type,
        summary=base.get("summary") or event.subject or event_type,
        entities=entities,
        issues=[],
        missing_information=[MissingInformation(**m) if isinstance(m, dict) else m for m in missing_raw],
        safety_concern=False,
        financial_action=False,
        access_control_action=False,
        vendor_sanction=False,
        recommended_priority=base.get("recommended_priority") or "MEDIUM",
        recommended_next_action="route_to_outcome_engine" if not missing_raw else "clarification",
        confidence=max(float(base.get("confidence") or 0.7), 0.9 if not missing_raw else 0.75),
        human_review_required=False,
        reason="Accepted by human reviewer; thread facts merged",
        is_reply=True,
        clarification_questions=[m["question"] if isinstance(m, dict) else m.question for m in missing_raw],
    )

    if decision:
        decision.human_corrected = True
        decision.corrected_by = user.person_id
        decision.output = extraction.model_dump()
        decision.confidence = extraction.confidence
        decision.route = "AUTO" if not missing_raw else "CLARIFICATION"
        decision.rationale = extraction.reason
        session.add(decision)

    conversation.facts = entities
    conversation.missing_information = [m.model_dump() for m in extraction.missing_information]
    conversation.status = (
        ConversationStatus.AWAITING_INFORMATION.value
        if missing_raw
        else ConversationStatus.ACTIVE.value
    )
    session.add(conversation)

    ctx = ContextRetrievalService(session, tenant_id).for_extraction(
        extraction.event_type, event.sender, extraction.entities
    )
    email = get_email_provider(session, tenant_id)
    sender = email if email.is_connected() else None
    orchestrator = ScenarioOrchestrator(
        session, tenant_id, CommunicationService(session, tenant_id, email_sender=sender)
    )
    outcome = orchestrator.orchestrate(
        extraction=extraction,
        requester_email=event.sender,
        conversation_id=conversation.conversation_id,
        business_event_id=event.event_id,
        context=ctx,
    )

    if missing_raw:
        CommunicationService(session, tenant_id, email_sender=sender).send_clarification(
            conversation=conversation,
            questions=extraction.clarification_questions,
            case_reference=outcome.case_reference,
        )
        event.processing_stage = ProcessingStage.COMMUNICATION.value
        continued_status = "clarification_sent"
    else:
        # Advance triage / reserve tasks to accepted for operator follow-through
        tasks = session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
        for task in tasks:
            if task.status == TaskStatus.ASSIGNED.value:
                task.status = TaskStatus.ACCEPTED.value
                session.add(task)
        event.processing_stage = ProcessingStage.COMPLETED.value
        continued_status = "orchestrated"

    session.add(event)
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=AuditAction.HUMAN_OVERRIDE,
        entity_type="HumanReviewItem",
        entity_id=item.review_id,
        after={
            "action": "ACCEPT",
            "continued": continued_status,
            "outcome_id": outcome.outcome_id,
            "entities": entities,
        },
        correlation_id=event.event_id,
    )
    return {
        "continued": True,
        "status": continued_status,
        "outcome_id": outcome.outcome_id,
        "case_reference": outcome.case_reference,
        "entities": entities,
        "missing": missing_raw,
    }


@router.post("/{review_id}/decide")
def decide_review(
    review_id: str,
    payload: HumanReviewDecision,
    session: SessionDep,
    tenant_id: TenantDep,
    user: UserDep,
):
    item = session.get(HumanReviewItem, review_id)
    if not item or item.tenant_id != tenant_id:
        raise HTTPException(404, "Review not found")
    if item.status != "PENDING":
        raise HTTPException(400, f"Review already {item.status}")

    decision = session.get(AIDecision, item.ai_decision_id) if item.ai_decision_id else None
    event = session.get(RawEmailEvent, item.event_id)
    conversation = session.get(Conversation, item.conversation_id) if item.conversation_id else None
    continue_result = None

    if payload.action == "CORRECT" and decision and payload.corrected_extraction:
        decision.human_corrected = True
        decision.correction = payload.corrected_extraction
        decision.corrected_by = user.person_id
        decision.output = {**(decision.output or {}), **payload.corrected_extraction}
        session.add(decision)
        AuditService(session).record(
            tenant_id=tenant_id,
            actor=user.email,
            action=AuditAction.HUMAN_OVERRIDE,
            entity_type="AIDecision",
            entity_id=decision.decision_id,
            after=payload.corrected_extraction,
            correlation_id=item.event_id,
        )
        extraction = ExtractionResult.model_validate(decision.output)
        ctx = ContextRetrievalService(session, tenant_id).for_extraction(
            extraction.event_type, event.sender if event else "", extraction.entities
        )
        ScenarioOrchestrator(session, tenant_id).orchestrate(
            extraction=extraction,
            requester_email=event.sender if event else conversation.requester_email,
            conversation_id=conversation.conversation_id if conversation else None,
            business_event_id=event.event_id if event else "",
            context=ctx,
        )
        if event:
            event.processing_stage = ProcessingStage.COMPLETED.value
            session.add(event)
        item.status = "CORRECTED"
    elif payload.action == "ACCEPT":
        continue_result = _continue_after_accept(
            session=session,
            tenant_id=tenant_id,
            user=user,
            item=item,
            decision=decision,
            event=event,
            conversation=conversation,
        )
        item.status = "ACCEPTED"
    elif payload.action == "CLARIFY" and conversation:
        questions = [payload.reason or "Please provide additional details."]
        email = get_email_provider(session, tenant_id)
        sender = email if email.is_connected() else None
        outcome = session.exec(
            select(Outcome).where(Outcome.conversation_id == conversation.conversation_id)
        ).first()
        CommunicationService(session, tenant_id, email_sender=sender).send_clarification(
            conversation=conversation,
            questions=questions,
            case_reference=outcome.case_reference if outcome else None,
        )
        item.status = "CLARIFICATION"
    elif payload.action == "REJECT":
        item.status = "REJECTED"
        if event:
            event.processing_stage = ProcessingStage.FAILED.value
            session.add(event)
    else:
        raise HTTPException(400, "Unsupported action")

    item.resolution = {**(payload.model_dump()), **({"continue": continue_result} if continue_result else {})}
    item.resolved_at = utcnow()
    item.assigned_to = payload.assign_to or user.person_id
    item.reason = payload.reason or item.reason
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
