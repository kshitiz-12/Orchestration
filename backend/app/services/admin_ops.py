"""Admin ops briefing mail — structured case packets; admin can act anytime."""

from __future__ import annotations

from typing import Any, Literal, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.outcome import Outcome
from app.services.communication import CommunicationService
from app.services.meeting_room import (
    _FIELD_LABELS,
    _field_is_confirmed,
    _time_summary,
    catering_needed,
    external_visitor_count,
    guest_vehicle_count,
    meeting_room_gaps,
    unconfirmed_meeting_requirements,
)

logger = get_logger(__name__)

# update = status packet; decision = needs ops follow-through (still fully actionable)
NotifyKind = Literal["update", "decision"]

_BOOKING_KEYS = {
    "attendees",
    "date",
    "preferred_time",
    "end_time",
    "duration_hours",
    "meeting_type",
    "location_preference",
    "hybrid_av",
    "presentation_display",
    "catering",
    "dietary",
    "confidentiality",
}


def admin_ops_email() -> Optional[str]:
    """Dedicated ops mailbox from env. Empty = admin notify disabled."""
    raw = (get_settings().admin_ops_email or "").strip()
    if not raw:
        return None
    return raw.lower()


def _open_request_texts(facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in facts.get("open_requests") or []:
        text = item.get("text") if isinstance(item, dict) else str(item)
        t = (text or "").strip()
        if t and t not in out:
            out.append(t)
    return out


def _section(title: str, lines: list[str]) -> str:
    if not lines:
        return ""
    body = "\n".join(f"  • {line}" for line in lines)
    return f"{title}\n{body}\n"


def build_admin_briefing(
    outcome: Outcome,
    *,
    event_title: str,
    detail: str = "",
    kind: NotifyKind = "update",
    facts: Optional[dict[str, Any]] = None,
) -> tuple[str, str]:
    """Return (subject_hint, body) — structured ops packet."""
    bag = dict(facts or outcome.facts or {})
    case = outcome.case_reference or outcome.outcome_id
    stage = bag.get("orchestration_stage") or outcome.status or "—"
    requester = outcome.requester_email or "unknown"
    name = (bag.get("requester_display_name") or "").strip()

    # --- Meeting details (schema fields only; no open_requests here)
    meeting: list[str] = []
    if _field_is_confirmed(bag, "attendees") or bag.get("attendees") not in (None, ""):
        if bag.get("attendees") not in (None, ""):
            meeting.append(f"Attendees (in person): {bag['attendees']}")
    if bag.get("date"):
        meeting.append(f"Date: {bag['date']}")
    time_line = _time_summary(bag, confirmed_only=False)
    if time_line:
        meeting.append(time_line)
    if bag.get("meeting_type"):
        meeting.append(f"Meeting type: {bag['meeting_type']}")
    if bag.get("location_preference"):
        meeting.append(f"Location: {bag['location_preference']}")
    if bag.get("primary_office") and not bag.get("location_preference"):
        meeting.append(f"Primary office: {bag['primary_office']}")
    for key, label in _FIELD_LABELS:
        if key in {"attendees", "date", "external_visitors", "visitor_details", "guest_vehicles", "vehicle_numbers", "special_access"}:
            continue
        if key not in _BOOKING_KEYS:
            continue
        if bag.get(key) in (None, ""):
            continue
        meeting.append(f"{label}: {bag.get(key)}")

    # --- Visitors / access / parking
    access: list[str] = []
    if external_visitor_count(bag) or bag.get("external_visitors_indicated"):
        access.append(f"External visitors: {bag.get('external_visitors') or 'indicated (count TBD)'}")
    if bag.get("visitor_details"):
        access.append(f"Visitor details: {bag['visitor_details']}")
    if bag.get("special_access") and str(bag.get("special_access")).lower() not in {"none", "n/a"}:
        access.append(f"Special access: {bag['special_access']}")
    if guest_vehicle_count(bag) or bag.get("vehicle_numbers"):
        access.append(f"Guest vehicles: {bag.get('guest_vehicles') or '—'}")
    if bag.get("vehicle_numbers"):
        access.append(f"Vehicle number(s): {bag['vehicle_numbers']}")

    # --- Special / extra requests (own section)
    specials = _open_request_texts(bag)

    # --- Room / inventory
    room_lines: list[str] = []
    proposed = bag.get("proposed_room") or {}
    booked = bag.get("booked_room") or {}
    if isinstance(booked, dict) and booked.get("name"):
        room_lines.append(f"Booked: {booked.get('name')}")
        if booked.get("capacity"):
            room_lines.append(f"Capacity: {booked.get('capacity')}")
    elif isinstance(proposed, dict) and proposed.get("name"):
        room_lines.append(f"Proposed: {proposed.get('name')}")
        if proposed.get("capacity"):
            room_lines.append(f"Capacity: {proposed.get('capacity')}")
        room_lines.append("Awaiting requester confirmation")
    if bag.get("inventory_max_capacity"):
        room_lines.append(f"Largest inventory room: {bag['inventory_max_capacity']}")
    diagnosis = bag.get("no_resource_diagnosis") or {}
    if isinstance(diagnosis, dict) and diagnosis.get("line"):
        room_lines.append(f"Inventory note: {diagnosis['line']}")
    choice = bag.get("no_resource_choice") or {}
    if isinstance(choice, dict) and choice.get("label"):
        room_lines.append(f"Requester alternative: {choice.get('label')}")
    alts = bag.get("no_resource_alternatives") or []
    for alt in alts:
        code = alt.get("code") if isinstance(alt, dict) else None
        if code == "REVIEW_NEAR_MISS":
            continue
        label = (alt.get("label") if isinstance(alt, dict) else None) or code
        if label:
            room_lines.append(f"Option on file: {label}")

    # --- Still needed from requester
    gaps = meeting_room_gaps(bag)
    still = [g["question"] for g in gaps if g.get("question")]
    if not still:
        still = unconfirmed_meeting_requirements(bag)[:8]

    # --- Status
    status_lines = [f"Stage: {stage}", f"Event: {event_title}"]
    if detail.strip():
        status_lines.append(detail.strip())
    if bag.get("last_action"):
        status_lines.append(f"Last action: {bag['last_action']}")

    parts: list[str] = [
        "Hello,",
        "",
        "══════════════════════════════════",
        f"  CASE  {case}",
        "══════════════════════════════════",
        "",
        _section("STATUS", status_lines),
        _section(
            "REQUESTER",
            [
                f"Name: {name}" if name else "Name: —",
                f"Email: {requester}",
            ],
        ),
        _section("MEETING DETAILS", meeting or ["(still gathering)"]),
        _section("SPECIAL REQUESTS", specials) if specials else _section("SPECIAL REQUESTS", ["None"]),
        _section("VISITORS / ACCESS / PARKING", access) if access else "",
        _section("ROOM / INVENTORY", room_lines) if room_lines else "",
        _section("STILL NEEDED FROM REQUESTER", still) if still else "",
    ]

    if kind == "decision":
        parts.append(
            _section(
                "OPS — WHAT YOU CAN DO",
                [
                    "Approve / reject spend or policy items",
                    "Book or propose a specific room",
                    "Escalate larger venue / split rooms / change time",
                    "Override a fact (attendees, time, location, …)",
                    "Ask the requester for more detail",
                ],
            )
        )
    else:
        parts.append(
            _section(
                "OPS — YOU CAN ACT ANYTIME",
                [
                    "Override facts, propose/book a room, or message the requester",
                    "No separate approval gate on this update — intervene if needed",
                ],
            )
        )

    parts.append("Reply on this thread from the ops mailbox, or use the dashboard.")
    parts.append("")

    body = "\n".join(p for p in parts if p is not None).rstrip() + "\n"
    # Subject: short ops label + case context (never "FYI")
    prefix = "OPS DECISION" if kind == "decision" else "OPS UPDATE"
    hint = f"{prefix}: {event_title}"[:90]
    return hint, body


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
    ) -> bool:
        """Returns True if a mail was sent. Dedupes by fingerprint."""
        to = admin_ops_email()
        if not to:
            return False
        if outcome.requester_email and to == outcome.requester_email.strip().lower():
            logger.warning(
                "admin_ops_email_matches_requester_skipped",
                case=outcome.case_reference,
                email=to,
            )
            return False

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
            recipients=[to],
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

    def fyi_case_opened(self, outcome: Outcome, *, facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="update",
            headline="New meeting-room request opened",
            fingerprint=f"opened:{outcome.outcome_id}",
            facts=facts,
        )

    def fyi_awaiting_requirements(self, outcome: Outcome, *, facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="update",
            headline="Gathering requirements from requester",
            fingerprint=f"clarify:{outcome.outcome_id}",
            facts=facts,
        )

    def fyi_proposed(self, outcome: Outcome, *, room_name: str, facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="update",
            headline=f"Room proposed — {room_name}",
            detail="System proposed a fit to the requester. Confirm / change room anytime if needed.",
            fingerprint=f"proposed:{outcome.outcome_id}:{room_name}",
            facts=facts,
        )

    def fyi_booked(self, outcome: Outcome, *, room_name: str, facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="update",
            headline=f"Booking confirmed — {room_name}",
            fingerprint=f"booked:{outcome.outcome_id}:{room_name}",
            facts=facts,
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

    def action_approval(self, outcome: Outcome, *, approval_type: str, facts: Optional[dict] = None) -> bool:
        return self.notify(
            outcome,
            kind="decision",
            headline=f"Approval needed — {approval_type.replace('_', ' ')}",
            fingerprint=f"approval:{outcome.outcome_id}:{approval_type}",
            facts=facts,
        )
