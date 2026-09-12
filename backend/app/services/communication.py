from typing import Optional

from sqlmodel import Session, select

from app.audit.service import AuditService
from app.connectors.base import EmailProvider
from app.core.enums import AuditAction, CommunicationType
from app.core.logging import get_logger
from app.models.intake import Conversation, RawEmailEvent
from app.models.outcome import Communication, Outcome
from app.services.intake import IdempotentActionService

logger = get_logger(__name__)


class CommunicationService:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        email_sender: Optional[EmailProvider] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.email_sender = email_sender
        self.audit = AuditService(session)
        self.actions = IdempotentActionService(session)

    def send(
        self,
        *,
        communication_type: str,
        recipients: list[str],
        subject: str,
        body: str,
        conversation_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        sender: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> Communication:
        key = idempotency_key or (
            f"comm:{communication_type}:{outcome_id}:{subject}:{','.join(sorted(recipients))}"
        )
        from_addr = sender or (
            self.email_sender.get_account_email() if self.email_sender else None
        ) or "orchestration@prototype.local"

        def _execute():
            msg = Communication(
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                outcome_id=outcome_id,
                thread_id=thread_id,
                communication_type=communication_type,
                sender=from_addr,
                recipients=recipients,
                subject=subject,
                body=body,
                idempotency_key=key,
            )
            self.session.add(msg)
            self.session.flush()
            delivery_error: Optional[str] = None
            if self.email_sender:
                try:
                    provider_id = self.email_sender.send_reply(
                        to=recipients,
                        subject=subject,
                        body=body,
                        conversation_id=thread_id,
                        in_reply_to_message_id=in_reply_to_message_id,
                    )
                    msg.provider_message_id = provider_id
                    msg.gmail_message_id = provider_id
                except Exception as exc:  # noqa: BLE001
                    delivery_error = str(exc)
                    logger.error("email_send_failed", error=delivery_error, key=key)
            else:
                logger.warning(
                    "email_sender_not_attached",
                    key=key,
                    hint="Communication stored only — configure CLOUDMAILIN_SMTP_URL + verified FROM for live replies",
                )
            self.audit.record(
                tenant_id=self.tenant_id,
                actor="system",
                action=AuditAction.COMMUNICATION_SENT,
                entity_type="Communication",
                entity_id=msg.message_id,
                after={
                    "type": communication_type,
                    "subject": subject,
                    "recipients": recipients,
                    "provider_message_id": msg.provider_message_id,
                    "delivered": bool(msg.provider_message_id) and not delivery_error,
                    "delivery_error": delivery_error,
                },
                correlation_id=outcome_id or conversation_id,
            )
            if delivery_error:
                logger.error("email_delivery_recorded_as_failed", key=key, error=delivery_error)
            return {"message_id": msg.message_id, "delivered": not delivery_error and bool(msg.provider_message_id)}

        result = self.actions.run_once(
            tenant_id=self.tenant_id,
            action_type="SEND_COMMUNICATION",
            idempotency_key=key,
            entity_type="Communication",
            execute_fn=_execute,
        )
        return self.session.exec(
            select(Communication).where(Communication.idempotency_key == key)
        ).first()

    def send_clarification(
        self,
        *,
        conversation: Conversation,
        questions: list[str],
        case_reference: Optional[str] = None,
    ) -> Communication:
        questions = [q for q in questions if q]
        if not questions:
            questions = [
                "How many people will attend?",
                "What date and preferred start time?",
                "How long do you need the room (duration)?",
            ]
        ref = case_reference or "PENDING"
        subject = f"[INFORMATION REQUIRED] [{ref}] Additional details needed"
        body = (
            "We need a few details to continue processing your request:\n\n"
            + "\n".join(f"- {q}" for q in questions)
            + "\n\nPlease reply to this email (use Reply — it routes back to our intake)."
        )
        # Prefer latest inbound provider message for Graph reply
        in_reply_to = None
        event = self.session.exec(
            select(RawEmailEvent)
            .where(RawEmailEvent.conversation_id == conversation.conversation_id)
            .order_by(RawEmailEvent.created_at.desc())  # type: ignore[attr-defined]
        ).first()
        if event:
            in_reply_to = event.provider_message_id or event.gmail_message_id

        return self.send(
            communication_type=CommunicationType.INFORMATION_REQUIRED.value,
            recipients=[conversation.requester_email],
            subject=subject,
            body=body,
            conversation_id=conversation.conversation_id,
            outcome_id=conversation.current_outcome_id,
            thread_id=conversation.thread_id,
            in_reply_to_message_id=in_reply_to,
            idempotency_key=f"clarify:{conversation.conversation_id}:{hash(tuple(questions))}",
        )

    def send_case_update(
        self,
        *,
        outcome: Outcome,
        communication_type: str,
        body: str,
        recipients: list[str],
        action_label: Optional[str] = None,
    ) -> Communication:
        label = action_label or communication_type.replace("_", " ")
        subject = f"[{label}] [{outcome.case_reference}] {outcome.title}"
        thread_id = None
        in_reply_to = None
        if outcome.conversation_id:
            conversation = self.session.get(Conversation, outcome.conversation_id)
            if conversation:
                thread_id = conversation.thread_id
            event = self.session.exec(
                select(RawEmailEvent)
                .where(RawEmailEvent.conversation_id == outcome.conversation_id)
                .order_by(RawEmailEvent.created_at.desc())  # type: ignore[attr-defined]
            ).first()
            if event:
                in_reply_to = event.provider_message_id or event.gmail_message_id
                thread_id = thread_id or event.provider_conversation_id or event.gmail_thread_id
        return self.send(
            communication_type=communication_type,
            recipients=recipients,
            subject=subject,
            body=body,
            conversation_id=outcome.conversation_id,
            outcome_id=outcome.outcome_id,
            thread_id=thread_id,
            in_reply_to_message_id=in_reply_to,
            idempotency_key=f"update:{outcome.outcome_id}:{communication_type}:{hash(body)}",
        )
