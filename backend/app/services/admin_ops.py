"""Admin ops mail — short case summaries; admin can act on any of them by replying."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.outcome import Outcome
from app.services.communication import CommunicationService
from app.services.meeting_room import (
    _FIELD_LABELS,
    catering_needed,
    external_visitor_count,
    guest_vehicle_count,
    hybrid_needed,
    meeting_room_gaps,
    presentation_needed,
    seats_needed,
)

logger = get_logger(__name__)

# update = status packet; decision = needs ops follow-through (still fully actionable)
NotifyKind = Literal["update", "decision"]


def admin_ops_email() -> Optional[str]:
    """Dedicated ops mailbox from env. Empty = admin notify disabled."""
    raw = (get_settings().admin_ops_email or "").strip()
    if not raw:
        return None
    return raw.lower()


def _emails(raw: Optional[str]) -> list[str]:
    return [e.strip().lower() for e in re.split(r"[,;\s]+", raw or "") if "@" in e]


def backup_ops_emails() -> list[str]:
    return _emails(get_settings().admin_backup_emails)


def approver_emails(approval_type: str) -> list[str]:
    """Who decides this approval: manager for spend, finance for money movement, else ops."""
    settings = get_settings()
    kind = (approval_type or "").upper()
    if any(t in kind for t in ("INVOICE", "PAYMENT", "FINANCE", "PO_")):
        picked = _emails(settings.approval_finance_email)
    elif "SPEND" in kind or "CATERING" in kind or "MANAGER" in kind:
        picked = _emails(settings.approval_manager_email)
    else:
        picked = []
    return picked or ([admin_ops_email()] if admin_ops_email() else [])


def trusted_ops_senders() -> set[str]:
    """Mailboxes whose replies may act on cases."""
    settings = get_settings()
    out = set(backup_ops_emails())
    out.update(_emails(settings.approval_manager_email))
    out.update(_emails(settings.approval_finance_email))
    if admin_ops_email():
        out.add(admin_ops_email())
    return out


def _open_request_texts(facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in facts.get("open_requests") or []:
        text = item.get("text") if isinstance(item, dict) else str(item)
        t = (text or "").strip()
        if t and t not in out:
            out.append(t)
    return out


_GAP_LABELS = dict(_FIELD_LABELS) | {
    "preferred_time": "start time",
    "duration": "time slot",
    "end_time": "end time",
    "duration_hours": "duration",
}


def _when_line(bag: dict[str, Any]) -> str:
    from app.services.room_booking import parse_meeting_date

    day = parse_meeting_date(bag.get("date"))
    date_text = day.strftime("%a %d %b %Y") if day else str(bag.get("date") or "")
    start = bag.get("preferred_time") or bag.get("time_window")
    end = bag.get("end_time")
    time_text = f"{start}–{end}" if start and end else str(start or "")
    if not time_text and bag.get("duration_hours"):
        time_text = f"{bag['duration_hours']}h"
    place = bag.get("location_preference") or bag.get("primary_office")
    return " · ".join(p for p in (", ".join(p for p in (date_text, time_text) if p), place) if p)


def _people_line(bag: dict[str, Any]) -> str:
    attendees = bag.get("attendees")
    visitors = external_visitor_count(bag)
    if attendees in (None, "") and not visitors:
        return ""
    text = str(attendees or 0)
    if visitors:
        names = bag.get("visitor_details")
        text += f" + {visitors} visitor{'s' if visitors != 1 else ''}" + (f" ({names})" if names else "")
        text += f" → {seats_needed(bag)} seats"
    elif bag.get("external_visitors_indicated"):
        text += " + visitors (count not given yet)"
    return text


def _needs_line(bag: dict[str, Any]) -> str:
    needs: list[str] = []
    if hybrid_needed(bag):
        needs.append("video call")
    if presentation_needed(bag):
        needs.append("display")
    if catering_needed(bag):
        food = str(bag.get("catering"))
        food = "catering" if food.lower() in {"yes", "requested"} else food
        notes = [n for n in bag.get("catering_notes") or [] if n]
        if notes:
            food += f' (as asked: "{notes[-1]}")'
        needs.append(f"{food} ({bag['dietary']})" if bag.get("dietary") else food)
    access = str(bag.get("special_access") or "").strip()
    if access and access.lower() not in {"none", "n/a", "no"}:
        needs.append(f"access: {access}")
    if guest_vehicle_count(bag):
        cars = f"parking for {guest_vehicle_count(bag)}"
        needs.append(f"{cars} ({bag['vehicle_numbers']})" if bag.get("vehicle_numbers") else cars)
    conf = str(bag.get("confidentiality") or "").lower()
    if conf and conf not in {"standard", "none", "no", "normal"}:
        needs.append(f"confidential ({bag['confidentiality']})")
    return ", ".join(needs)


def _room_line(bag: dict[str, Any]) -> str:
    booked = bag.get("booked_room") if isinstance(bag.get("booked_room"), dict) else {}
    proposed = bag.get("proposed_room") if isinstance(bag.get("proposed_room"), dict) else {}
    if booked.get("name"):
        cap = f" ({booked['capacity']} seats)" if booked.get("capacity") else ""
        return f"{booked['name']}{cap} — booked"
    if proposed.get("name") and bag.get("pending_confirmation"):
        cap = f" ({proposed['capacity']} seats)" if proposed.get("capacity") else ""
        return f"{proposed['name']}{cap} — held, waiting for the requester to confirm"
    diagnosis = bag.get("no_resource_diagnosis") if isinstance(bag.get("no_resource_diagnosis"), dict) else {}
    choice = bag.get("no_resource_choice") if isinstance(bag.get("no_resource_choice"), dict) else {}
    if choice.get("label"):
        return f"none fits — requester picked: {choice['label']}"
    if diagnosis.get("line"):
        return f"none fits — {diagnosis['line']}"
    return ""


def _pending_catering_approval(bag: dict[str, Any]) -> str:
    if not bag.get("catering_approval_id") or bag.get("catering_auto_approved"):
        return ""
    if (bag.get("vendor_sla") or {}).get("status") not in (None, "PENDING_ASSIGNMENT"):
        return ""
    quote = bag.get("catering_quote") or {}
    amount = quote.get("amount_ex_tax")
    cost = f"{quote.get('currency') or 'INR'} {amount:,.0f} + tax" if isinstance(amount, (int, float)) else "cost not quoted"
    vendor = f" via {str(quote['vendor']).rstrip('.')}" if quote.get("vendor") else ""
    return f"Catering needs your approval: {cost} for {quote.get('headcount') or seats_needed(bag)} people{vendor}."


_DIET_WORD = re.compile(r"\b(?:non[\s-]?veg\w*|veg\w*|vegan|jain|halal|gluten|dairy)\b", re.I)
_COUNTED_ASK = re.compile(r"\d|\brest\b|\bfor\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b", re.I)
_VISITOR_PLACEHOLDER = re.compile(r"\d|\b(?:visitors?|guests?|people|persons?|more|additional|others?|external)\b", re.I)


def _latest_catering_ask(bag: dict[str, Any]) -> str:
    """The requester's most recent catering sentence, when it carries counts the structured field loses."""
    notes = [str(n).strip() for n in bag.get("catering_notes") or [] if str(n).strip()]
    counted = [n for n in notes if _COUNTED_ASK.search(n)]
    return counted[-1] if counted else ""


def _visitor_names_raw(value: Any) -> list[str]:
    return [p.strip() for p in re.split(r",|;|&|\band\b", str(value or "")) if p.strip()]


def _visitor_names(value: Any) -> list[str]:
    return [p for p in _visitor_names_raw(value) if not _VISITOR_PLACEHOLDER.search(p)]


def _after_dash(value: Any) -> str:
    text = str(value or "").strip()
    parts = re.split(r"\s+[—–-]\s+", text, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def _arrange_items(bag: dict[str, Any]) -> list[str]:
    items: list[str] = []
    if hybrid_needed(bag):
        how = _after_dash(bag.get("hybrid_av"))
        items.append("Video call" + (f" ({how})" if how else "") + (" + display" if presentation_needed(bag) else ""))
    elif presentation_needed(bag):
        items.append("Display / screen")
    if catering_needed(bag):
        latest = _latest_catering_ask(bag)
        if latest:
            dietary = bag.get("dietary") if bag.get("dietary") and not _DIET_WORD.search(latest) else ""
            items.append(f'Catering, as the requester asked: "{latest}"' + (f" — {dietary}" if dietary else ""))
        else:
            food = str(bag.get("catering"))
            food = "Catering" if food.lower() in {"yes", "requested"} else food[:1].upper() + food[1:]
            items.append(f"{food}" + (f" — {bag['dietary']}" if bag.get("dietary") else ""))
    visitors = external_visitor_count(bag)
    if visitors:
        raw_names = str(bag.get("visitor_details") or "").strip()
        name_list = _visitor_names(raw_names)
        named = len(name_list)
        names = raw_names if named == len(_visitor_names_raw(raw_names)) else " and ".join(name_list)
        line = f"Visitor passes for {visitors}" + (f": {names}" if names else "")
        if names and named < visitors:
            line += f" + {visitors - named} name{'s' if visitors - named > 1 else ''} to come"
        items.append(line)
    cars = guest_vehicle_count(bag)
    if cars:
        items.append(f"Parking for {cars}" + (f": {bag['vehicle_numbers']}" if bag.get("vehicle_numbers") else ""))
    access = str(bag.get("special_access") or "").strip()
    if access and access.lower() not in {"none", "n/a", "no", "required"}:
        items.append(f"Access: {access}")
    conf = str(bag.get("confidentiality") or "").lower()
    if conf and conf not in {"standard", "none", "no", "normal"}:
        items.append(f"Confidential ({bag['confidentiality']})")
    for ask in _open_request_texts(bag):
        items.append(ask[:1].upper() + ask[1:])
    return items


def _booked_briefing(outcome: Outcome, bag: dict[str, Any], *, event_title: str, detail: str, kind: NotifyKind) -> str:
    case = outcome.case_reference or outcome.outcome_id
    booked = bag.get("booked_room") or {}
    room = str(booked.get("name") or "")
    if booked.get("capacity"):
        room += f" ({booked['capacity']} seats)"
    setup = bag.get("setup_buffer_minutes")
    if setup:
        room += f", setup {setup} min before"
    lines = [f"{case} — {event_title}", ""]
    lines += [f"{label}: {value}" for label, value in (
        ("Requester", _requester_label(outcome, bag)),
        ("When", _when_line(bag)),
        ("Room", room),
        ("People", _people_line(bag)),
    ) if value]
    items = _arrange_items(bag)
    if items:
        lines += ["", "To arrange:"] + [f"- {i}" for i in items]
    if detail.strip():
        lines += ["", detail.strip()]
    lines.append("")
    if kind == "decision":
        lines.append('Reply "approve" or "reject, <reason>". To change the booking, just say so — e.g. "move to 3pm".')
    else:
        lines.append('To change anything, just reply — e.g. "move to 3pm", "make it 20 people" or "cancel".')
    return "\n".join(lines) + "\n"


def _requester_label(outcome: Outcome, bag: dict[str, Any]) -> str:
    email = outcome.requester_email or "unknown"
    name = str(bag.get("requester_name") or bag.get("requester_display_name") or "").strip()
    if name.lower() in {"there", "team", "anonymous"}:
        name = ""
    return f"{name} <{email}>" if name else email


def build_admin_briefing(
    outcome: Outcome,
    *,
    event_title: str,
    detail: str = "",
    kind: NotifyKind = "update",
    facts: Optional[dict[str, Any]] = None,
) -> tuple[str, str]:
    """Return (subject_hint, body) — a short case summary ops can read in seconds."""
    bag = dict(facts or outcome.facts or {})
    prefix = "OPS DECISION" if kind == "decision" else "OPS UPDATE"
    hint = f"{prefix}: {event_title}"[:90]
    if isinstance(bag.get("booked_room"), dict) and bag["booked_room"].get("name"):
        return hint, _booked_briefing(outcome, bag, event_title=event_title, detail=detail, kind=kind)

    case = outcome.case_reference or outcome.outcome_id
    rows = [
        ("Requester", _requester_label(outcome, bag)),
        ("When", _when_line(bag)),
        ("People", _people_line(bag)),
        ("Needs", _needs_line(bag)),
        ("Also asked", "; ".join(_open_request_texts(bag))),
        ("Room", _room_line(bag)),
    ]
    gaps = [
        _GAP_LABELS.get(g.get("field"), str(g.get("field") or "").replace("_", " ")).lower()
        for g in meeting_room_gaps(bag)
    ]
    if gaps:
        rows.append(("Waiting on requester", ", ".join(dict.fromkeys(gaps))))

    lines = [f"{case} — {event_title}"]
    if detail.strip():
        lines.append(detail.strip())
    lines.append("")
    lines.extend(f"{label}: {value}" for label, value in rows if value)
    lines.append("")
    if kind == "decision":
        lines.append(
            'Your call. Reply in plain words, e.g. "approve", "reject, no budget", '
            '"book F2-R3", "split it", or "move to 3pm".'
        )
    else:
        lines.append(
            'No action needed. To change anything, just reply — e.g. "move them to F2-R3", '
            '"make it 20 people" or "cancel".'
        )
    return hint, "\n".join(lines) + "\n"


class AdminOpsNotifier:
    """Structured case briefings to ADMIN_OPS_EMAIL. Admin can act on any mail."""

    def __init__(self, session: Session, tenant_id: str, comms: CommunicationService):
        self.session = session
        self.tenant_id = tenant_id
        self.comms = comms

    def notify(
        self,
        outcome: Outcome,
        *,
        kind: NotifyKind,
        headline: str,
        detail: str = "",
        fingerprint: str,
        facts: Optional[dict[str, Any]] = None,
        recipients: Optional[list[str]] = None,
    ) -> bool:
        """Returns True if a mail was sent. Dedupes by fingerprint."""
        primary = [e for e in (recipients or [admin_ops_email()]) if e]
        if kind == "decision":
            primary += backup_ops_emails()
        requester = (outcome.requester_email or "").strip().lower()
        to_list: list[str] = []
        for addr in primary:
            if addr == requester:
                logger.warning("admin_ops_email_matches_requester_skipped", case=outcome.case_reference, email=addr)
                continue
            if addr not in to_list:
                to_list.append(addr)
        if not to_list:
            return False
        to = ", ".join(to_list)

        bag = dict(facts or outcome.facts or {})
        history = list(bag.get("admin_ops_notices") or [])
        if any(h.get("fingerprint") == fingerprint for h in history):
            return False

        subject_hint, body = build_admin_briefing(
            outcome,
            event_title=headline,
            detail=detail,
            kind=kind,
            facts=bag,
        )
        label = "OPS DECISION" if kind == "decision" else "OPS UPDATE"
        sent = self.comms.send_case_update(
            outcome=outcome,
            communication_type="ACTION_REQUIRED" if kind == "decision" else "INFORMATION_ONLY",
            body=body,
            recipients=to_list,
            action_label=label,
            subject_hint=subject_hint,
            suppress_fingerprint=f"admin_ops:{fingerprint}",
        )
        if sent is None:
            return False

        history.append(
            {
                "fingerprint": fingerprint,
                "kind": kind,
                "headline": headline[:200],
                "message_id": getattr(sent, "message_id", None),
            }
        )
        bag["admin_ops_notices"] = history[-40:]
        bag["admin_ops_last"] = history[-1]
        outcome.facts = bag
        self.session.add(outcome)
        flag_modified(outcome, "facts")
        logger.info(
            "admin_ops_notified",
            case=outcome.case_reference,
            kind=kind,
            to=to,
            fingerprint=fingerprint,
        )
        return True

    @staticmethod
    def _all_fyi() -> bool:
        return (get_settings().admin_fyi_level or "key").strip().lower() == "all"

    def fyi_case_opened(self, outcome: Outcome, *, facts: Optional[dict] = None) -> bool:
        if not self._all_fyi():
            return False
        return self.notify(
            outcome,
            kind="update",
            headline="New meeting-room request opened",
            fingerprint=f"opened:{outcome.outcome_id}",
            facts=facts,
        )

    def fyi_awaiting_requirements(self, outcome: Outcome, *, facts: Optional[dict] = None) -> bool:
        if not self._all_fyi():
            return False
        return self.notify(
            outcome,
            kind="update",
            headline="Gathering requirements from requester",
            fingerprint=f"clarify:{outcome.outcome_id}",
            facts=facts,
        )

    def fyi_proposed(self, outcome: Outcome, *, room_name: str, facts: Optional[dict] = None) -> bool:
        if not self._all_fyi():
            return False
        return self.notify(
            outcome,
            kind="update",
            headline=f"Room offered to requester — {room_name}",
            fingerprint=f"proposed:{outcome.outcome_id}:{room_name}",
            facts=facts,
        )

    def fyi_booked(self, outcome: Outcome, *, room_name: str, facts: Optional[dict] = None) -> bool:
        bag = dict(facts or outcome.facts or {})
        approval = _pending_catering_approval(bag)
        return self.notify(
            outcome,
            kind="decision" if approval else "update",
            headline=f"Booking confirmed — {room_name}",
            detail=approval,
            fingerprint=f"booked:{outcome.outcome_id}:{room_name}",
            facts=bag,
        )

    def action_no_resource(self, outcome: Outcome, *, diagnosis: str = "", facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="decision",
            headline="No suitable room in inventory",
            detail=diagnosis
            or "Inventory could not satisfy this request. Choose larger venue / split / different time, or override.",
            fingerprint=f"no_resource:{(facts or outcome.facts or {}).get('no_resource_fingerprint') or outcome.outcome_id}",
            facts=facts,
        )

    def action_requester_choice(
        self,
        outcome: Outcome,
        *,
        choice_label: str,
        facts: Optional[dict] = None,
    ) -> bool:
        return self.notify(
            outcome,
            kind="decision",
            headline=f"Requester selected alternative — {choice_label}",
            detail="Follow through on this alternative (book off-site, split, reschedule, etc.).",
            fingerprint=f"choice:{outcome.outcome_id}:{choice_label}",
            facts=facts,
        )

    def action_needs_review(self, outcome: Outcome, *, reason: str, facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="decision",
            headline="Ops review before booking",
            detail=reason.replace("_", " "),
            fingerprint=f"ops_review:{outcome.outcome_id}:{reason}",
            facts=facts,
        )

    def action_approval(
        self,
        outcome: Outcome,
        *,
        approval_type: str,
        facts: Optional[dict] = None,
        include_admin: bool = True,
    ) -> bool:
        admin = admin_ops_email()
        recipients = approver_emails(approval_type)
        if include_admin:
            recipients += [admin] if admin else []
        else:
            recipients = [r for r in recipients if r != admin]
            if not recipients:
                return False
        return self.notify(
            outcome,
            kind="decision",
            headline=f"Approval needed — {approval_type.replace('_', ' ')}",
            fingerprint=f"approval:{outcome.outcome_id}:{approval_type}:{(facts or {}).get('catering_approval_id') or ''}",
            facts=facts,
            recipients=recipients,
        )
