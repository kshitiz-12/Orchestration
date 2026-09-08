from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.audit.service import AuditService
from app.core.enums import AuditAction
from app.engine.pipeline import ProcessingPipeline
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import AIDecision, Conversation, HumanReviewItem, RawEmailEvent
from app.models.org import utcnow
from app.schemas.ai import ExtractionResult
from app.schemas.api import HumanReviewDecision
from app.services.communication import CommunicationService
from app.services.context import ContextRetrievalService

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
    decision = session.get(AIDecision, item.ai_decision_id) if item.ai_decision_id else None
    event = session.get(RawEmailEvent, item.event_id)
    conversation = session.get(Conversation, item.conversation_id) if item.conversation_id else None

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
        item.status = "CORRECTED"
    elif payload.action == "ACCEPT":
        item.status = "ACCEPTED"
    elif payload.action == "CLARIFY" and conversation:
        questions = [payload.reason or "Please provide additional details."]
        CommunicationService(session, tenant_id).send_clarification(
            conversation=conversation,
            questions=questions,
        )
        item.status = "CLARIFICATION"
    elif payload.action == "REJECT":
        item.status = "REJECTED"
    else:
        raise HTTPException(400, "Unsupported action")

    item.resolution = payload.model_dump()
    item.resolved_at = utcnow()
    item.assigned_to = payload.assign_to or user.person_id
    item.reason = payload.reason or item.reason
    session.add(item)
    session.commit()
    return item
