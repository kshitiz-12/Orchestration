from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.audit.service import AuditService
from app.connectors.base import EmailProvider
from app.core.enums import AuditAction, CommunicationType
from app.core.logging import get_logger
from app.models.intake import Conversation, RawEmailEvent
from app.models.org import Person
from app.models.outcome import Communication, Outcome
from app.services.intake import IdempotentActionService

logger = get_logger(__name__)


def humanize_email_local(email: str) -> str:
    local = (email or "").split("@")[0].strip()
    if not local:
        return "there"
    local = re.sub(r"\d+$", "", local)
    parts = [p for p in re.split(r"[._+\-]+", local) if p]
    if not parts:
        return "there"
    # Avoid ugly single-token handles like "anonymousxo"
    if len(parts) == 1 and len(parts[0]) >= 11:
        return "there"
    return " ".join(p[:1].upper() + p[1:].lower() for p in parts)


def display_name_from_headers(headers: Optional[dict]) -> Optional[str]:
    """Parse RFC From / sender display name from stored email headers."""
    if not headers:
        return None
    raw = (
        headers.get("from")
        or headers.get("From")
        or headers.get("sender")
        or headers.get("Sender")
        or ""
    )
    if isinstance(raw, list):
        raw = raw[0] if raw else ""
    text = str(raw).strip()
    if not text:
        return None
    # "Kapil Mantri" <kapil@…> or Kapil Mantri <kapil@…>
    m = re.match(r'^"?([^"<@]+?)"?\s*<[^>]+>$', text)
    if m:
        name = m.group(1).strip().strip('"').strip()
        if name and "@" not in name:
            return name
    if "<" not in text and "@" not in text and len(text.split()) <= 5:
        return text
    return None


def resolve_requester_name(
    session: Session,
    *,
    email: Optional[str] = None,
    person_id: Optional[str] = None,
    outcome: Optional[Outcome] = None,
    conversation: Optional[Conversation] = None,
    headers: Optional[dict] = None,
    event: Optional[RawEmailEvent] = None,
) -> str:
    """Prefer HR/master person name, then From display name, then email local-part."""
    pid = person_id
    addr = (email or "").strip().lower()
    hdrs = headers
    if outcome is not None:
        pid = pid or outcome.requester_person_id
        addr = addr or (outcome.requester_email or "").strip().lower()
        cached = (outcome.facts or {}).get("requester_display_name")
        if cached and str(cached).strip() and str(cached).strip().lower() != "there":
            return str(cached).strip()
    if conversation is not None:
        pid = pid or conversation.requester_person_id
        addr = addr or (conversation.requester_email or "").strip().lower()
    if event is not None:
        addr = addr or (event.sender or "").strip().lower()
        hdrs = hdrs or (event.headers or {})
    if pid:
        person = session.get(Person, pid)
        if person and (person.name or "").strip():
            return person.name.strip()
    if addr:
        person = session.exec(select(Person).where(Person.email == addr)).first()
        if person and (person.name or "").strip():
            return person.name.strip()
    from_name = display_name_from_headers(hdrs)
    if from_name:
        return from_name
    if addr:
        return humanize_email_local(addr)
    return "there"


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
        msg = self.session.exec(
            select(Communication).where(Communication.idempotency_key == key)
        ).first()
        if result.get("status") == "already_done":
            outcome = self.session.get(Outcome, outcome_id) if outcome_id else None
            if outcome:
                self.record_suppressed(
                    outcome=outcome,
                    reason="duplicate_idempotency_key",
                    detail={
                        "idempotency_key": key,
                        "communication_type": communication_type,
                        "subject": subject,
                        "existing_message_id": msg.message_id if msg else None,
                    },
                )
            if msg is not None:
                setattr(msg, "_suppressed", True)
                setattr(msg, "_suppress_reason", "duplicate_idempotency_key")
        elif outcome_id and msg is not None:
            outcome = self.session.get(Outcome, outcome_id)
            if outcome:
                facts = dict(outcome.facts or {})
                facts["last_outbound"] = {
                    "status": "SENT",
                    "communication_type": communication_type,
                    "message_id": msg.message_id,
                    "subject": subject,
                    "delivered": bool((result.get("result") or {}).get("delivered")),
                }
                outcome.facts = facts
                self.session.add(outcome)
                flag_modified(outcome, "facts")
        return msg

    def send_clarification(
        self,
        *,
        conversation: Conversation,
        questions: list[str],
        case_reference: Optional[str] = None,
        understood: Optional[list[str]] = None,
        force_send_key: Optional[str] = None,
        first_contact: bool = False,
        greeting_name: Optional[str] = None,
    ) -> Communication:
        questions = [q for q in questions if q]
        if not questions:
            from app.services.meeting_room import default_meeting_room_questions

            questions = default_meeting_room_questions()
        ref = case_reference or "PENDING"
        name = greeting_name or resolve_requester_name(self.session, conversation=conversation)
        if first_contact:
            subject = f"[INFORMATION REQUIRED] [{ref}] Request registered — details needed"
        else:
            subject = f"[INFORMATION REQUIRED] [{ref}] Additional details needed"
        parts: list[str] = [f"Dear {name},\n"]
        if first_contact:
            parts.append(
                f"Your meeting-room request has been registered as {ref}.\n"
            )
        if understood:
            parts.append("Here’s what we already have on file (no need to repeat these):\n")
            parts.extend(f"- {line}" for line in understood if line)
            parts.append("\nWe only still need:\n" if questions else "\n")
        elif first_contact:
            parts.append("To proceed, please share:\n")
        else:
            parts.append("We still need:\n")
        if questions:
            parts.extend(f"- {q}" for q in questions)
            parts.append(
                "\nPlease reply with just the missing items above (Reply keeps this thread)."
            )
        else:
            parts.append("\nPlease reply to confirm we can proceed.")
        body = "\n".join(parts)
        # Prefer latest inbound provider message for Graph reply
        in_reply_to = None
        event = self.session.exec(
            select(RawEmailEvent)
            .where(RawEmailEvent.conversation_id == conversation.conversation_id)
            .order_by(RawEmailEvent.created_at.desc())  # type: ignore[attr-defined]
        ).first()
        if event:
            in_reply_to = event.provider_message_id or event.gmail_message_id

        # force_send_key (e.g. event_id) ensures each inbound reply can trigger a new clarify mail
        # even if some questions overlap with a prior clarification.
        key_suffix = force_send_key or str(hash(tuple(questions)))
        return self.send(
            communication_type=CommunicationType.INFORMATION_REQUIRED.value,
            recipients=[conversation.requester_email],
            subject=subject,
            body=body,
            conversation_id=conversation.conversation_id,
            outcome_id=conversation.current_outcome_id,
            thread_id=conversation.thread_id,
            in_reply_to_message_id=in_reply_to,
            idempotency_key=f"clarify:{conversation.conversation_id}:{key_suffix}",
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
        event_id = None
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
                event_id = event.event_id
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
            idempotency_key=f"update:{outcome.outcome_id}:{communication_type}:{event_id or hash(body)}",
        )

    def record_suppressed(
        self,
        *,
        outcome: Outcome,
        reason: str,
        detail: Optional[dict] = None,
    ) -> None:
        """Every inbound must produce an outbound or a logged SUPPRESSED disposition."""
        from app.models.org import utcnow

        payload = {
            "status": "SUPPRESSED",
            "reason": reason,
            "at": utcnow().isoformat(),
            **(detail or {}),
        }
        logger.info(
            "outbound_suppressed",
            outcome_id=outcome.outcome_id,
            case_reference=outcome.case_reference,
            reason=reason,
            detail=detail or {},
        )
        facts = dict(outcome.facts or {})
        history = list(facts.get("outbound_suppressions") or [])
        history.append(payload)
        facts["outbound_suppressions"] = history[-20:]
        facts["last_outbound"] = payload
        outcome.facts = facts
        self.session.add(outcome)
        flag_modified(outcome, "facts")
        self.audit.record(
            tenant_id=self.tenant_id,
            actor="system",
            action=AuditAction.COMMUNICATION_SUPPRESSED,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after=payload,
            correlation_id=outcome.outcome_id,
        )