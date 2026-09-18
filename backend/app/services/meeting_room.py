"""Meeting-room booking facts, gaps, scoring, and confirmation helpers."""

from __future__ import annotations

import re
from typing import Any, Optional


MEETING_ROOM_CORE = (
    "attendees",
    "date",
    "preferred_time",
    "duration",
)

MEETING_ROOM_OPTIONAL = (
    "meeting_type",
    "hybrid_av",
    "location_preference",
    "catering",
    "special_access",
    "presentation_display",
    "guest_vehicles",
    "external_visitors",
    "confidentiality",
)

# Silent defaults for optional fields only — never invent schedule/type/location.
MEETING_ROOM_DEFAULTS = {
    "hybrid_av": "no",
    "catering": "none",
    "special_access": "none",
    "presentation_display": "no",
    "guest_vehicles": 0,
    "external_visitors": 0,
    "confidentiality": "standard",
}

PRIMARY_OFFICE_HINT = "Corporate Office, Gurugram"
VC_POLICY_CODE = "MP-INT-006"
LOW_RISK_SCORE_THRESHOLD = 90.0

_INTERNAL_TYPE_RE = re.compile(
    r"\b(internal|finance|huddle|team\s+meeting|standup|stand-up)\b",
    re.I,
)
_SHORTCUT_INTERNAL_RE = re.compile(
    r"internal\s+meeting[,.]?\s+no\s+additional\s+arrangements",
    re.I,
)

MEETING_ROOM_REQUIRED = MEETING_ROOM_CORE

_NONE_LIKE = frozenset(
    {
        "none",
        "n/a",
        "na",
        "no",
        "nil",
        "nothing",
        "not needed",
        "not required",
        "no thanks",
        "no need",
        "not mentioned",
        "0",
    }
)

_CONFIRM_RE = re.compile(
    r"\b("
    r"confirm(?:\s+my\s+booking)?|"
    r"confirmed|"
    r"yes(?:\s+please)?|"
    r"please\s+(?:confirm|proceed|book|go\s+ahead)|"
    r"go\s+ahead|"
    r"book\s+it|"
    r"looks\s+good|"
    r"that\s+works|"
    r"ok(?:ay)?\s+to\s+book|"
    r"proceed|"
    r"please\s+book|"
    r"do\s+it|"
    r"satisfied"
    r")\b",
    re.I,
)

_NEW_REQUEST_RE = re.compile(
    r"\b("
    r"another\s+meeting|"
    r"new\s+meeting|"
    r"separate\s+(?:request|booking|meeting)|"
    r"also\s+need\s+a\s+(?:room|meeting)|"
    r"book\s+(?:another|a\s+new)|"
    r"different\s+(?:day|date)|"
    r"additionally\s+book"
    r")\b",
    re.I,
)

_UPDATE_CASE_RE = re.compile(r"\bupdate\s+(ROOM|MTG|EVT)-\d{4}-\d+\b", re.I)

_UPDATE_INTENT_RE = re.compile(
    r"\b(update|change|modify|for\s+the\s+same|same\s+booking|regarding\s+(?:the\s+)?(?:room|booking))\b",
    re.I,
)

_ADDON_HINT_RE = re.compile(
    r"\b("
    r"also|additionally|instead|change|need|want|require|"
    r"catering|coffee|snacks|lunch|high\s*tea|zoom|teams|hybrid|av|"
    r"visitor|pass|projector|whiteboard|floor|building|parking|vehicle"
    r")\b",
    re.I,
)

_SATISFIED_RE = re.compile(r"\b(satisfied|all\s+good|went\s+well|thank\s+you|thanks)\b", re.I)


def _answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    text = str(value).strip()
    return bool(text)


def _norm_date(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def catering_needed(facts: dict[str, Any]) -> bool:
    val = str(facts.get("catering") or "").strip().lower()
    if not val or val in _NONE_LIKE:
        return False
    return True


def hybrid_needed(facts: dict[str, Any]) -> bool:
    val = str(facts.get("hybrid_av") or "").strip().lower()
    if not val or val in _NONE_LIKE:
        return False
    return "yes" in val or "zoom" in val or "teams" in val or "video" in val or "av" in val


def presentation_needed(facts: dict[str, Any]) -> bool:
    val = str(facts.get("presentation_display") or "").strip().lower()
    if not val or val in _NONE_LIKE:
        return False
    return True


def external_visitor_count(facts: dict[str, Any]) -> int:
    try:
        return int(facts.get("external_visitors") or 0)
    except (TypeError, ValueError):
        return 0


def guest_vehicle_count(facts: dict[str, Any]) -> int:
    try:
        return int(facts.get("guest_vehicles") or 0)
    except (TypeError, ValueError):
        return 0


def apply_meeting_room_defaults(facts: dict[str, Any]) -> dict[str, Any]:
    """Fill silent optional fields with human defaults (silence = no AV, etc.)."""
    out = dict(facts or {})
    if _SHORTCUT_INTERNAL_RE.search(str(out.get("raw_reply") or out.get("shortcut_text") or "")):
        if not _answered(out.get("meeting_type")):
            out["meeting_type"] = "internal meeting"
        if not _answered(out.get("location_preference")):
            out["location_preference"] = out.get("primary_office") or PRIMARY_OFFICE_HINT
        for key in ("hybrid_av", "catering", "special_access", "presentation_display", "external_visitors"):
            if not _answered(out.get(key)):
                out[key] = MEETING_ROOM_DEFAULTS.get(key, "none" if key != "external_visitors" else 0)
        applied = list(out.get("defaults_applied") or [])
        if "shortcut_internal" not in applied:
            applied.append("shortcut_internal")
        out["defaults_applied"] = applied

    for key, default in MEETING_ROOM_DEFAULTS.items():
        if key == "hybrid_av":
            # VC handled by policy after meeting type is known — don't invent early
            continue
        if not _answered(out.get(key)):
            out[key] = default
            applied = list(out.get("defaults_applied") or [])
            if key not in applied:
                applied.append(key)
            out["defaults_applied"] = applied
    return out


def is_internal_meeting(facts: dict[str, Any]) -> bool:
    mt = str(facts.get("meeting_type") or "")
    return bool(_INTERNAL_TYPE_RE.search(mt))


def apply_internal_vc_policy(facts: dict[str, Any]) -> dict[str, Any]:
    """
    MP-INT-006: if internal meeting lists equipment and omits VC, treat VC as not required.
    Assumption is recorded and must be disclosed in confirmation.
    """
    out = dict(facts or {})
    assumptions = list(out.get("policy_assumptions") or [])
    hybrid_set = _answered(out.get("hybrid_av"))
    if hybrid_set:
        return out
    if is_internal_meeting(out):
        out["hybrid_av"] = "no"
        assumptions.append(
            {
                "code": VC_POLICY_CODE,
                "field": "hybrid_av",
                "value": "no",
                "confidence": 0.88,
                "message": (
                    "Video conferencing treated as not required under internal-meeting rule "
                    f"{VC_POLICY_CODE}; reply to correct before the change cutoff."
                ),
            }
        )
        out["policy_assumptions"] = assumptions
        applied = list(out.get("defaults_applied") or [])
        if "hybrid_av_policy" not in applied:
            applied.append("hybrid_av_policy")
        out["defaults_applied"] = applied
    elif not hybrid_set:
        out["hybrid_av"] = MEETING_ROOM_DEFAULTS["hybrid_av"]
        applied = list(out.get("defaults_applied") or [])
        if "hybrid_av" not in applied:
            applied.append("hybrid_av")
        out["defaults_applied"] = applied
    return out


def is_low_risk_auto_bookable(
    facts: dict[str, Any],
    score: float | None = None,
    *,
    policy: Any = None,
) -> bool:
    """Client rule: internal, no visitors/cost/exception, authorised, score threshold from policy."""
    from app.policy.meeting_policy import default_meeting_policy

    pol = policy or default_meeting_policy()
    if score is None:
        score = float((facts.get("recommended_room") or {}).get("score") or 0)
    if score < float(pol.auto_book_min_score):
        return False
    if pol.auto_book_require_internal and not is_internal_meeting(facts):
        return False
    if pol.auto_book_forbid_visitors and external_visitor_count(facts) > 0:
        return False
    if pol.auto_book_forbid_catering and catering_needed(facts):
        return False
    if str(facts.get("special_access") or "").strip().lower() not in {"", "none", "no", "n/a", "na"}:
        return False
    conf = str(facts.get("confidentiality") or "standard").strip().lower()
    if conf and conf not in {"standard", "normal", "none", "n/a"}:
        return False
    if facts.get("needs_ops") or facts.get("auto_book_skipped"):
        return False
    return True


def meeting_room_gaps(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Blocking gaps derived from typed snapshot (never stale checklist_missing)."""
    from app.engine.outcome_reducer import snapshot_gaps

    return snapshot_gaps(facts)


def meeting_room_details_complete(facts: dict[str, Any]) -> bool:
    return len(meeting_room_gaps(facts)) == 0


def is_booking_confirmation(text: str) -> bool:
    if not text:
        return False
    from app.services.email_utils import strip_for_ai

    # Never treat legal disclaimer "sender confirms that…" as a booking confirm
    cleaned = strip_for_ai(text)
    lowered = cleaned.lower().strip()
    if not lowered:
        return False
    # Long requirement mails that only mention "confirm" inside boilerplate
    if re.search(r"\bsender\s+confirms\s+that\b", text, re.I) and not re.search(
        r"^\s*(yes|confirm|confirmed|go ahead|book it|please book)\b",
        cleaned,
        re.I | re.M,
    ):
        # Still allow if an explicit confirm phrase appears in the cleaned body
        if not re.search(
            r"\b(i\s+confirm|yes\s*,?\s*confirm|confirm(?:\s+my\s+booking)?|confirmed|go\s+ahead|book\s+it)\b",
            lowered,
        ):
            return False
    # Bare "yes" in a long requirements reply (e.g. "yes external visitors") is not confirm
    if re.search(r"\byes\b", lowered) and not re.search(
        r"^\s*yes(?:\s+please)?\s*[.!]?$",
        lowered,
        re.I,
    ):
        # Allow yes only when clearly confirming the booking
        if not re.search(
            r"\b(yes(?:\s+please)?\s*,?\s*)?(confirm|confirmed|go ahead|book it|please book|proceed)\b",
            lowered,
            re.I,
        ):
            # Strip bare-yes matches by checking remaining confirm patterns only
            confirm_without_yes = re.compile(
                r"\b("
                r"confirm(?:\s+my\s+booking)?|"
                r"confirmed|"
                r"please\s+(?:confirm|proceed|book|go\s+ahead)|"
                r"go\s+ahead|"
                r"book\s+it|"
                r"looks\s+good|"
                r"that\s+works|"
                r"ok(?:ay)?\s+to\s+book|"
                r"proceed|"
                r"please\s+book|"
                r"do\s+it"
                r")\b",
                re.I,
            )
            return bool(confirm_without_yes.search(cleaned))
    if "should we confirm" in lowered and len(cleaned.strip()) > 220:
        if not re.search(
            r"^\s*(yes|confirm|confirmed|go ahead|book it|please book)\b",
            cleaned,
            re.I | re.M,
        ) and "i confirm" not in lowered:
            if not _CONFIRM_RE.search(cleaned):
                return False
    return bool(_CONFIRM_RE.search(cleaned))


def is_employee_satisfied(text: str) -> bool:
    return bool(text and _SATISFIED_RE.search(text))


def looks_like_requirement_update(text: str) -> bool:
    if not text or len(text.strip()) < 2:
        return False
    return bool(_ADDON_HINT_RE.search(text))


def is_new_meeting_request(
    *,
    text: str,
    new_facts: dict[str, Any],
    existing_facts: dict[str, Any],
    existing_status: str | None = None,
) -> str:
    """Return 'new' | 'update' | 'ambiguous' for same-thread replies."""
    existing_status = (existing_status or "").upper()
    if existing_status in {"CLOSED", "CANCELLED", "VERIFIED"}:
        return "new"

    if new_facts.get("new_request") is True or new_facts.get("force_new_outcome"):
        return "new"
    if new_facts.get("update_existing") is True:
        return "update"

    body = text or ""
    if _NEW_REQUEST_RE.search(body):
        return "new"
    if _UPDATE_CASE_RE.search(body):
        return "update"
    if is_booking_confirmation(body) or is_employee_satisfied(body):
        return "update"
    if _UPDATE_INTENT_RE.search(body) and not _NEW_REQUEST_RE.search(body):
        return "update"

    old_date = _norm_date(
        existing_facts.get("date")
        or (existing_facts.get("booked_room") or {}).get("date")
        or (existing_facts.get("proposed_room") or {}).get("date")
    )
    new_date = _norm_date(new_facts.get("date"))
    if old_date and new_date and old_date != new_date:
        # Distinct date on an active case → treat as new booking unless clearly an update
        if existing_facts.get("pending_confirmation") or existing_facts.get("booked_room"):
            return "new"
        return "ambiguous"

    if existing_facts.get("pending_confirmation") or existing_facts.get("booked_room"):
        if looks_like_requirement_update(body):
            return "update"
    return "update"


def summarize_meeting_requirements(facts: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if facts.get("attendees"):
        lines.append(f"Attendees (in person): {facts['attendees']}")
    if facts.get("external_visitors"):
        lines.append(f"External visitors: {facts['external_visitors']}")
    if facts.get("date"):
        lines.append(f"Date: {facts['date']}")
    start = facts.get("preferred_time") or facts.get("time_window")
    end = facts.get("end_time")
    duration = facts.get("duration_hours")
    if start and end:
        lines.append(f"Time: {start} – {end}")
    elif start and duration:
        lines.append(f"Time: {start} ({duration}h)")
    elif start:
        lines.append(f"Start: {start}")
    elif duration:
        lines.append(f"Duration: {duration}h")
    if facts.get("hold_start") or facts.get("hold_end"):
        lines.append(
            f"Room hold (incl. buffers): {facts.get('hold_start') or '—'} – {facts.get('hold_end') or '—'}"
        )
    lines.append(f"Meeting type: {facts.get('meeting_type') or 'to be confirmed'}")
    lines.append(f"Hybrid / AV: {facts.get('hybrid_av') or 'to be confirmed'}")
    lines.append(
        f"Presentation display: {facts.get('presentation_display') or MEETING_ROOM_DEFAULTS['presentation_display']}"
    )
    lines.append(f"Location preference: {facts.get('location_preference') or 'to be confirmed'}")
    lines.append(f"Catering / amenities: {facts.get('catering') or MEETING_ROOM_DEFAULTS['catering']}")
    if facts.get("dietary"):
        lines.append(f"Dietary: {facts['dietary']}")
    lines.append(
        f"Special access / security: {facts.get('special_access') or MEETING_ROOM_DEFAULTS['special_access']}"
    )
    lines.append(f"Confidentiality: {facts.get('confidentiality') or MEETING_ROOM_DEFAULTS['confidentiality']}")
    if guest_vehicle_count(facts):
        lines.append(f"Guest vehicles: {guest_vehicle_count(facts)}")
    defaults = facts.get("defaults_applied") or []
    if defaults:
        pretty = ", ".join(str(d).replace("_", " ") for d in defaults)
        lines.append(f"(Assumed where not mentioned: {pretty})")
    for assumption in facts.get("policy_assumptions") or []:
        lines.append(f"Policy: {assumption.get('message') or assumption}")
    return lines


def remaining_meeting_room_questions(facts: dict[str, Any] | None = None) -> list[str]:
    """Ask only for blocking gaps still missing — never re-ask answered facts."""
    facts = facts or {}
    gaps = meeting_room_gaps(facts)
    if gaps:
        return [g["question"] for g in gaps if g.get("question")]
    return []


def default_meeting_room_questions(facts: dict[str, Any] | None = None) -> list[str]:
    """
    Clarification questions for the requester.
    If we already know most of the request, ask ONLY remaining gaps.
    Use the full checklist only when almost nothing is known (e.g. date-only).
    """
    facts = facts or {}
    known_core = sum(
        1
        for key in ("date", "attendees", "preferred_time", "meeting_type", "location_preference")
        if _answered(facts.get(key))
    )
    # Also count duration completeness
    if facts.get("duration_hours") is not None or _answered(facts.get("end_time")):
        known_core += 1

    remaining = remaining_meeting_room_questions(facts)
    if known_core >= 2:
        # Smart path: confirm what we have, ask only what's blocking
        return remaining

    # Sparse first mail — one consolidated ask so the requester can finish in a single reply
    office = facts.get("primary_office") or PRIMARY_OFFICE_HINT
    date_line = (
        f"We already have the date as {facts['date']} — reply to change it if needed."
        if _answered(facts.get("date"))
        else "Which date do you need the room?"
    )
    questions = [date_line]
    # Skip checklist items we already know
    has_start = _answered(facts.get("preferred_time")) or _answered(facts.get("time_window"))
    has_duration = _answered(facts.get("end_time")) or facts.get("duration_hours") is not None
    if not has_start and not has_duration:
        questions.append("What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?")
    elif not has_start:
        questions.append("What start time do you need (e.g. 2:00 PM)?")
    elif not has_duration:
        questions.append("How long do you need the room (end time or duration)?")
    if not _answered(facts.get("attendees")):
        questions.append("Number of participants (in person).")
    if not _answered(facts.get("location_preference")):
        questions.append(f"Required office or building. Your primary office is {office}.")
    if not _answered(facts.get("meeting_type")):
        questions.append(
            "Meeting type: internal, client/vendor, interview, training, confidential, or other."
        )
    if facts.get("external_visitors") is None and not facts.get("external_visitors_indicated"):
        questions.append("Whether external visitors will attend (and names if yes).")
    elif facts.get("external_visitors_indicated") and not _answered(facts.get("external_visitors")):
        questions.append("How many external visitors, and their names / organisations?")
    elif (facts.get("external_visitors") or 0) > 0 and not _answered(facts.get("visitor_details")):
        questions.append("Please share visitor names, organisations and emails.")
    if not _answered(facts.get("hybrid_av")) and not _answered(facts.get("presentation_display")):
        questions.append(
            "Required facilities: video conference, display, whiteboard, microphone, or special seating."
        )
    if not _answered(facts.get("catering")):
        questions.append("Whether tea, coffee or catering is required.")
    elif catering_needed(facts) and not _answered(facts.get("dietary")):
        questions.append("Dietary split (veg / non-veg) and any allergies.")
    questions.append(
        'If no special service is needed, you may reply: "Internal meeting, no additional arrangements."'
    )
    # Prefer remaining gap questions if somehow richer
    if remaining and len(remaining) < len(questions):
        return remaining
    return questions


def requirement_fingerprint(facts: dict[str, Any]) -> str:
    keys = (
        "attendees",
        "date",
        "preferred_time",
        "end_time",
        "duration_hours",
        "meeting_type",
        "hybrid_av",
        "location_preference",
        "catering",
        "special_access",
        "presentation_display",
        "guest_vehicles",
        "external_visitors",
        "dietary",
        "confidentiality",
    )
    return "|".join(str(facts.get(k) or "") for k in keys)


def buffer_minutes(facts: dict[str, Any], *, policy: Any = None) -> tuple[int, int]:
    """Buffers from versioned policy: complex vs internal vs default."""
    from app.policy.meeting_policy import default_meeting_policy

    pol = policy or default_meeting_policy()
    if catering_needed(facts) or external_visitor_count(facts) > 0 or hybrid_needed(facts):
        return int(pol.setup_buffer_complex_minutes), int(pol.release_buffer_complex_minutes)
    if is_internal_meeting(facts):
        return int(pol.setup_buffer_internal_minutes), int(pol.release_buffer_internal_minutes)
    return 15, 10


def compute_hold_window(facts: dict[str, Any], *, policy: Any = None) -> dict[str, str]:
    """Setup/cleanup buffers around the meeting block."""
    start = str(facts.get("preferred_time") or facts.get("time_window") or "").strip()
    end = str(facts.get("end_time") or "").strip()
    duration = facts.get("duration_hours")
    setup_m, release_m = buffer_minutes(facts, policy=policy)
    hold_start = f"{start} (setup {setup_m}m earlier)" if start else "TBD"
    if end:
        hold_end = f"{end} (+{release_m}m release)"
    elif start and duration:
        hold_end = f"{start} + {duration}h (+{release_m}m release)"
    else:
        hold_end = "TBD"
    return {
        "hold_start": hold_start,
        "hold_end": hold_end,
        "setup_buffer_minutes": setup_m,
        "release_buffer_minutes": release_m,
        "policy_version": getattr(policy, "version", None) or facts.get("policy_version"),
    }


def score_meeting_room(room: Any, facts: dict[str, Any]) -> tuple[float, list[str]]:
    """Return (score 0-100, reasons)."""
    attrs = getattr(room, "attributes", None) or {}
    reasons: list[str] = []
    score = 60.0
    try:
        needed = int(facts.get("attendees") or 1)
    except (TypeError, ValueError):
        needed = 1
    try:
        capacity = int(attrs.get("capacity") or 0) or 999
    except (TypeError, ValueError):
        capacity = 999
    if capacity < needed:
        return 0.0, ["insufficient capacity"]
    overflow = capacity - needed
    if overflow <= 1:
        score += 26
        reasons.append(f"capacity {capacity} for {needed} (tight fit)")
    elif overflow <= 4:
        score += 18
        reasons.append(f"capacity {capacity} for {needed}")
    else:
        score += max(0, 12 - min(overflow, 12))
        reasons.append(f"capacity {capacity} for {needed} (oversized)")

    if hybrid_needed(facts):
        if attrs.get("video_conferencing") or attrs.get("vc"):
            score += 12
            reasons.append("VC available")
        else:
            score -= 25
            reasons.append("VC missing")
    if presentation_needed(facts):
        if attrs.get("presentation_display") or attrs.get("display"):
            score += 10
            reasons.append("display available")
        else:
            return 0.0, ["display missing"]
    if attrs.get("open_complaint") or attrs.get("open_incident"):
        score -= 25
        reasons.append("open complaint")
    pref = str(facts.get("location_preference") or "").strip().lower()
    name = (getattr(room, "name", None) or "").lower()
    floor = str(attrs.get("floor") or "").lower()
    dept = str(attrs.get("near_department") or "").lower()
    if pref and pref not in {"any", "none", "n/a"}:
        if pref in name or pref in floor or "corporate" in pref and "corporate" in floor:
            score += 8
            reasons.append("location match")
    if "finance" in str(facts.get("meeting_type") or "").lower() and "finance" in dept:
        score += 6
        reasons.append("near Finance")
    return max(0.0, min(100.0, score)), reasons
