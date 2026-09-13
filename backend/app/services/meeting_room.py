"""Meeting-room booking facts, gaps, and confirmation helpers."""

from __future__ import annotations

import re
from typing import Any


# Only schedule + capacity block finding a room.
# Facilities default when silent; confirm email invites additions.
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
)

# Silence = not requested (human default), shown clearly on confirm mail.
MEETING_ROOM_DEFAULTS = {
    "meeting_type": "general meeting",
    "hybrid_av": "no",
    "location_preference": "any",
    "catering": "none",
    "special_access": "none",
}

# Back-compat alias used by older imports/tests
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
    r"do\s+it"
    r")\b",
    re.I,
)

_ADDON_HINT_RE = re.compile(
    r"\b("
    r"also|additionally|instead|change|need|want|require|"
    r"catering|coffee|snacks|lunch|zoom|teams|hybrid|av|"
    r"visitor|pass|projector|whiteboard|floor|building"
    r")\b",
    re.I,
)


def _answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    text = str(value).strip()
    return bool(text)


def apply_meeting_room_defaults(facts: dict[str, Any]) -> dict[str, Any]:
    """Fill silent optional fields with human defaults (silence = no AV, etc.)."""
    out = dict(facts or {})
    for key, default in MEETING_ROOM_DEFAULTS.items():
        if not _answered(out.get(key)):
            out[key] = default
            out.setdefault("defaults_applied", [])
            if key not in out["defaults_applied"]:
                out["defaults_applied"] = list(out.get("defaults_applied") or []) + [key]
    return out


def meeting_room_gaps(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Blocking gaps — only what is required to match a room."""
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
                "question": "What start time do you need (e.g. 3:00 PM)?",
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
    return gaps


def meeting_room_details_complete(facts: dict[str, Any]) -> bool:
    return len(meeting_room_gaps(facts)) == 0


def is_booking_confirmation(text: str) -> bool:
    """True when the requester is confirming a proposed booking."""
    if not text:
        return False
    lowered = text.lower()
    # Ignore quoted system mail that contains the phrase
    if "should we confirm" in lowered and len(text.strip()) > 220:
        if not re.search(
            r"^\s*(yes|confirm|confirmed|go ahead|book it|please book)\b",
            text,
            re.I | re.M,
        ) and "i confirm" not in lowered:
            # still true if they clearly confirm somewhere
            if not _CONFIRM_RE.search(text):
                return False
    return bool(_CONFIRM_RE.search(text))


def looks_like_requirement_update(text: str) -> bool:
    """Heuristic: reply is adding/changing facilities rather than only saying hello."""
    if not text or len(text.strip()) < 2:
        return False
    return bool(_ADDON_HINT_RE.search(text))


def summarize_meeting_requirements(facts: dict[str, Any]) -> list[str]:
    """Human-readable requirement lines for confirm emails."""
    lines: list[str] = []
    if facts.get("attendees"):
        lines.append(f"Attendees (in person): {facts['attendees']}")
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
    lines.append(f"Meeting type: {facts.get('meeting_type') or MEETING_ROOM_DEFAULTS['meeting_type']}")
    lines.append(f"Hybrid / AV: {facts.get('hybrid_av') or MEETING_ROOM_DEFAULTS['hybrid_av']}")
    lines.append(
        f"Location preference: {facts.get('location_preference') or MEETING_ROOM_DEFAULTS['location_preference']}"
    )
    lines.append(f"Catering / amenities: {facts.get('catering') or MEETING_ROOM_DEFAULTS['catering']}")
    lines.append(
        f"Special access / security: {facts.get('special_access') or MEETING_ROOM_DEFAULTS['special_access']}"
    )
    defaults = facts.get("defaults_applied") or []
    if defaults:
        pretty = ", ".join(str(d).replace("_", " ") for d in defaults)
        lines.append(f"(Assumed where not mentioned: {pretty})")
    return lines


def default_meeting_room_questions() -> list[str]:
    """First-touch human questions — core first, facilities invited but not blocking."""
    return [
        "How many people will attend in person?",
        "Which date do you need, and what start/end time (or duration)?",
        "What is the meeting for (huddle, board, workshop, client pitch, etc.)? Optional if unsure.",
        "Any hybrid/AV, floor preference, catering, or visitor access needs? "
        "If you skip these, we’ll assume none and you can add them when we ask you to confirm.",
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
    )
    return "|".join(str(facts.get(k) or "") for k in keys)
