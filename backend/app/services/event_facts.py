"""Event-level facts the room flow needs beyond the slot: kind, layout, multi-day dates, trainers, travel, cost centre."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Optional

_WORD_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a": 1, "an": 1,
}
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

_TRAINING_RE = re.compile(r"\b(training|bootcamp|induction|classroom|masterclass|course)\b", re.I)
_EXTERNAL_TYPE_RE = re.compile(r"\b(client|customer|partner|vendor|external|guest|investor|board\s+meeting|interview)\b", re.I)
_LAYOUTS = (
    ("classroom", re.compile(r"\bclass\s*room\b", re.I)),
    ("u_shape", re.compile(r"\bu[\s-]?shape[d]?\b", re.I)),
    ("theatre", re.compile(r"\btheat(?:re|er)(?:\s+style)?\b|\bauditorium\s+style\b", re.I)),
    ("boardroom", re.compile(r"\bboard\s*room(?:\s+style)?\b", re.I)),
    ("cluster", re.compile(r"\bcluster(?:s)?\b|\bpods?\b", re.I)),
)
LAYOUT_LABELS = {
    "classroom": "classroom",
    "u_shape": "U-shape",
    "theatre": "theatre",
    "boardroom": "boardroom",
    "cluster": "cluster",
}
_DAY_RANGE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:and|&|-|–|to)\s*(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(" + "|".join(_MONTHS) + r")[a-z]*\.?,?\s*(\d{4})?",
    re.I,
)
_N_DAY_RE = re.compile(r"\b(\d|two|three|four|five)[\s-]+days?\b", re.I)
_TRAINER_RE = re.compile(r"\b(?:the\s+|a\s+|one\s+|an?\s+external\s+)?(trainers?|facilitators?|speakers?)\b", re.I)
_TRAINER_COUNT_RE = re.compile(r"\b(\d|one|two|three)\s+(?:external\s+)?(?:trainers?|facilitators?)\b", re.I)
_TRAVEL_RE = re.compile(
    r"\b(travel(?:l)?ing|will\s+travel|travel\s+from|outstation|fly(?:ing)?\s+in|flights?|hotel|stay|"
    r"airport|station|pick\s*-?\s*up|drop|transfers?|cab)\b",
    re.I,
)
_TRAVELLER_COUNT_RE = re.compile(
    r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:employees?|people|participants?|colleagues?|members?|of\s+them)"
    r"\s+(?:will\s+|are\s+|would\s+)?(?:be\s+)?(?:travel(?:l)?ing|travel|flying|coming\s+from|outstation)",
    re.I,
)
_FROM_CITY_RE = re.compile(r"\b(?:from|travel(?:l)?ing\s+from|coming\s+from)\s+([A-Z][a-zA-Z]+(?:\s+(?:and|&)\s+[A-Z][a-zA-Z]+)?)")
_HOTEL_RE = re.compile(r"\b(hotel|stay|accommodation|overnight)\b", re.I)
_FLIGHT_RE = re.compile(r"\b(flights?|fly(?:ing)?|air\s*ticket|airfare)\b", re.I)
_TRANSFER_RE = re.compile(r"\b(airport|station|transfers?|pick\s*-?\s*up|drop|cab)\b", re.I)
_COST_CENTRE_RE = re.compile(r"\bcost[\s-]*cent(?:re|er)\s*(?:code|no\.?|number|is|:|-)?\s*[:\-]?\s*([A-Z]{1,5}[-\s]?\d{2,6})\b", re.I)
_APPROVER_RE = re.compile(r"\bapprov(?:er|ing\s+(?:manager|head))\s*(?:is|:|-)?\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)")
_RECORDING_NO_RE = re.compile(r"\b(no\s+recording|recording\s+(?:is\s+)?not\s+(?:required|needed))\b", re.I)
_RECORDING_YES_RE = re.compile(r"\b(record(?:ing)?\s+(?:is\s+)?(?:required|needed)|please\s+record|need\s+(?:a\s+)?recording)\b", re.I)


def _num(token: str) -> int:
    token = (token or "").strip().lower()
    return int(token) if token.isdigit() else _WORD_NUM.get(token, 0)


def _parse_day(value: Any) -> Optional[date]:
    from app.services.room_booking import parse_meeting_date

    return parse_meeting_date(value) if value else None


def event_kind(facts: dict[str, Any]) -> str:
    """training | external | internal — drives buffers, layout default and the task plan."""
    from app.services.meeting_room import external_visitor_count

    kind = str(facts.get("event_kind") or "").lower()
    if kind in {"training", "external", "internal"}:
        return kind
    mt = str(facts.get("meeting_type") or "")
    if _TRAINING_RE.search(mt) or facts.get("layout") == "classroom":
        return "training"
    if external_visitor_count(facts) > 0 or _EXTERNAL_TYPE_RE.search(mt):
        return "external"
    return "internal"


def event_dates(facts: dict[str, Any]) -> list[str]:
    return [d for d in facts.get("event_dates") or [] if d]


def is_multi_day(facts: dict[str, Any]) -> bool:
    return len(event_dates(facts)) > 1


def day_count(facts: dict[str, Any]) -> int:
    return max(1, len(event_dates(facts)))


def extra_day_facts(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Copies of the facts pointed at day 2..N (same times, same buffers)."""
    return [{**facts, "date": d} for d in event_dates(facts)[1:]]


def trainer_count(facts: dict[str, Any]) -> int:
    try:
        return int(facts.get("trainers") or 0)
    except (TypeError, ValueError):
        return 0


def travel_needed(facts: dict[str, Any]) -> bool:
    return bool(facts.get("travel_needed")) and int(facts.get("travellers") or 0) > 0


def _layout(text: str) -> Optional[str]:
    for code, rx in _LAYOUTS:
        if rx.search(text):
            return code
    return None


def _date_range(text: str) -> list[str]:
    m = _DAY_RANGE_RE.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        year = m.group(4) or ""
        first = _parse_day(f"{a} {m.group(3)} {year}".strip())
        if first and 1 <= b - a <= 6:
            return [(first + timedelta(days=i)).isoformat() for i in range(b - a + 1)]
    return []


def enrich_event_facts(facts: dict[str, Any], text: str) -> dict[str, Any]:
    """Read event facts from the latest mail text; never erase what an earlier mail established."""
    out = dict(facts or {})
    text = text or ""

    layout = _layout(text)
    if layout:
        out["layout"] = layout

    if not out.get("event_kind") and re.search(r"\b(training|bootcamp|induction)\b", text, re.I):
        out["event_kind"] = "training"
    if event_kind(out) == "training" and not out.get("layout"):
        out["layout"] = "classroom"
        out.setdefault("layout_assumed", True)

    dates = _date_range(text)
    if not dates:
        m = _N_DAY_RE.search(text)
        days = _num(m.group(1)) if m else 0
        first = _parse_day(out.get("date"))
        if days > 1 and first and not event_dates(out):
            dates = [(first + timedelta(days=i)).isoformat() for i in range(days)]
    if dates:
        out["event_dates"] = dates
        out["date"] = dates[0]
    elif event_dates(out):
        # A new single date that is not one of the event days means the requester moved the event
        current = _parse_day(out.get("date"))
        if current and current.isoformat() not in event_dates(out):
            out.pop("event_dates", None)
        elif current:
            out["date"] = event_dates(out)[0]

    m = _TRAINER_COUNT_RE.search(text)
    if m:
        out["trainers"] = _num(m.group(1))
    elif event_kind(out) == "training" and _TRAINER_RE.search(text) and not out.get("trainers"):
        out["trainers"] = 1

    if _TRAVEL_RE.search(text):
        count = 0
        m = _TRAVELLER_COUNT_RE.search(text)
        if m:
            count = _num(m.group(1))
        elif trainer_count(out) and re.search(r"\btrainer\b[^.]{0,60}\b(from|travel|hotel|fly|airport)\b", text, re.I):
            count = trainer_count(out)
        if count:
            out["travel_needed"] = True
            out["travellers"] = count
            city = _FROM_CITY_RE.search(text)
            if city:
                out["travel_from"] = city.group(1)
            out["travel_hotel"] = bool(_HOTEL_RE.search(text)) or bool(out.get("travel_hotel"))
            out["travel_flight"] = bool(_FLIGHT_RE.search(text)) or bool(out.get("travel_flight")) or out["travel_hotel"]
            out["travel_transfer"] = bool(_TRANSFER_RE.search(text)) or bool(out.get("travel_transfer")) or out["travel_hotel"]

    m = _COST_CENTRE_RE.search(text)
    if m:
        out["cost_centre"] = re.sub(r"\s+", "-", m.group(1).upper())
    m = _APPROVER_RE.search(text)
    if m:
        out["cost_approver_name"] = m.group(1).strip()

    if _RECORDING_NO_RE.search(text):
        out["recording"] = "no"
    elif _RECORDING_YES_RE.search(text):
        out["recording"] = "yes"
    return out


def buffer_kind(facts: dict[str, Any]) -> str:
    return event_kind(facts)


def event_extra_questions(facts: dict[str, Any], *, chargeable: bool = False) -> list[str]:
    """Non-blocking questions asked alongside the blocking ones in the same first mail."""
    qs: list[str] = []
    if chargeable and not facts.get("cost_centre"):
        qs.append("Cost centre and approving department head (for the chargeable items).")
    if travel_needed(facts) and not facts.get("traveller_details"):
        qs.append("Names and arrival/departure details of the travelling participants.")
    if event_kind(facts) == "training":
        if trainer_count(facts) and not facts.get("trainer_details"):
            qs.append("Trainer name, phone and travel itinerary.")
        if not facts.get("recording"):
            qs.append("Whether recording is required.")
        if not facts.get("attendance_capture"):
            qs.append("Whether attendance capture is required.")
    elif not facts.get("recording") and str(facts.get("hybrid_av") or "").lower() not in {"", "no", "none"}:
        qs.append("Whether recording is required.")
    return qs


def layout_label(facts: dict[str, Any]) -> str:
    return LAYOUT_LABELS.get(str(facts.get("layout") or ""), "")
