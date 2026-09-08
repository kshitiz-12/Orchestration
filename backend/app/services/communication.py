from typing import Optional

from sqlmodel import Session, select

from app.audit.service import AuditService
from app.core.enums import AuditAction, CommunicationType
from app.models.intake import Conversation
from app.models.org import NotificationTemplate
from app.models.outcome import Communication, Outcome
from app.services.intake import IdempotentActionService


class CommunicationService:
    def __init__(self, session: Session, tenant_id: str, email_sender=None):
        self.session = session
        self.tenant_id = tenant_id
        self.email_sender = email_sender
        self.audit = AuditService(session)
        self.actions = IdempotentActionService(session)

    def _render(self, template: str, **kwargs) -> str:
        result = template
        for k, v in kwargs.items():
            result = result.replace("{{" + k + "}}", str(v))
        return result

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
        sender: str = "orchestration@prototype.local",
    ) -> Communication:
        key = idempotency_key or f"comm:{communication_type}:{outcome_id}:{subject}:{','.join(sorted(recipients))}"

        def _execute():
            msg = Communication(
                tenant_id=self.tenant_id,
                conversation_id=conversation_id,
                outcome_id=outcome_id,
                thread_id=thread_id,
                communication_type=communication_type,
                sender=sender,
                recipients=recipients,
                subject=subject,
                body=body,
                idempotency_key=key,
            )
            self.session.add(msg)
            self.session.flush()
            if self.email_sender:
                try:
                    gmail_id = self.email_sender.send(
                        to=recipients,
                        subject=subject,
                        body=body,
                        thread_id=thread_id,
                    )
                    msg.gmail_message_id = gmail_id
                except Exception:
                    # Store outbound even if Gmail send fails — recoverable
                    pass
            self.audit.record(
                tenant_id=self.tenant_id,
                actor="system",
                action=AuditAction.COMMUNICATION_SENT,
                entity_type="Communication",
                entity_id=msg.message_id,
                after={"type": communication_type, "subject": subject, "recipients": recipients},
                correlation_id=outcome_id or conversation_id,
            )
            return {"message_id": msg.message_id}

        result = self.actions.run_once(
            tenant_id=self.tenant_id,
            action_type="SEND_COMMUNICATION",
            idempotency_key=key,
            entity_type="Communication",
            execute_fn=_execute,
        )
        if result["status"] == "already_done":
            existing = self.session.exec(
                select(Communication).where(Communication.idempotency_key == key)
            ).first()
            return existing
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
        ref = case_reference or "PENDING"
        subject = f"[INFORMATION REQUIRED] [{ref}] Additional details needed"
        body = (
            "We need a few details to continue processing your request:\n\n"
            + "\n".join(f"- {q}" for q in questions)
            + "\n\nPlease reply to this email thread."
        )
        return self.send(
            communication_type=CommunicationType.INFORMATION_REQUIRED.value,
            recipients=[conversation.requester_email],
            subject=subject,
            body=body,
            conversation_id=conversation.conversation_id,
            outcome_id=conversation.current_outcome_id,
            thread_id=conversation.thread_id,
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
        return self.send(
            communication_type=communication_type,
            recipients=recipients,
            subject=subject,
            body=body,
            conversation_id=outcome.conversation_id,
            outcome_id=outcome.outcome_id,
            idempotency_key=f"update:{outcome.outcome_id}:{communication_type}:{hash(body)}",
        )
