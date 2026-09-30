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
from app.schemas.ai import ExtractionResult, MissingInformation
from app.services.communication import CommunicationService, resolve_requester_name
from app.services.admin_commands import (
    AdminCommandHandler,
    case_reference_from_subject,
    is_admin_sender,
    sender_address,
    verify_ops_sender,
)
from app.services.admin_ops import AdminOpsNotifier, admin_ops_email
from app.services.context import ContextRetrievalService
from app.services.intake import JobQueueService
from app.services.meeting_room import (
    default_meeting_room_questions,
    meeting_room_gaps,
    requirement_email_sections,
)
from app.services.thread_facts import merge_thread_prior_facts

logger = get_logger(__name__)

_PROCESSED_STAGES = {
    ProcessingStage.COMPLETED.value,
    ProcessingStage.COMMUNICATION.value,
    ProcessingStage.HUMAN_REVIEW.value,
}


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

    def process_event(self, event_id: str, *, force: bool = False) -> dict:
        event = self.session.get(RawEmailEvent, event_id)
        if not event:
            raise ValueError(f"Event not found: {event_id}")

        if not force and event.processing_stage in _PROCESSED_STAGES:
            outcome_id = None
            if event.conversation_id:
                from app.models.outcome import Outcome

                existing = self.session.exec(
                    select(Outcome).where(Outcome.conversation_id == event.conversation_id)
                ).first()
                outcome_id = existing.outcome_id if existing else None
            return {
                "status": "already_processed",
                "stage": event.processing_stage,
                "event_id": event.event_id,
                "outcome_id": outcome_id,
            }

        admin_result = self._maybe_handle_admin_reply(event)
        if admin_result is not None:
            return admin_result

        event.processing_stage = ProcessingStage.AI_INTERPRETATION.value
        self.session.add(event)
        self.session.commit()

        conversation = self._get_or_create_conversation(event)
        event.conversation_id = conversation.conversation_id
        self.session.add(event)

        self._handoff_categories: set[str] = set()
        if self.settings.agent_mode:
            from app.agent.desk import AdminDesk

            desk = AdminDesk(self.session, self.tenant_id, self.comms, self.llm.provider)
            desk_result = desk.handle(event, conversation)
            self._handoff_categories = desk.handoff_categories
            if desk_result is not None:
                event.processing_stage = ProcessingStage.COMPLETED.value
                self.session.add(event)
                self.session.commit()
                return {"event_id": event.event_id, **desk_result}

        prior_facts = merge_thread_prior_facts(
            self.session,
            tenant_id=self.tenant_id,
            conversation=conversation,
            exclude_event_id=event.event_id,
        )
        # Keep stored conversation + outcome facts (pending confirmation, checklist, etc.)
        prior_facts = {**(conversation.facts or {}), **prior_facts}
        if conversation.current_outcome_id:
            from app.models.outcome import Outcome

            current = self.session.get(Outcome, conversation.current_outcome_id)
            if current and current.facts:
                prior_facts = {**(current.facts or {}), **prior_facts}

        # Light context for first-pass extraction (requester only)
        preliminary_ctx = self.context.for_extraction(None, event.sender, prior_facts)

        extraction = self.llm.extract(
            subject=event.subject,
            body=event.body_text or event.body_for_ai,
            attachment_summaries=[
                a.get("filename", "") for a in (event.attachments or []) if a.get("validation", {}).get("allowed", True)
            ],
            prior_facts=prior_facts,
            allowed_context=preliminary_ctx,
        )
        extraction = self._enrich_with_thread_facts(extraction, prior_facts, event)

        # Second-pass: relevant context based on detected event type
        relevant_ctx = self.context.for_extraction(
            extraction.event_type, event.sender, extraction.entities
        )
        if relevant_ctx != preliminary_ctx:
            extraction = self.llm.extract(
                subject=event.subject,
                body=event.body_text or event.body_for_ai,
                attachment_summaries=[
                    a.get("filename", "")
                    for a in (event.attachments or [])
                    if a.get("validation", {}).get("allowed", True)
                ],
                prior_facts=prior_facts,
                allowed_context=relevant_ctx,
            )
            extraction = self._enrich_with_thread_facts(extraction, prior_facts, event)

        routing = self.llm.route(extraction)
        interp_path = (extraction.entities or {}).get("interpretation_path")
        endpoint = (extraction.entities or {}).get("interpretation_endpoint") or {}
        model_label = (
            interp_path
            or (endpoint.get("label") if isinstance(endpoint, dict) else None)
            or getattr(self.llm.provider, "model", type(self.llm.provider).__name__)
        )
        decision = AIDecision(
            tenant_id=self.tenant_id,
            event_id=event.event_id,
            conversation_id=conversation.conversation_id,
            model=str(model_label),
            model_version=str(
                (endpoint.get("model") if isinstance(endpoint, dict) else None)
                or getattr(self.llm.provider, "model", "heuristic")
            ),
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
        conversation.facts = {**prior_facts, **(extraction.entities or {})}
        missing_list = [m.model_dump() for m in extraction.missing_information]
        conversation.missing_information = missing_list
        if missing_list and any(m.get("blocking", True) for m in missing_list):
            conversation.status = ConversationStatus.AWAITING_INFORMATION.value
        elif conversation.status == ConversationStatus.AWAITING_INFORMATION.value:
            conversation.status = ConversationStatus.ACTIVE.value
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
            if (outcome.facts or {}).get("orchestration_stage") == "CANCELLED":
                event.processing_stage = ProcessingStage.COMPLETED.value
                self.session.add(event)
                self.session.commit()
                return {"status": "cancelled", "outcome_id": outcome.outcome_id, "decision_id": decision.decision_id}
            questions = [
                q
                for q in (
                    extraction.clarification_questions
                    or [m.question for m in extraction.missing_information]
                )
                if q
            ]
            facts_for_q = {**(outcome.facts or {}), **(extraction.entities or {})}
            prior_clarify = bool((outcome.facts or {}).get("clarification_sent"))
            is_first_contact = not prior_clarify
            # Always ask ONLY what is still blocking — never re-ask answered facts.
            gap_questions = [g["question"] for g in meeting_room_gaps(facts_for_q) if g.get("question")]
            if gap_questions:
                questions = gap_questions
            elif not questions:
                questions = default_meeting_room_questions(facts_for_q)

            understood, unconfirmed = requirement_email_sections(facts_for_q)
            name = resolve_requester_name(
                self.session,
                outcome=outcome,
                conversation=conversation,
                email=event.sender,
                event=event,
            )
            self.comms.send_clarification(
                conversation=conversation,
                questions=questions,
                case_reference=outcome.case_reference,
                understood=understood or None,
                unconfirmed=unconfirmed or None,
                force_send_key=event.event_id,
                first_contact=is_first_contact,
                greeting_name=name,
            )
            facts = dict(outcome.facts or {})
            facts["clarification_sent"] = True
            if name and name.lower() not in {"there", "team"}:
                facts["requester_display_name"] = name
            path = (extraction.entities or {}).get("interpretation_path")
            if path:
                facts["interpretation_path"] = path
            outcome.facts = facts
            self.session.add(outcome)
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(outcome, "facts")
            if is_first_contact:
                AdminOpsNotifier(self.session, self.tenant_id, self.comms).fyi_awaiting_requirements(
                    outcome, facts=facts
                )
            self.audit.record(
                tenant_id=self.tenant_id,
                actor="system",
                action=AuditAction.CLARIFICATION_SENT,
                entity_type="Conversation",
                entity_id=conversation.conversation_id,
                after={"questions": questions, "first_contact": is_first_contact},
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
        facts = dict(outcome.facts or {})
        stage = (facts.get("orchestration_stage") or "").upper()
        if stage == "CANCELLED":
            event.processing_stage = ProcessingStage.COMPLETED.value
            self.session.add(event)
            self.session.commit()
            return {"status": "cancelled", "outcome_id": outcome.outcome_id, "decision_id": decision.decision_id}
        blocking = meeting_room_gaps(facts) if (outcome.category or "").upper() == "MEETING_ROOM" else []
        # Never mark COMPLETE while requirements are blocking or inventory failed
        if stage == "AWAITING_REQUIREMENTS" or blocking:
            prior_clarify = bool(facts.get("clarification_sent"))
            is_first_contact = not prior_clarify
            questions = [g["question"] for g in blocking if g.get("question")]
            if not questions:
                questions = default_meeting_room_questions(facts)
            understood, unconfirmed = requirement_email_sections(facts)
            name = resolve_requester_name(
                self.session,
                outcome=outcome,
                conversation=conversation,
                email=event.sender,
                event=event,
            )
            self.comms.send_clarification(
                conversation=conversation,
                questions=questions,
                case_reference=outcome.case_reference,
                understood=understood or None,
                unconfirmed=unconfirmed or None,
                force_send_key=event.event_id,
                first_contact=is_first_contact,
                greeting_name=name,
            )
            facts["clarification_sent"] = True
            if name and name.lower() not in {"there", "team"}:
                facts["requester_display_name"] = name
            path = (extraction.entities or {}).get("interpretation_path")
            if path:
                facts["interpretation_path"] = path
            outcome.facts = facts
            self.session.add(outcome)
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(outcome, "facts")
            if is_first_contact:
                AdminOpsNotifier(self.session, self.tenant_id, self.comms).fyi_awaiting_requirements(
                    outcome, facts=facts
                )
            event.processing_stage = ProcessingStage.COMMUNICATION.value
            self.session.add(event)
            self.session.commit()
            return {
                "status": "clarification_sent",
                "outcome_id": outcome.outcome_id,
                "decision_id": decision.decision_id,
            }
        if stage == "NO_RESOURCE":
            event.processing_stage = ProcessingStage.COMMUNICATION.value
            self.session.add(event)
            self.session.commit()
            return {
                "status": "no_resource",
                "outcome_id": outcome.outcome_id,
                "decision_id": decision.decision_id,
            }

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

        # Persist AI path + greeting name on successful orchestration
        facts = dict(outcome.facts or {})
        path = (extraction.entities or {}).get("interpretation_path")
        if path:
            facts["interpretation_path"] = path
        name = resolve_requester_name(
            self.session,
            outcome=outcome,
            conversation=conversation,
            email=event.sender,
            event=event,
        )
        if name and name.lower() != "there":
            facts["requester_display_name"] = name
        if facts != (outcome.facts or {}):
            outcome.facts = facts
            self.session.add(outcome)
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(outcome, "facts")

        event.processing_stage = ProcessingStage.COMPLETED.value
        self.session.add(event)
        self.session.commit()
        return {
            "status": "orchestrated",
            "outcome_id": outcome.outcome_id,
            "case_reference": outcome.case_reference,
            "decision_id": decision.decision_id,
        }

    def _maybe_handle_admin_reply(self, event: RawEmailEvent) -> Optional[dict]:
        """Ops mailbox and department replies are commands on an existing case, not requester mail."""
        from app.agent.directory import department_emails
        from app.services.site_services import cost_centre_approver_emails

        addr = sender_address(event.sender)
        if (
            not is_admin_sender(event.sender)
            and addr not in department_emails(self.session, self.tenant_id)
            and addr not in cost_centre_approver_emails(self.session, self.tenant_id)
        ):
            return None
        from app.models.outcome import Outcome

        outcome = None
        case_ref = case_reference_from_subject(event.subject)
        if case_ref:
            outcome = self.session.exec(
                select(Outcome).where(
                    Outcome.tenant_id == self.tenant_id,
                    Outcome.case_reference == case_ref,
                )
            ).first()
        if outcome is None:
            thread_id = event.provider_conversation_id or event.gmail_thread_id
            if thread_id:
                conv = self.session.exec(
                    select(Conversation).where(
                        Conversation.tenant_id == self.tenant_id,
                        Conversation.thread_id == thread_id,
                    )
                ).first()
                if conv and conv.current_outcome_id:
                    outcome = self.session.get(Outcome, conv.current_outcome_id)
        sender = sender_address(event.sender)
        # No case, or the ops person filed their own request: treat as a normal requester mail
        if outcome is None or (outcome.requester_email or "").strip().lower() == sender:
            return None

        event.conversation_id = outcome.conversation_id
        verified, how = verify_ops_sender(self.session, self.tenant_id, event.headers, sender)
        if not verified:
            return self._reject_unverified_ops_mail(event, outcome, sender)

        from app.agent.desk import AdminDesk, is_service_case

        if is_service_case(outcome):
            from app.services.admin_commands import admin_reply_text

            result = AdminDesk(self.session, self.tenant_id, self.comms).apply_team_reply(
                outcome, admin_reply_text(event.body_text or event.body_for_ai or ""), sender
            )
            if not result.get("applied"):
                self._ops_not_understood(outcome, sender)
        else:
            result = AdminCommandHandler(self.session, self.tenant_id, self.comms).handle(
                outcome=outcome,
                body=event.body_text or event.body_for_ai or "",
                event_id=event.event_id,
                admin_email=sender,
            )
        result["sender_verification"] = how
        event.processing_stage = ProcessingStage.COMPLETED.value
        self.session.add(event)
        self.session.commit()
        return {
            "status": "admin_command",
            "outcome_id": outcome.outcome_id,
            "case_reference": outcome.case_reference,
            **result,
        }

    def _ops_not_understood(self, outcome, sender: str) -> None:
        self.comms.send_case_update(
            outcome=outcome,
            communication_type="INFORMATION_ONLY",
            body=(
                f"I couldn't tell what to do with your reply on {outcome.case_reference}.\n\n"
                'You can reply with: "approve", "reject, <reason>", "done <note>", "assign to <email>", '
                '"tell requester: <message>" or "cancel".\n'
            ),
            recipients=[sender],
            action_label="OPS NOT APPLIED",
            subject_hint="Reply not understood",
            suppress_fingerprint=f"not-understood:{outcome.updated_at}",
        )

    def _reject_unverified_ops_mail(self, event: RawEmailEvent, outcome, sender: str) -> dict:
        """Looks like ops but can't be authenticated: change nothing, tell the real ops mailbox."""
        from app.core.enums import AuditAction

        self.audit.record(
            tenant_id=self.tenant_id,
            actor=f"unverified:{sender}",
            action=AuditAction.HUMAN_OVERRIDE,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"rejected": "ops_sender_unverified", "event_id": event.event_id, "subject": event.subject},
            correlation_id=outcome.outcome_id,
        )
        admin = admin_ops_email()
        if admin:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="INFORMATION_ONLY",
                body=(
                    f"A reply claiming to be from {sender} on this case could not be verified "
                    "(no SPF/DKIM pass for that domain and it wasn't a reply to our mail), so nothing was changed.\n\n"
                    "If it was you, reply directly to the case briefing mail instead.\n\n"
                    f"Subject: {event.subject}\nCase: {outcome.case_reference}"
                ),
                recipients=[admin],
                action_label="OPS NOT APPLIED",
                subject_hint="Unverified ops reply",
                suppress_fingerprint=f"unverified:{event.event_id}",
            )
        event.processing_stage = ProcessingStage.COMPLETED.value
        self.session.add(event)
        self.session.commit()
        logger.warning("ops_sender_unverified", case=outcome.case_reference, sender=sender)
        return {
            "status": "admin_unverified",
            "outcome_id": outcome.outcome_id,
            "case_reference": outcome.case_reference,
            "applied": False,
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

        # Fallback: subject contains [EVT-2026-0006] / [ROOM-2026-0001] from clarification replies
        subject = event.subject or ""
        m = re.search(r"\[([A-Z]{2,5}-\d{4}-\d+)\]", subject, re.I)
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

    def _enrich_with_thread_facts(
        self,
        extraction: ExtractionResult,
        prior_facts: dict,
        event: RawEmailEvent,
    ) -> ExtractionResult:
        """Merge prior thread facts and recompute meeting-room gaps for short replies."""
        subject = event.subject or ""
        body = event.body_text or event.body_for_ai or ""
        merged = {**(prior_facts or {}), **(extraction.entities or {})}

        if self.settings.agent_mode:
            looks_meeting = self._is_meeting_thread(extraction, merged, event)
        else:
            looks_meeting = (
                extraction.event_type == "MEETING_ROOM"
                or "information required" in subject.lower()
                or "meeting" in subject.lower()
                or "room" in (subject + body).lower()
                or any(k in merged for k in ("attendees", "preferred_time", "duration_hours"))
            )
        if looks_meeting:
            # LLMService already reduced; re-derive gaps from snapshot without heuristic overwrite
            snapshot = dict(extraction.entities or merged)
            gaps = meeting_room_gaps(snapshot)
            if snapshot.get("booked_room") or (
                snapshot.get("pending_confirmation") and snapshot.get("proposed_room")
            ):
                gaps = []
            extraction.event_type = "MEETING_ROOM"
            extraction.category = "MEETING_ROOM"
            extraction.entities = snapshot
            extraction.missing_information = [MissingInformation(**g) for g in gaps]
            extraction.clarification_questions = [g["question"] for g in gaps]
            if snapshot.get("employee_satisfied") and snapshot.get("booked_room"):
                extraction.recommended_next_action = "route_to_outcome_engine"
                extraction.reason = (extraction.reason or "") + " | employee satisfied"
            elif snapshot.get("booking_confirmed") and snapshot.get("pending_confirmation"):
                extraction.recommended_next_action = "route_to_outcome_engine"
                extraction.reason = (extraction.reason or "") + " | requester confirmed meeting room booking"
            elif gaps:
                extraction.recommended_next_action = "clarification"
            else:
                extraction.recommended_next_action = "route_to_outcome_engine"
        else:
            extraction.entities = merged
        return extraction

    def _is_meeting_thread(self, extraction: ExtractionResult, merged: dict, event: RawEmailEvent) -> bool:
        """Meeting-room flow only when the admin agent said so or the thread already is a room case."""
        from app.models.intake import Conversation
        from app.models.outcome import Outcome

        in_room_case = any(k in merged for k in ("booked_room", "proposed_room", "attendees", "preferred_time", "duration_hours"))
        conv = self.session.get(Conversation, event.conversation_id) if event.conversation_id else None
        if conv and conv.current_outcome_id:
            current = self.session.get(Outcome, conv.current_outcome_id)
            if current and current.template_code != "SERVICE_REQUEST":
                in_room_case = in_room_case or (current.category or "").upper() == "MEETING_ROOM"
        handoff = getattr(self, "_handoff_categories", set())
        if handoff:
            return "meeting_room" in handoff or (in_room_case and "invoice" not in handoff)
        return extraction.event_type == "MEETING_ROOM" or in_room_case


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
