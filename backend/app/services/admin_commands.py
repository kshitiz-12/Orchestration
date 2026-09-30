"""Admin reply-by-mail: Gemini reads the ops reply, the handler validates and applies it."""

from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.ai.admin_interpreter import (
    AdminInterpreter,
    default_admin_interpreter,
    normalize_admin_decision,
)
from app.audit.service import AuditService
from app.core.enums import AuditAction
from app.core.logging import get_logger
from app.domain.meeting import REQUIREMENT_FIELDS, MeetingStage
from app.models.org import Resource, utcnow
from app.models.outcome import Approval, ExceptionRecord, Outcome
from app.services.admin_ops import admin_ops_email, trusted_ops_senders
from app.services.approval_actions import approval_pretty
from app.services.communication import CommunicationService, resolve_requester_name
from app.services.email_utils import prepare_interpreter_view
from app.services.meeting_room import (
    apply_meeting_room_defaults,
    compute_hold_window,
    requirement_fingerprint,
    seats_needed,
)
from app.services.no_resource_flow import detect_no_resource_choice, format_outbound_greeting
from app.services.room_booking import meeting_window

logger = get_logger(__name__)

_CASE_REF = re.compile(r"\[([A-Z]{2,5}-\d{4}-\d+)\]", re.I)

_MESSAGE = re.compile(
    r"^\s*(?:msg|message|tell(?:\s+(?:the\s+)?(?:requester|user|them))?|"
    r"reply(?:\s+to\s+(?:the\s+)?requester)?|inform(?:\s+(?:the\s+)?requester)?)\s*[:\-–]\s*(?P<text>.+)",
    re.I | re.S,
)
_BOOK = re.compile(
    r"^\s*(?:please\s+)?(?:book|allot|allocate|assign)\s+(?:the\s+)?(?:room|venue)?\s*[:\-–]?\s*(?P<room>[^\n.,;!]+)",
    re.I,
)
_CONFIRM_ROOM = re.compile(r"^\s*confirm\s+(?:room\s+)?(?P<room>[A-Za-z]*\d[\w\-/]*)\b", re.I)
_REJECT = re.compile(
    r"^\s*(?:reject(?:ed)?|decline(?:d)?|deny|denied|not\s+approved|disapprove(?:d)?|no\b|nope|refuse(?:d)?)",
    re.I,
)
_APPROVE = re.compile(
    r"^\s*(?:approve(?:d)?|approval\s+granted|ok(?:ay)?\b|go\s+ahead|proceed|yes\b|yep|confirm(?:ed)?|"
    r"sanction(?:ed)?|lgtm|done\b|granted)",
    re.I,
)

_CHOICE_COPY = {
    "LARGER_VENUE": (
        "Ops has approved a larger venue / off-site option for your meeting. "
        "We're arranging the venue now and will send you the confirmed location shortly."
    ),
    "SPLIT_ROOMS": (
        "Ops has approved splitting your meeting across rooms. "
        "We'll send you the room details shortly."
    ),
    "DIFFERENT_TIME": (
        "Ops has approved moving your meeting to a different slot. "
        "Please reply with the date and time that works for you and we'll book it."
    ),
    "REDUCE_HEADCOUNT": (
        "Ops has approved going ahead with a smaller group. "
        "Please reply with the reduced headcount and we'll re-check rooms."
    ),
}


def sender_address(sender: Optional[str]) -> str:
    return parseaddr(sender or "")[1].strip().lower()


def is_admin_sender(sender: Optional[str]) -> bool:
    addr = sender_address(sender)
    return bool(addr) and addr in trusted_ops_senders()


_MSG_ID = re.compile(r"<([^<>\s]+)>")


def _lower_headers(headers: Any) -> dict[str, Any]:
    return {str(k).lower(): v for k, v in (headers or {}).items()} if isinstance(headers, dict) else {}


def _spf(envelope: Any) -> tuple[str, str]:
    env = envelope if isinstance(envelope, dict) else {}
    spf = env.get("spf")
    if isinstance(spf, dict):
        return str(spf.get("result") or "").lower(), str(spf.get("domain") or "").lower()
    return str(env.get("spf][result") or "").lower(), str(env.get("spf][domain") or "").lower()


def verify_ops_sender(session: Session, tenant_id: str, headers: Any, sender: str) -> tuple[bool, str]:
    """A From header is trivially spoofed; require SPF/DKIM for the sender's domain or a reply to our own mail."""
    from app.core.config import get_settings
    from app.models.outcome import Communication

    if (get_settings().admin_sender_verification or "strict").strip().lower() in {"off", "none", "false", "0"}:
        return True, "verification_off"
    domain = sender.rsplit("@", 1)[-1]
    hdrs = _lower_headers(headers)

    result, spf_domain = _spf(hdrs.get("_envelope"))
    if result == "pass" and spf_domain and (spf_domain == domain or spf_domain.endswith("." + domain)):
        return True, "spf_pass"

    auth = str(hdrs.get("authentication-results") or hdrs.get("arc-authentication-results") or "").lower()
    if re.search(rf"dkim=pass[^;]*header\.(?:d|i)=@?(?:[\w.-]+\.)?{re.escape(domain)}\b", auth):
        return True, "dkim_pass"

    ids = {m.strip().lower() for key in ("in-reply-to", "references") for m in _MSG_ID.findall(str(hdrs.get(key) or ""))}
    if ids:
        # CloudMailin's API returns our id bare ("a0578687-…") while replies reference
        # "<a0578687-…@cloudmta.net>", so match on the local part too.
        locals_ = {i.split("@", 1)[0] for i in ids}
        variants = list(ids | locals_ | {f"<{i}>" for i in ids | locals_})
        rows = session.exec(
            select(Communication).where(
                Communication.tenant_id == tenant_id,
                (Communication.provider_message_id.in_(variants))  # type: ignore[union-attr]
                | (Communication.gmail_message_id.in_(variants)),  # type: ignore[union-attr]
            )
        ).all()
        for row in rows:
            if sender in [str(r).strip().lower() for r in (row.recipients or [])]:
                return True, "reply_to_our_mail"
    return False, "unverified"


def case_reference_from_subject(subject: Optional[str]) -> Optional[str]:
    m = _CASE_REF.search(subject or "")
    return m.group(1).upper() if m else None


def admin_reply_text(body: str) -> str:
    """Only what the admin typed — never the quoted briefing below it."""
    view = prepare_interpreter_view(body or "")
    text = (view.get("this_message") or "").strip()
    if not text:
        text = (body or "").strip().split("\n\n", 1)[0].strip()
    return text


def _tail(text: str, match: re.Match[str]) -> str:
    rest = text[match.end():].strip(" \t:-–,.")
    return rest.strip()


def parse_admin_command(text: str) -> dict[str, Any]:
    """Offline fallback only (Gemini unavailable). Same shape as normalize_admin_decision."""
    raw = (text or "").strip()
    first = raw.split("\n", 1)[0].strip()
    result: dict[str, Any] = {
        "action": "NONE",
        "room": None,
        "rooms": [],
        "choice_code": None,
        "fact_updates": {},
        "reason": None,
        "message_to_requester": None,
        "understood_as": "No actionable instruction found",
        "confidence": 0.9,
        "needs_clarification": False,
        "clarification_question": None,
    }
    if not raw:
        return result

    m = _MESSAGE.match(raw)
    if m:
        msg = m.group("text").strip()
        result.update(action="MESSAGE_REQUESTER", message_to_requester=msg, understood_as="Pass a message to the requester")
        return result

    m = _BOOK.match(first) or _CONFIRM_ROOM.match(first)
    if m:
        room = re.sub(
            r"\s+(?:for\s+(?:them|this|the\s+requester)|please|pls|asap)\s*$", "", m.group("room").strip(), flags=re.I
        ).strip()
        if room:
            result.update(action="BOOK", room=room, understood_as=f"Book {room}")
            return result

    m = _REJECT.match(first)
    if m:
        result.update(action="REJECT", reason=_tail(raw, m) or None, understood_as="Reject the pending item")
        return result

    choice = detect_no_resource_choice(raw)
    m = _APPROVE.match(first)
    if m:
        result.update(
            action="APPROVE",
            message_to_requester=_tail(raw, m) or None,
            choice_code=choice["code"] if choice else None,
            understood_as="Approve the pending item",
        )
        return result

    if choice:
        result.update(action="CHOOSE_ALTERNATIVE", choice_code=choice["code"], understood_as=f"Choose {choice['label']}")
    return result


class AdminCommandHandler:
    """Applies one admin reply to one case, mails the requester, acks the admin."""

    MIN_CONFIDENCE = 0.55

    def __init__(
        self,
        session: Session,
        tenant_id: str,
        comms: CommunicationService,
        interpreter: Optional[AdminInterpreter] = None,
    ):
        from app.engine.meeting_scenario import ClientMeetingOrchestrator
        from app.engine.outcome_engine import OutcomeEngine

        self.session = session
        self.tenant_id = tenant_id
        self.comms = comms
        self.engine = OutcomeEngine(session, tenant_id)
        self.orch = ClientMeetingOrchestrator(session, tenant_id, self.engine, comms)
        self.audit = AuditService(session)
        self.interpreter = interpreter if interpreter is not None else default_admin_interpreter()

    # ---------- entry
    def handle(self, *, outcome: Outcome, body: str, event_id: str, admin_email: str) -> dict[str, Any]:
        self.event_id = event_id
        self.admin_email = admin_email
        self.actor = f"admin:{admin_email}"

        view = prepare_interpreter_view(body or "")
        text = admin_reply_text(body)
        package = self.orch.apply_package_reply(outcome, text, admin_email, is_admin=is_admin_sender(admin_email))
        if package:
            cmd = {"action": package["action"], "raw": text[:500], "path": "task_package", "confidence": 1.0}
            self._record(outcome, cmd, package)
            return {"action": package["action"], "interpretation_path": "task_package", **package}
        cmd = self._interpret(outcome, text, view.get("quoted_thread_excerpt") or "")
        cmd["raw"] = text[:500]
        action = cmd["action"]
        cmd["note"] = cmd.get("reason") if action == "REJECT" else cmd.get("message_to_requester")
        if cmd.get("choice_code"):
            code = cmd["choice_code"]
            cmd["choice"] = {"code": code, "label": code.replace("_", " ").title()}

        if cmd.get("needs_clarification") or cmd["confidence"] < self.MIN_CONFIDENCE:
            result = {
                "applied": False,
                "summary": cmd.get("clarification_question")
                or "Your reply was ambiguous for this case — nothing was changed.",
            }
        else:
            handler = {
                "APPROVE": self._approve,
                "CHOOSE_ALTERNATIVE": self._approve,
                "REJECT": self._reject,
                "BOOK": self._book,
                "UPDATE_FACTS": self._update_facts,
                "MESSAGE_REQUESTER": self._message,
                "HOLD": self._hold,
                "CANCEL": self._cancel,
            }.get(action)
            if handler:
                result = handler(outcome, cmd)
            else:
                result = {"applied": False, "summary": "Nothing actionable in your reply — nothing was changed."}

        self._record(outcome, cmd, result)
        if not result.get("skip_ack"):
            self._ack_admin(outcome, cmd, result)
        logger.info(
            "admin_command_handled",
            case=outcome.case_reference,
            action=action,
            path=cmd.get("path"),
            confidence=cmd.get("confidence"),
            applied=result.get("applied"),
        )
        return {
            "action": action,
            "interpretation_path": cmd.get("path"),
            "understood_as": cmd.get("understood_as"),
            **{k: v for k, v in result.items() if k != "skip_ack"},
        }

    def _interpret(self, outcome: Outcome, text: str, briefing: str) -> dict[str, Any]:
        if self.interpreter is not None:
            try:
                data, endpoint = self.interpreter.interpret(
                    self._interpreter_payload(outcome, text, briefing)
                )
                cmd = normalize_admin_decision(data)
                cmd["path"] = f"gemini:{(endpoint or {}).get('label') or 'ok'}"
                return cmd
            except Exception as exc:  # noqa: BLE001
                logger.warning("admin_interpreter_failed_using_rules", error=str(exc)[:300])
        cmd = parse_admin_command(text)
        cmd["path"] = "rules_fallback"
        return cmd

    def _interpreter_payload(self, outcome: Outcome, text: str, briefing: str) -> dict[str, Any]:
        facts = dict(outcome.facts or {})
        on_file = {k: facts.get(k) for k in REQUIREMENT_FIELDS if facts.get(k) not in (None, "")}
        rooms = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type.in_(["MEETING_ROOM", "OFFSITE_VENUE"]),  # type: ignore[attr-defined]
            )
        ).all()
        window = meeting_window(facts)
        return {
            "admin_typed": text,
            "briefing_they_replied_to": briefing[-2500:],
            "case": {
                "case_reference": outcome.case_reference,
                "stage": facts.get("orchestration_stage") or outcome.status,
                "summary": outcome.summary,
                "requester": outcome.requester_email,
                "facts_on_file": on_file,
                "requester_choice": facts.get("no_resource_choice"),
                "no_room_alternatives": [
                    {"code": a.get("code"), "label": a.get("label")}
                    for a in (facts.get("no_resource_alternatives") or [])
                    if isinstance(a, dict)
                ],
                "no_room_diagnosis": (facts.get("no_resource_diagnosis") or {}).get("line")
                if isinstance(facts.get("no_resource_diagnosis"), dict)
                else None,
                "proposed_room": (facts.get("proposed_room") or {}).get("name")
                if facts.get("pending_confirmation")
                else None,
                "booked_room": (facts.get("booked_room") or {}).get("name"),
                "seats_needed_in_room": seats_needed(facts),
                "pending_approvals": [
                    {"type": a.approval_type, "payload": a.payload} for a in self._pending_approvals(outcome)
                ],
                "open_special_requests": [
                    (r.get("text") if isinstance(r, dict) else str(r)) for r in (facts.get("open_requests") or [])
                ],
                "requester_latest_message": (facts.get("raw_reply") or "")[:800],
                "previous_admin_commands": [
                    {"action": c.get("action"), "raw": c.get("raw")} for c in (facts.get("admin_commands") or [])[-5:]
                ],
            },
            "rooms_in_inventory": [
                {
                    "name": r.name,
                    "kind": "off-site venue" if r.type == "OFFSITE_VENUE" else "meeting room",
                    "capacity": (r.attributes or {}).get("capacity"),
                    "free_for_this_meeting": self.orch.bookings.is_free(
                        r, window, exclude_outcome_id=outcome.outcome_id
                    ),
                }
                for r in rooms
            ],
        }

    # ---------- actions
    def _cancel(self, outcome: Outcome, cmd: dict) -> dict:
        facts = outcome.facts or {}
        if facts.get("orchestration_stage") == MeetingStage.CANCELLED.value:
            return {"applied": False, "summary": "Case was already cancelled."}
        self.orch.cancel_case(
            outcome,
            actor=self.actor,
            reason=cmd.get("message_to_requester") or cmd.get("reason") or "",
        )
        return {"applied": True, "summary": "Case cancelled, room released, requester told.", "requester_notified": True}

    def _hold(self, outcome: Outcome, cmd: dict) -> dict:
        facts = dict(outcome.facts or {})
        facts["admin_decision"] = {
            "decision": "HOLD",
            "by": self.admin_email,
            "at": utcnow().isoformat(),
            "note": cmd.get("reason") or "",
        }
        facts["needs_ops"] = True
        facts["last_action"] = "admin_hold"
        self._save(outcome, facts)
        if cmd.get("message_to_requester"):
            self._mail_requester(
                outcome,
                label="UPDATE FROM OPS",
                lines=[cmd["message_to_requester"]],
                communication_type="INFORMATION_ONLY",
            )
        return {
            "applied": True,
            "summary": "Case put on hold" + (f" ({cmd['reason']})" if cmd.get("reason") else "") + ".",
            "requester_notified": bool(cmd.get("message_to_requester")),
        }

    def _update_facts(self, outcome: Outcome, cmd: dict) -> dict:
        updates = dict(cmd.get("fact_updates") or {})
        if not updates:
            return {"applied": False, "summary": "No requirement change could be read from your reply."}
        # Pass updates as fresh input so the orchestrator sees them as a change and re-searches.
        self.orch.run(outcome, updates, extraction=None)
        facts = dict(outcome.facts or {})
        facts["admin_decision"] = {
            "decision": "UPDATED_FACTS",
            "fields": updates,
            "by": self.admin_email,
            "at": utcnow().isoformat(),
        }
        self._save(outcome, facts)
        if cmd.get("message_to_requester"):
            self._mail_requester(
                outcome,
                label="UPDATE FROM OPS",
                lines=[cmd["message_to_requester"]],
                communication_type="INFORMATION_ONLY",
            )
        changed = ", ".join(f"{k.replace('_', ' ')} → {v}" for k, v in updates.items())
        stage = facts.get("orchestration_stage") or "—"
        room = (facts.get("proposed_room") or {}).get("name") if facts.get("pending_confirmation") else None
        booked = (facts.get("booked_room") or {}).get("name")
        if booked:
            tail = f" Booking now: {booked}" + (" (needs ops — no room fits)." if facts.get("needs_ops") else ".")
        elif room:
            tail = f" Proposed {room} to the requester."
        else:
            tail = f" Stage now {stage}."
        return {"applied": True, "summary": f"Updated {changed}; re-ran room search.{tail}", "requester_notified": True}

    def _message(self, outcome: Outcome, cmd: dict) -> dict:
        msg = (cmd.get("message_to_requester") or "").strip()
        if not msg or not outcome.requester_email:
            return {"applied": False, "summary": "No message text / requester email — nothing sent."}
        self._mail_requester(
            outcome,
            label="UPDATE FROM OPS",
            lines=[msg],
            communication_type="INFORMATION_ONLY",
        )
        return {"applied": True, "summary": "Your message was sent to the requester.", "requester_notified": True}

    def _approve(self, outcome: Outcome, cmd: dict) -> dict:
        facts = dict(outcome.facts or {})
        stage = (facts.get("orchestration_stage") or "").upper()

        pending = self._pending_approvals(outcome)
        if pending and cmd["action"] == "APPROVE":
            return self._decide_approvals(outcome, pending, approved=True, note=cmd.get("note") or "")

        if facts.get("booked_room"):
            return {"applied": False, "summary": "Case is already booked and nothing is pending approval."}

        if stage == MeetingStage.NO_RESOURCE.value:
            return self._approve_alternative(outcome, facts, cmd)

        if cmd["action"] == "CHOOSE_ALTERNATIVE":
            return {"applied": False, "summary": f"Alternatives only apply to a no-room case; this case is {stage or '—'}."}

        if facts.get("proposed_room") and facts.get("pending_confirmation"):
            return self._book(outcome, {**cmd, "room": None})

        if stage == MeetingStage.AWAITING_REQUIREMENTS.value:
            return {
                "applied": False,
                "summary": "Still gathering requirements from the requester — nothing to approve yet. "
                "Name a room to book it anyway, or tell me what to pass on to them.",
            }

        return self._book(outcome, {**cmd, "room": None})

    def _approve_alternative(self, outcome: Outcome, facts: dict, cmd: dict) -> dict:
        alts = list(facts.get("no_resource_alternatives") or [])
        choice = cmd.get("choice") or facts.get("no_resource_choice")
        if isinstance(choice, dict) and choice.get("code") and not choice.get("label"):
            choice = {**choice, "label": choice["code"].replace("_", " ").title()}
        if choice and alts:
            labelled = detect_no_resource_choice(str(choice.get("label") or choice.get("code")), alts)
            if labelled and labelled.get("code") == choice.get("code"):
                choice = labelled
        if not choice:
            return {
                "applied": False,
                "summary": "Requester hasn't picked an alternative yet. Reply LARGER VENUE, SPLIT ROOMS, "
                "DIFFERENT TIME, or BOOK <venue>.",
            }

        code = str(choice.get("code"))
        facts["no_resource_choice"] = choice
        facts["admin_decision"] = {
            "decision": "APPROVED",
            "choice": code,
            "by": self.admin_email,
            "at": utcnow().isoformat(),
            "note": cmd.get("note") or "",
        }
        facts["needs_ops"] = True
        facts["last_action"] = f"admin_approved:{code}"
        facts["outbound_required"] = "admin_approved"
        self._save(outcome, facts)
        self._note_exception(
            outcome,
            note=f"Ops approved {code} ({self.admin_email})" + (f": {cmd['note']}" if cmd.get("note") else ""),
        )

        lines = [_CHOICE_COPY.get(code, f"Ops has approved: {choice.get('label')}.")]
        if cmd.get("note"):
            lines.append(f"Note from ops: {cmd['note']}")
        self._mail_requester(outcome, label="OPS APPROVED", lines=lines, communication_type="INFORMATION_ONLY")

        next_step = {
            "LARGER_VENUE": "Next: once the venue is fixed, just reply with it (e.g. \"book Hyatt ballroom\") — "
            "the requester gets the confirmation.",
            "SPLIT_ROOMS": "Next: reply with the rooms once fixed (e.g. \"put them in F2-R1 and F2-R2\").",
            "DIFFERENT_TIME": "Requester was asked for a new slot; the system re-searches when they reply.",
            "REDUCE_HEADCOUNT": "Requester was asked for the new headcount; the system re-searches when they reply.",
        }.get(code, "")
        return {
            "applied": True,
            "summary": f"Approved requester alternative: {choice.get('label')}. Requester informed.",
            "next": next_step,
            "requester_notified": True,
        }

    def _reject(self, outcome: Outcome, cmd: dict) -> dict:
        reason = (cmd.get("note") or "").strip()
        facts = dict(outcome.facts or {})
        stage = (facts.get("orchestration_stage") or "").upper()

        pending = self._pending_approvals(outcome)
        if pending:
            return self._decide_approvals(outcome, pending, approved=False, note=reason)

        if stage == MeetingStage.NO_RESOURCE.value:
            prev = facts.get("no_resource_choice") or {}
            facts.pop("no_resource_choice", None)
            facts["admin_decision"] = {
                "decision": "REJECTED",
                "choice": prev.get("code") if isinstance(prev, dict) else None,
                "by": self.admin_email,
                "at": utcnow().isoformat(),
                "note": reason,
            }
            facts["last_action"] = "admin_rejected_alternative"
            facts["outbound_required"] = "admin_rejected"
            self._save(outcome, facts)
            self._note_exception(outcome, note=f"Ops rejected alternative ({self.admin_email}): {reason or '—'}")
            label = prev.get("label") if isinstance(prev, dict) else None
            alt_lines = [
                f"- {a.get('label')}"
                for a in (facts.get("no_resource_alternatives") or [])
                if a.get("code") not in {"REVIEW_NEAR_MISS", (prev or {}).get("code")}
            ]
            lines = [
                f"Our ops team couldn't arrange {label or 'that option'}."
                + (f" Reason: {reason}" if reason else ""),
            ]
            if cmd.get("message_to_requester"):
                lines.append(cmd["message_to_requester"])
            if alt_lines:
                lines.append("Please reply with another option:\n" + "\n".join(alt_lines))
            self._mail_requester(outcome, label="OPS UPDATE", lines=lines, communication_type="ACTION_REQUIRED")
            return {"applied": True, "summary": "Alternative rejected; requester asked to pick another.", "requester_notified": True}

        if facts.get("proposed_room") and facts.get("pending_confirmation") and not facts.get("booked_room"):
            proposal = facts.get("proposed_room") or {}
            self._release_room(outcome)
            facts["proposed_room"] = None
            facts["pending_confirmation"] = False
            facts["needs_ops"] = True
            facts["last_action"] = "admin_rejected_proposal"
            facts["admin_decision"] = {
                "decision": "REJECTED",
                "room": proposal.get("name"),
                "by": self.admin_email,
                "at": utcnow().isoformat(),
                "note": reason,
            }
            self._save(outcome, facts)
            lines = [
                f"After ops review, {proposal.get('name') or 'the proposed room'} can't be used for this request."
                + (f" Reason: {reason}" if reason else ""),
                cmd.get("message_to_requester") or "",
                "We're finding an alternative and will come back to you shortly.",
            ]
            self._mail_requester(outcome, label="OPS UPDATE", lines=lines, communication_type="INFORMATION_ONLY")
            return {
                "applied": True,
                "summary": "Proposed room released; requester told ops is finding an alternative. "
                "Reply BOOK <room> to set one.",
                "requester_notified": True,
            }

        return {"applied": False, "summary": "Nothing on this case is waiting for a decision to reject."}

    def _book(self, outcome: Outcome, cmd: dict) -> dict:
        facts = dict(outcome.facts or {})
        names = [str(n).strip() for n in (cmd.get("rooms") or []) if str(n).strip()]
        if not names and (cmd.get("room") or "").strip():
            names = [cmd["room"].strip()]
        already = facts.get("booked_room")
        if already and not names:
            return {"applied": False, "summary": f"Already booked: {already.get('name')}. No change made."}
        facts = apply_meeting_room_defaults(facts)
        facts.update(compute_hold_window(facts))
        window = meeting_window(facts)

        rooms: list[Resource] = []
        if names:
            rooms = [self._find_room(n) or self._learn_offsite(n, facts) for n in names]
        else:
            proposed = facts.get("proposed_room") or {}
            ids = [r.get("resource_id") for r in proposed.get("rooms") or []] or [proposed.get("resource_id")]
            rooms = [r for r in (self.session.get(Resource, i) for i in ids if i) if r is not None]
            if not rooms:
                picked = self.orch._pick_room(facts, outcome.outcome_id)
                rooms = [picked] if picked else []
        if not rooms:
            return {
                "applied": False,
                "summary": "No room fits from inventory. Reply with a room or venue name to book one explicitly.",
            }

        busy = [r.name for r in rooms if not self.orch.bookings.is_free(r, window, exclude_outcome_id=outcome.outcome_id)]
        if busy:
            return {
                "applied": False,
                "summary": f"{', '.join(busy)} is already booked at that time for another case — nothing changed. "
                "Name a different room or venue.",
            }

        if already:
            return self._move_booking(outcome, facts, rooms, cmd)

        proposal: dict[str, Any] = {
            "resource_id": rooms[0].resource_id if len(rooms) == 1 else None,
            "name": " + ".join(r.name for r in rooms),
            "capacity": sum(int((r.attributes or {}).get("capacity") or 0) for r in rooms),
        }
        if len(rooms) > 1:
            proposal["split"] = True
            proposal["rooms"] = [
                {"resource_id": r.resource_id, "name": r.name, "capacity": (r.attributes or {}).get("capacity")}
                for r in rooms
            ]
        if any(r.type == "OFFSITE_VENUE" for r in rooms):
            proposal["external_venue"] = True

        proposal.update(
            {
                "attendees": facts.get("attendees"),
                "date": facts.get("date"),
                "start": facts.get("preferred_time") or facts.get("time_window"),
                "end": facts.get("end_time"),
                "duration_hours": facts.get("duration_hours"),
                "hold_start": facts.get("hold_start"),
                "hold_end": facts.get("hold_end"),
                "assigned_to_email": outcome.requester_email,
                "fingerprint": requirement_fingerprint(facts),
                "booked_by_admin": self.admin_email,
            }
        )
        facts["proposed_room"] = proposal
        facts["pending_confirmation"] = True
        facts["booking_confirmed"] = True
        facts["admin_decision"] = {
            "decision": "BOOKED",
            "room": proposal["name"],
            "by": self.admin_email,
            "at": utcnow().isoformat(),
            "note": cmd.get("note") or "",
        }
        self._save(outcome, facts)
        self.orch._finalize_booking(outcome, actor=self.actor)
        self._resolve_exceptions(outcome, resolution=f"Booked {proposal['name']} by ops ({self.admin_email})")
        if cmd.get("message_to_requester"):
            self._mail_requester(
                outcome,
                label="UPDATE FROM OPS",
                lines=[cmd["message_to_requester"]],
                communication_type="INFORMATION_ONLY",
            )
        return {
            "applied": True,
            "summary": f"Booked {proposal['name']}. Requester got BOOKING CONFIRMED.",
            "requester_notified": True,
            "skip_ack": True,
        }

    def _learn_offsite(self, name: str, facts: dict) -> Resource:
        """A venue ops named that isn't in inventory becomes bookable inventory (so clashes are tracked)."""
        venue = Resource(
            tenant_id=self.tenant_id,
            type="OFFSITE_VENUE",
            name=name[:120],
            status="AVAILABLE",
            attributes={
                "capacity": seats_needed(facts) or None,
                "offsite": True,
                "added_by": self.admin_email,
            },
        )
        self.session.add(venue)
        self.session.flush()
        return venue

    def _move_booking(self, outcome: Outcome, facts: dict, rooms: list[Resource], cmd: dict) -> dict:
        old = dict(facts.get("booked_room") or {})
        window = meeting_window(facts)
        keep: set[str] = set()
        parts = []
        for room in rooms:
            row = self.orch.bookings.confirm(
                outcome_id=outcome.outcome_id,
                room_name=room.name,
                window=window,
                resource_id=room.resource_id,
                is_offsite=room.type == "OFFSITE_VENUE",
                attributes={"moved_by": self.admin_email, "moved_from": old.get("name")},
                keep=keep,
            )
            keep.add(row.booking_id)
            parts.append({"resource_id": room.resource_id, "name": room.name, "booking_id": row.booking_id,
                          "capacity": (room.attributes or {}).get("capacity")})
        new_name = " + ".join(r.name for r in rooms)
        booked = {
            **old,
            "resource_id": rooms[0].resource_id if len(rooms) == 1 else None,
            "name": new_name,
            "booking_id": parts[0]["booking_id"],
            "moved_from": old.get("name"),
            "moved_by_admin": self.admin_email,
        }
        booked.pop("rooms", None)
        booked.pop("split", None)
        if len(rooms) > 1:
            booked.update({"rooms": parts, "split": True})
        facts["booked_room"] = booked
        facts["needs_ops"] = False
        facts["last_action"] = "admin_moved_booking"
        facts["admin_decision"] = {
            "decision": "MOVED",
            "room": new_name,
            "from": old.get("name"),
            "by": self.admin_email,
            "at": utcnow().isoformat(),
        }
        self._save(outcome, facts)
        for row in self._open_exceptions(outcome):
            if row.exception_type in {"POST_BOOKING_CHANGE", "NO_MEETING_ROOM"}:
                row.status = "RESOLVED"
                row.resolution = f"Moved to {new_name} by ops ({self.admin_email})"
                row.resolved_at = utcnow()
                self.session.add(row)
        lines = [f"Your meeting has been moved from {old.get('name') or 'the earlier room'} to {new_name}."]
        if cmd.get("message_to_requester"):
            lines.append(cmd["message_to_requester"])
        self._mail_requester(outcome, label="ROOM CHANGED", lines=lines, communication_type="INFORMATION_ONLY")
        return {"applied": True, "summary": f"Moved booking {old.get('name')} → {new_name}. Requester told.",
                "requester_notified": True}

    # ---------- approvals
    def _pending_approvals(self, outcome: Outcome) -> list[Approval]:
        return list(
            self.session.exec(
                select(Approval).where(
                    Approval.outcome_id == outcome.outcome_id,
                    Approval.decision == "PENDING",
                )
            ).all()
        )

    def _decide_approvals(self, outcome: Outcome, pending: list[Approval], *, approved: bool, note: str) -> dict:
        decision = "APPROVED" if approved else "REJECTED"
        types: list[str] = []
        for approval in pending:
            approval.decision = decision
            approval.reason = note or f"{decision.title()} by mail ({self.admin_email})"
            approval.decided_at = utcnow()
            self.session.add(approval)
            types.append(approval.approval_type)
            self.audit.record(
                tenant_id=self.tenant_id,
                actor=self.actor,
                action=AuditAction.APPROVAL_GRANTED if approved else AuditAction.APPROVAL_REJECTED,
                entity_type="Approval",
                entity_id=approval.approval_id,
                after={"decision": decision, "reason": approval.reason, "via": "admin_mail"},
                correlation_id=outcome.outcome_id,
            )
            self.orch.on_approval_decided(outcome, approval, approved=approved, note=note or "")

        facts = dict(outcome.facts or {})
        facts["last_action"] = f"admin_{decision.lower()}:{','.join(types)}"
        self._save(outcome, facts)

        pretty = ", ".join(approval_pretty(t, facts) for t in types)
        if approved:
            lines = [f"Your {pretty} request has been approved by ops."]
        else:
            lines = [f"Your {pretty} request was not approved by ops." + (f" Reason: {note}" if note else "")]
            if facts.get("booked_room"):
                lines.append("Your room booking itself is unaffected.")
        if note and approved:
            lines.append(f"Note from ops: {note}")
        self._mail_requester(
            outcome,
            label="OPS APPROVED" if approved else "OPS UPDATE",
            lines=lines,
            communication_type="INFORMATION_ONLY",
        )
        return {
            "applied": True,
            "summary": f"{decision.title()}: {pretty}. Requester informed.",
            "requester_notified": True,
        }

    # ---------- helpers
    def _find_room(self, name: str) -> Optional[Resource]:
        rooms = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type.in_(["MEETING_ROOM", "OFFSITE_VENUE"]),  # type: ignore[attr-defined]
            )
        ).all()
        needle = re.sub(r"\s+", "", name.lower())
        for room in rooms:
            if re.sub(r"\s+", "", (room.name or "").lower()) == needle:
                return room
        for room in rooms:
            hay = re.sub(r"\s+", "", (room.name or "").lower())
            if needle and (needle in hay or hay in needle):
                return room
        return None

    def _release_room(self, outcome: Outcome) -> None:
        self.orch.bookings.release_for_outcome(outcome.outcome_id, only_held=True)

    def _open_exceptions(self, outcome: Outcome) -> list[ExceptionRecord]:
        return list(
            self.session.exec(
                select(ExceptionRecord).where(
                    ExceptionRecord.outcome_id == outcome.outcome_id,
                    ExceptionRecord.status.in_(["OPEN", "IN_PROGRESS"]),  # type: ignore[attr-defined]
                )
            ).all()
        )

    def _note_exception(self, outcome: Outcome, *, note: str) -> None:
        for row in self._open_exceptions(outcome):
            if row.exception_type != "NO_MEETING_ROOM":
                continue
            row.description = ((row.description or "") + f"\n{note}").strip()
            self.session.add(row)

    def _resolve_exceptions(self, outcome: Outcome, *, resolution: str) -> None:
        for row in self._open_exceptions(outcome):
            if row.exception_type != "NO_MEETING_ROOM":
                continue
            row.status = "RESOLVED"
            row.resolution = resolution
            row.resolved_at = utcnow()
            self.session.add(row)

    def _save(self, outcome: Outcome, facts: dict) -> None:
        outcome.facts = dict(facts)
        self.session.add(outcome)
        flag_modified(outcome, "facts")

    def _mail_requester(self, outcome: Outcome, *, label: str, lines: list[str], communication_type: str) -> None:
        if not outcome.requester_email:
            return
        name = resolve_requester_name(self.session, outcome=outcome)
        body = (
            f"{format_outbound_greeting(name)}\n\n"
            + "\n\n".join(line for line in lines if line)
            + f"\n\nCase: {outcome.case_reference}"
        )
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=communication_type,
            body=body,
            recipients=[outcome.requester_email],
            action_label=label,
            subject_hint=outcome.summary or label.title(),
            suppress_fingerprint=f"admin_cmd:{self.event_id}:requester",
        )

    def _ack_admin(self, outcome: Outcome, cmd: dict, result: dict) -> None:
        applied = bool(result.get("applied"))
        understood = cmd.get("understood_as") or cmd["action"].replace("_", " ").title()
        if applied:
            lines = [f"Done — {result.get('summary') or understood}"]
        else:
            lines = [
                f"Not done — {result.get('summary') or 'I could not act on that.'}",
                f"I read your reply as: {understood}",
            ]
        if cmd.get("fact_updates"):
            lines.append("Changed: " + ", ".join(f"{k.replace('_', ' ')} → {v}" for k, v in cmd["fact_updates"].items()))
        if result.get("next"):
            lines.append(result["next"])
        if not applied:
            lines.append('Reply again in plain words, e.g. "approve", "book F2-R3" or "make it 20 people".')
        lines += ["", f"Case: {outcome.case_reference}", ""]
        self.comms.send_case_update(
            outcome=outcome,
            communication_type="INFORMATION_ONLY",
            body="\n".join(lines),
            recipients=[self.admin_email],
            action_label="OPS DONE" if applied else "OPS NOT APPLIED",
            subject_hint=f"{cmd['action']}: {result.get('summary') or ''}"[:90],
            suppress_fingerprint=f"admin_cmd:{self.event_id}:ack",
        )

    def _record(self, outcome: Outcome, cmd: dict, result: dict) -> None:
        facts = dict(outcome.facts or {})
        history = list(facts.get("admin_commands") or [])
        history.append(
            {
                "at": utcnow().isoformat(),
                "event_id": self.event_id,
                "by": self.admin_email,
                "action": cmd["action"],
                "raw": (cmd.get("raw") or "")[:300],
                "understood_as": cmd.get("understood_as"),
                "confidence": cmd.get("confidence"),
                "path": cmd.get("path"),
                "fact_updates": cmd.get("fact_updates") or {},
                "applied": bool(result.get("applied")),
                "summary": result.get("summary"),
            }
        )
        facts["admin_commands"] = history[-30:]
        self._save(outcome, facts)
        self.audit.record(
            tenant_id=self.tenant_id,
            actor=self.actor,
            action=AuditAction.HUMAN_OVERRIDE,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={
                "via": "admin_mail",
                "command": cmd["action"],
                "raw": (cmd.get("raw") or "")[:300],
                "applied": bool(result.get("applied")),
                "summary": result.get("summary"),
            },
            correlation_id=outcome.outcome_id,
        )
