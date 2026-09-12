from typing import Optional

from sqlmodel import Session, select

from app.ai.service import LLMService
from app.audit.service import AuditService
from app.core.config import get_settings
from app.core.enums import (
    AuditAction,
    ConfidenceRoute,
    ConversationStatus,
    JobStatus,
    ProcessingStage,
)
from app.core.logging import get_logger
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import AIDecision, Conversation, HumanReviewItem, ProcessingJob, RawEmailEvent
from app.models.org import utcnow
from app.connectors.factory import get_email_provider
from app.services.communication import CommunicationService
from app.services.context import ContextRetrievalService
from app.services.intake import JobQueueService

logger = get_logger(__name__)


class ProcessingPipeline:
    """
    Email → Intake(already done) → AI → Validate → Context → Rules → Outcome Engine
    → Controlled execution → Human approval where required → Evidence → Communication → Audit
    """

    def __init__(self, session: Session, tenant_id: str, llm: Optional[LLMService] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.llm = llm or LLMService()
        self.audit = AuditService(session)
        self.context = ContextRetrievalService(session, tenant_id)
        email = get_email_provider(session, tenant_id)
        # Only attach live sender when connected — otherwise persist-only
        sender = email if email.is_connected() else None
        self.comms = CommunicationService(session, tenant_id, email_sender=sender)
        self.scenarios = ScenarioOrchestrator(session, tenant_id, self.comms)
        self.settings = get_settings()

    def process_event(self, event_id: str) -> dict:
        event = self.session.get(RawEmailEvent, event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")

        event.processing_stage = ProcessingStage.AI_INTERPRETATION.value
        self.session.add(event)
        self.session.commit()

        conversation = self._get_or_create_conversation(event)
        event.conversation_id = conversation.conversation_id
        self.session.add(event)

        # Light context for first-pass extraction (requester only)
        preliminary_ctx = self.context.for_extraction(None, event.sender, conversation.facts or {})

        extraction = self.llm.extract(
            subject=event.subject,
            body=event.body_for_ai or event.body_text,
            attachment_summaries=[
                a.get("filename", "") for a in (event.attachments or []) if a.get("validation", {}).get("allowed", True)
            ],
            prior_facts=conversation.facts or {},
            allowed_context=preliminary_ctx,
        )

        # Second-pass: relevant context based on detected event type
        relevant_ctx = self.context.for_extraction(
            extraction.event_type, event.sender, extraction.entities
        )
        if relevant_ctx != preliminary_ctx:
            extraction = self.llm.extract(
                subject=event.subject,
                body=event.body_for_ai or event.body_text,
                attachment_summaries=[
                    a.get("filename", "")
                    for a in (event.attachments or [])
                    if a.get("validation", {}).get("allowed", True)
                ],
                prior_facts=conversation.facts or {},
                allowed_context=relevant_ctx,
            )

        routing = self.llm.route(extraction)
        decision = AIDecision(
            tenant_id=self.tenant_id,
            event_id=event.event_id,
            conversation_id=conversation.conversation_id,
            model=getattr(self.llm.provider, "model", type(self.llm.provider).__name__),
            model_version=str(getattr(self.llm.provider, "model", "heuristic")),
            prompt_version=self.settings.ai_prompt_version,
            confidence=extraction.confidence,
            output=extraction.model_dump(),
            recommendation=extraction.recommended_next_action,
            rationale=extraction.reason,
            route=routing.route,
        )
        self.session.add(decision)
        self.session.flush()

        self.audit.record(
            tenant_id=self.tenant_id,
            actor="ai",
            action=AuditAction.AI_EXTRACTION_COMPLETED,
            entity_type="AIDecision",
            entity_id=decision.decision_id,
            after={
                "event_type": extraction.event_type,
                "confidence": extraction.confidence,
                "route": routing.route,
            },
            correlation_id=event.processing_id,
        )

        # Merge facts into conversation (reply path — same outcome)
        conversation.facts = {**(conversation.facts or {}), **extraction.entities}
        conversation.missing_information = [m.model_dump() for m in extraction.missing_information]
        if extraction.missing_information and any(m.blocking for m in extraction.missing_information):
            conversation.status = ConversationStatus.AWAITING_INFORMATION.value
        self.session.add(conversation)

        if event.safety_flags.get("bank_change_mentioned"):
            extraction.financial_action = True
            extraction.human_review_required = True
            routing = self.llm.route(extraction)
            decision.route = routing.route
            decision.output = extraction.model_dump()
            self.session.add(decision)

        if routing.route in {ConfidenceRoute.HUMAN_REQUIRED.value, ConfidenceRoute.OPERATOR_REVIEW.value}:
            self._enqueue_human_review(event, conversation, decision, routing.reasons)
            # Still create/update outcome for visibility, but flagged
            outcome = self.scenarios.orchestrate(
                extraction=extraction,
                requester_email=event.sender,
                conversation_id=conversation.conversation_id,
                business_event_id=event.event_id,
                context=relevant_ctx,
            )
            event.processing_stage = ProcessingStage.HUMAN_REVIEW.value
            self.session.add(event)
            self.session.commit()
            return {
                "status": "human_review",
                "outcome_id": outcome.outcome_id,
                "decision_id": decision.decision_id,
                "route": routing.route,
            }

        if routing.route == ConfidenceRoute.CLARIFICATION.value or (
            extraction.missing_information and any(m.blocking for m in extraction.missing_information)
        ):
            # Create/update draft outcome then clarify — never duplicate on reply
            outcome = self.scenarios.orchestrate(
                extraction=extraction,
                requester_email=event.sender,
                conversation_id=conversation.conversation_id,
                business_event_id=event.event_id,
                context=relevant_ctx,
            )
            questions = [
                q
                for q in (
                    extraction.clarification_questions
                    or [m.question for m in extraction.missing_information]
                )
                if q
            ]
            if not questions:
                questions = [
                    "How many people will attend?",
                    "What date and preferred start time?",
                    "How long do you need the room (duration)?",
                ]
            self.comms.send_clarification(
                conversation=conversation,
                questions=questions,
                case_reference=outcome.case_reference,
            )
            self.audit.record(
                tenant_id=self.tenant_id,
                actor="system",
                action=AuditAction.CLARIFICATION_SENT,
                entity_type="Conversation",
                entity_id=conversation.conversation_id,
                after={"questions": questions},
                correlation_id=event.processing_id,
            )
            event.processing_stage = ProcessingStage.COMMUNICATION.value
            self.session.add(event)
            self.session.commit()
            return {
                "status": "clarification_sent",
                "outcome_id": outcome.outcome_id,
                "decision_id": decision.decision_id,
            }

        # AUTO path
        outcome = self.scenarios.orchestrate(
            extraction=extraction,
            requester_email=event.sender,
            conversation_id=conversation.conversation_id,
            business_event_id=event.event_id,
            context=relevant_ctx,
        )
        if conversation.facts and (event.provider_conversation_id or event.gmail_thread_id):
            self.audit.record(
                tenant_id=self.tenant_id,
                actor="system",
                action=AuditAction.INFORMATION_MERGED,
                entity_type="Conversation",
                entity_id=conversation.conversation_id,
                after={"facts": conversation.facts},
                correlation_id=event.processing_id,
            )

        event.processing_stage = ProcessingStage.COMPLETED.value
        self.session.add(event)
        self.session.commit()
        return {
            "status": "orchestrated",
            "outcome_id": outcome.outcome_id,
            "case_reference": outcome.case_reference,
            "decision_id": decision.decision_id,
        }

    def _get_or_create_conversation(self, event: RawEmailEvent) -> Conversation:
        import re

        thread_id = (
            event.provider_conversation_id
            or event.gmail_thread_id
            or event.provider_message_id
            or event.gmail_message_id
        )
        existing = self.session.exec(
            select(Conversation).where(
                Conversation.tenant_id == self.tenant_id,
                Conversation.thread_id == thread_id,
            )
        ).first()
        if existing:
            return existing

        # Fallback: subject contains [EVT-2026-0006] from clarification replies
        subject = event.subject or ""
        m = re.search(r"\[(EVT-\d{4}-\d+)\]", subject, re.I)
        if m:
            from app.models.outcome import Outcome

            case_ref = m.group(1).upper()
            outcome = self.session.exec(
                select(Outcome).where(
                    Outcome.tenant_id == self.tenant_id,
                    Outcome.case_reference == case_ref,
                )
            ).first()
            if outcome and outcome.conversation_id:
                linked = self.session.get(Conversation, outcome.conversation_id)
                if linked:
                    logger.info(
                        "conversation_linked_by_case_reference",
                        case_reference=case_ref,
                        conversation_id=linked.conversation_id,
                    )
                    return linked

        from app.models.org import Person

        person = self.session.exec(
            select(Person).where(Person.email == event.sender.lower())
        ).first()
        conv = Conversation(
            tenant_id=self.tenant_id,
            thread_id=thread_id,
            requester_email=event.sender.lower(),
            requester_person_id=person.person_id if person else None,
            subject=event.subject,
            status=ConversationStatus.OPEN.value,
        )
        self.session.add(conv)
        self.session.flush()
        return conv

    def _enqueue_human_review(self, event, conversation, decision, reasons) -> HumanReviewItem:
        item = HumanReviewItem(
            tenant_id=self.tenant_id,
            event_id=event.event_id,
            conversation_id=conversation.conversation_id,
            ai_decision_id=decision.decision_id,
            status="PENDING",
            reason="; ".join(reasons) if reasons else decision.rationale,
        )
        self.session.add(item)
        self.audit.record(
            tenant_id=self.tenant_id,
            actor="system",
            action=AuditAction.AI_REVIEW_REQUIRED,
            entity_type="HumanReviewItem",
            entity_id=item.review_id if item.review_id else event.event_id,
            after={"reasons": reasons},
            correlation_id=event.processing_id,
        )
        self.session.flush()
        return item


def process_claimed_job(session: Session, job: ProcessingJob, tenant_id: str) -> None:
    queue = JobQueueService(session)
    settings = get_settings()
    try:
        if job.job_type == "PROCESS_EMAIL":
            event_id = job.payload.get("event_id") or job.event_id
            pipeline = ProcessingPipeline(session, tenant_id)
            result = pipeline.process_event(event_id)
            job.payload = {**(job.payload or {}), "result": result}
            queue.succeed(job)
        else:
            queue.succeed(job)
    except Exception as exc:  # noqa: BLE001
        logger.exception("job_failed", job_id=job.job_id, error=str(exc))
        AuditService(session).record(
            tenant_id=tenant_id,
            actor="system",
            action=AuditAction.AUTOMATION_FAILED,
            entity_type="ProcessingJob",
            entity_id=job.job_id,
            after={"error": str(exc)},
        )
        session.commit()
        queue.fail(
            job,
            str(exc),
            max_attempts=settings.worker_max_retries,
            base_delay=settings.worker_retry_base_seconds,
        )
