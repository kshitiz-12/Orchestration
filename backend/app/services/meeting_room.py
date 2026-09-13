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


def is_low_risk_auto_bookable(facts: dict[str, Any], score: float | None = None) -> bool:
    """Client rule: internal, no visitors/cost/exception, authorised, score >= 90."""
    if score is None:
        score = float((facts.get("recommended_room") or {}).get("score") or 0)
    if score < LOW_RISK_SCORE_THRESHOLD:
        return False
    if not is_internal_meeting(facts):
        return False
    if external_visitor_count(facts) > 0:
        return False
    if catering_needed(facts):
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
    """Blocking gaps — schedule/capacity/type/location, plus conditional visitor/parking/dietary."""
    gaps: list[dict[str, Any]] = []
    if not _answered(facts.get("attendees")):
        gaps.append(
            {
                "field": "attendees",
                "question": "How many people will attend in person?",
                "blocking": True,
            }
        )
    if not _answered(facts.get("date")):
        gaps.append(
            {
                "field": "date",
                "question": "Which date do you need the room?",
                "blocking": True,
            }
        )
    if not _answered(facts.get("preferred_time")) and not _answered(facts.get("time_window")):
        gaps.append(
            {
                "field": "preferred_time",
                "question": "What start time do you need (e.g. 2:00 PM)?",
                "blocking": True,
            }
        )
    if not _answered(facts.get("duration_hours")) and not _answered(facts.get("end_time")):
        gaps.append(
            {
                "field": "duration",
                "question": "How long do you need the room (end time or duration)?",
                "blocking": True,
            }
        )
    if not _answered(facts.get("location_preference")):
        office = facts.get("primary_office") or PRIMARY_OFFICE_HINT
        gaps.append(
            {
                "field": "location_preference",
                "question": (
                    f"Which office or building is required? "
                    f"Your primary office is {office}."
                ),
                "blocking": True,
            }
        )
    if not _answered(facts.get("meeting_type")):
        gaps.append(
            {
                "field": "meeting_type",
                "question": (
                    "Meeting type: internal, client/vendor, interview, training, confidential, or other?"
                ),
                "blocking": True,
            }
        )

    # Conditional: external visitors mentioned/count>0 without visitor details
    if external_visitor_count(facts) > 0 and not _answered(facts.get("visitor_details")):
        gaps.append(
            {
                "field": "visitor_details",
                "question": (
                    "Please share visitor names, organisations and emails "
                    f"(you indicated {external_visitor_count(facts)} external visitors)."
                ),
                "blocking": True,
            }
        )
    if guest_vehicle_count(facts) > 0 and not _answered(facts.get("vehicle_numbers")):
        gaps.append(
            {
                "field": "vehicle_numbers",
                "question": (
                    f"Please share the {guest_vehicle_count(facts)} guest vehicle number(s)."
                ),
                "blocking": True,
            }
        )
    if catering_needed(facts) and not _answered(facts.get("dietary")):
        gaps.append(
            {
                "field": "dietary",
                "question": (
                    "Please share dietary split (veg / non-veg) and any allergies for catering."
                ),
                "blocking": True,
            }
        )
    return gaps


def meeting_room_details_complete(facts: dict[str, Any]) -> bool:
    return len(meeting_room_gaps(facts)) == 0


def is_booking_confirmation(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if "should we confirm" in lowered and len(text.strip()) > 220:
        if not re.search(
            r"^\s*(yes|confirm|confirmed|go ahead|book it|please book)\b",
            text,
            re.I | re.M,
        ) and "i confirm" not in lowered:
            if not _CONFIRM_RE.search(text):
                return False
    return bool(_CONFIRM_RE.search(text))


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


def default_meeting_room_questions(facts: dict[str, Any] | None = None) -> list[str]:
    """One consolidated clarification — mandatory + likely conditionals (avoid drip Q&A)."""
    facts = facts or {}
    office = facts.get("primary_office") or PRIMARY_OFFICE_HINT
    date_line = (
        f"We can arrange a room for {facts['date']}."
        if _answered(facts.get("date"))
        else "Which date do you need the room?"
    )
    return [
        date_line,
        "1. Start time and end time, or expected duration.",
        "2. Number of participants.",
        f"3. Required office or building. Your primary office is {office}.",
        "4. Meeting type: internal, client/vendor, interview, training, confidential, or other.",
        "5. Whether external visitors will attend.",
        "6. Required facilities: video conference, display, whiteboard, microphone, or special seating.",
        "7. Whether tea, coffee or catering is required.",
        "8. Any accessibility requirement.",
        "9. Preferred room, if any.",
        'If no special service is needed, you may reply: "Internal meeting, no additional arrangements."',
    ]


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


def buffer_minutes(facts: dict[str, Any]) -> tuple[int, int]:
    """Simple internal → 10+10; visitors/catering/VC → longer buffers."""
    if catering_needed(facts) or external_visitor_count(facts) > 0 or hybrid_needed(facts):
        return 30, 15
    if is_internal_meeting(facts):
        return 10, 10
    return 15, 10


def compute_hold_window(facts: dict[str, Any]) -> dict[str, str]:
    """Setup/cleanup buffers around the meeting block."""
    start = str(facts.get("preferred_time") or facts.get("time_window") or "").strip()
    end = str(facts.get("end_time") or "").strip()
    duration = facts.get("duration_hours")
    setup_m, release_m = buffer_minutes(facts)
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
        "setup_buffer_minutes": str(setup_m),
        "release_buffer_minutes": str(release_m),
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
