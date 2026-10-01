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


def _rfc_message_id(provider_id: Optional[str]) -> Optional[str]:
    """The Message-ID recipients see: CloudMailin's API hands back a bare id that goes out as <id@cloudmta.net>."""
    pid = (provider_id or "").strip()
    if not pid or pid.startswith("cloudmailin-api:"):
        return None
    if pid.startswith("<"):
        return pid
    return f"<{pid}>" if "@" in pid else f"<{pid}@cloudmta.net>"


def humanize_email_local(email: str) -> str:
    local = (email or "").split("@")[0].strip()
    if not local:
        return "there"
    local = re.sub(r"\d+$", "", local)
    parts = [p for p in re.split(r"[._+\-]+", local) if p]
    if not parts:
        return "there"
    # Avoid ugly single-token handles like "anonymousxo" / "anonymous"
    joined = "".join(parts).lower()
    if joined.startswith("anonymous") or (len(parts) == 1 and len(parts[0]) >= 11):
        return "team"
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


def _clean_signed_name(value: object) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip(",.-").strip()
    if not text or "@" in text or len(text) > 60 or len(text.split()) > 4:
        return None
    if text.lower() in {"there", "team", "user", "unknown", "admin", "regards", "thanks"}:
        return None
    return text


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
    """HR/master name, then the name they signed with, then From display name, then email local-part."""
    pid = person_id
    addr = (email or "").strip().lower()
    hdrs = headers
    signed = None
    cached = None
    if outcome is not None:
        pid = pid or outcome.requester_person_id
        addr = addr or (outcome.requester_email or "").strip().lower()
        facts = outcome.facts or {}
        signed = _clean_signed_name(facts.get("requester_name"))
        cached = facts.get("requester_display_name")
        cached = str(cached).strip() if cached and str(cached).strip().lower() != "there" else None
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
    if signed:
        return signed
    if cached:
        return cached
    from_name = display_name_from_headers(hdrs)
    if from_name:
        return from_name
    if addr:
        return humanize_email_local(addr)
    return "team"


def _event_clarification_extras(facts: dict) -> list[str]:
    """Provisional hold, included-vs-chargeable note and non-blocking asks for the first clarification."""
    parts: list[str] = []
    extra = [q for q in facts.get("event_extra_questions") or [] if q]
    if extra:
        parts.append("")
        parts.append("If you have them handy, please also share (these won't hold up the booking):\n")
        parts.extend(f"- {q}" for q in extra)
    hold = facts.get("provisional_hold") or {}
    if hold.get("room"):
        parts.append("")
        parts.append(
            f"Meanwhile I've provisionally held {hold['room']}"
            + (f" until {hold['expires_label']}" if hold.get("expires_label") else "")
            + " so it isn't taken while you reply."
        )
    note = str(facts.get("cost_preview") or "").strip()
    if note:
        parts.append("")
        parts.append(note)
    return parts


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
        polish: Optional[dict] = None,
    ) -> Communication:
        key = idempotency_key or (
            f"comm:{communication_type}:{outcome_id}:{subject}:{','.join(sorted(recipients))}"
        )
        from_addr = sender or (
            self.email_sender.get_account_email() if self.email_sender else None
        ) or "orchestration@prototype.local"

        def _execute():
            nonlocal body
            if polish:
                from app.ai.mail_writer import write_requester_mail

                body = write_requester_mail(draft=body, **polish) or body
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
        unconfirmed: Optional[list[str]] = None,
        force_send_key: Optional[str] = None,
        first_contact: bool = False,
        greeting_name: Optional[str] = None,
    ) -> Communication:
        questions = [q for q in questions if q]
        current = self.session.get(Outcome, conversation.current_outcome_id) if conversation.current_outcome_id else None
        category = (current.category if current else "") or ""
        is_room = category.upper() in {"", "MEETING_ROOM"}
        if not questions and is_room:
            from app.services.meeting_room import default_meeting_room_questions

            questions = default_meeting_room_questions()
        ref = case_reference or "PENDING"
        name = greeting_name or resolve_requester_name(self.session, conversation=conversation)
        from app.services.no_resource_flow import format_outbound_greeting, short_case_subject

        if first_contact:
            hint = (current.summary if current and (current.summary or "").startswith("Meeting for ") else "") or (
                "Request registered — details needed"
            )
            subject = short_case_subject(
                case_reference=ref, action_label="RECEIVED + INFORMATION REQUIRED", summary=hint, title=""
            )
        else:
            subject = f"[INFORMATION REQUIRED] [{ref}] Additional details needed"
        case_facts = dict((current.facts if current else None) or {})

        parts: list[str] = [f"{format_outbound_greeting(name)}\n"]
        kind = "meeting-room request" if is_room else "request"
        if first_contact:
            parts.append(f"Thanks for your {kind} — it's registered as {ref}.\n")
        if understood:
            parts.append("Here's what I have so far:\n")
            parts.extend(f"- {line}" for line in understood if line)
            parts.append("")
        if questions:
            if is_room:
                ask = "To lock in a room I just need:\n" if understood or not first_contact else "To find you a room, please share:\n"
            else:
                ask = "To take this forward I just need:\n"
            parts.append(ask)
            parts.extend(f"- {q}" for q in questions)
        lines = [line for line in (unconfirmed or []) if line]
        open_items = [line.replace(" (not confirmed)", "") for line in lines if not line.endswith("(assumed)")]
        defaults = [line[: -len("(assumed)")].strip() for line in lines if line.endswith("(assumed)")]
        if open_items:
            parts.append("")
            parts.append("Also worth a quick check:\n")
            parts.extend(f"- {line}" for line in open_items)
        if defaults:
            parts.append("")
            parts.append("I've set these for you — reply if any should change:\n")
            parts.extend(f"- {line}" for line in defaults)
        if is_room and questions:
            parts.extend(_event_clarification_extras(case_facts))
        if questions:
            parts.append("\nJust reply to this email with the details.")
        else:
            parts.append("\nReply to this email to confirm and I'll go ahead.")
        body = "\n".join(parts)
        outcome = current
        polish = {
            "purpose": "INFORMATION REQUIRED — ask for the missing details",
            "facts": dict((outcome.facts if outcome else None) or {}),
            "requester_name": name,
            "case_reference": ref if ref != "PENDING" else None,
        }
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
            polish=polish,
        )

    def _earlier_mails(self, outcome: Outcome, recipients: list[str]) -> list[Communication]:
        """Mail already sent on this case to exactly these people, oldest first."""
        want = sorted(r.strip().lower() for r in recipients)
        rows = self.session.exec(
            select(Communication)
            .where(Communication.outcome_id == outcome.outcome_id)
            .order_by(Communication.created_at)  # type: ignore[arg-type]
        ).all()
        return [m for m in rows if sorted(str(r).strip().lower() for r in (m.recipients or [])) == want]

    def send_case_update(
        self,
        *,
        outcome: Outcome,
        communication_type: str,
        body: str,
        recipients: list[str],
        action_label: Optional[str] = None,
        subject_hint: Optional[str] = None,
        suppress_fingerprint: Optional[str] = None,
    ) -> Communication | None:
        from app.services.no_resource_flow import short_case_subject

        label = action_label or communication_type.replace("_", " ")
        # Suppress identical stage mail when fingerprint unchanged
        if suppress_fingerprint:
            facts = dict(outcome.facts or {})
            last = facts.get("last_outbound") or {}
            if (
                isinstance(last, dict)
                and last.get("status") == "SENT"
                and last.get("suppress_fingerprint") == suppress_fingerprint
                and last.get("communication_type") == communication_type
                and (last.get("action_label") or "") == label
            ):
                self.record_suppressed(
                    outcome=outcome,
                    reason="duplicate_stage_fingerprint",
                    detail={
                        "fingerprint": suppress_fingerprint,
                        "action_label": label,
                        "communication_type": communication_type,
                    },
                )
                return None
        subject = short_case_subject(
            case_reference=outcome.case_reference or "",
            action_label=label,
            summary=subject_hint or (outcome.summary or ""),
            title=outcome.title or "",
        )
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
        requester = (outcome.requester_email or "").strip().lower()
        if outcome.template_code == "SERVICE_REQUEST":
            earlier = self._earlier_mails(outcome, recipients)
            if earlier:
                # Same subject and a reply chain, so every update for this case lands in one conversation.
                subject = re.sub(r"^\s*(?:re\s*:\s*)+", "", earlier[0].subject or "", flags=re.I) or subject
                ids = [i for i in (_rfc_message_id(m.provider_message_id or m.gmail_message_id) for m in earlier) if i]
                if ids:
                    in_reply_to = ids[-1]
                    if [r.strip().lower() for r in recipients] != [requester]:
                        thread_id = ids[0]
            elif label not in {"WORK ORDER", "DONE"} and outcome.title:
                # This subject heads the whole thread, so use the case title rather than this one update's headline.
                subject = short_case_subject(
                    case_reference=outcome.case_reference or "", action_label=label, summary=outcome.title, title=outcome.title,
                )
        key_suffix = suppress_fingerprint or event_id or hash(body)
        polish = None
        # Desk (non-room) cases already write human mail; the rewriter is tuned for room bookings.
        if requester and [r.strip().lower() for r in recipients] == [requester] and outcome.template_code != "SERVICE_REQUEST":
            polish = {
                "purpose": label,
                "facts": dict(outcome.facts or {}),
                "requester_name": resolve_requester_name(self.session, outcome=outcome),
                "case_reference": outcome.case_reference,
            }
        comm = self.send(
            communication_type=communication_type,
            recipients=recipients,
            subject=subject,
            body=body,
            conversation_id=outcome.conversation_id,
            outcome_id=outcome.outcome_id,
            thread_id=thread_id,
            in_reply_to_message_id=in_reply_to,
            idempotency_key=f"update:{outcome.outcome_id}:{communication_type}:{key_suffix}",
            polish=polish,
        )
        if suppress_fingerprint and outcome.outcome_id:
            facts = dict(outcome.facts or {})
            facts["last_outbound"] = {
                **(facts.get("last_outbound") or {}),
                "status": "SENT",
                "communication_type": communication_type,
                "action_label": label,
                "suppress_fingerprint": suppress_fingerprint,
                "message_id": comm.message_id,
                "subject": subject,
                "delivered": True,
            }
            outcome.facts = facts
            self.session.add(outcome)
            flag_modified(outcome, "facts")
        return comm

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