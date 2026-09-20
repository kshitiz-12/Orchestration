"""NO_RESOURCE reply handling — choices, suppress, honest diagnosis."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional

from app.services.meeting_room import requirement_fingerprint

# Phrases that map a requester reply onto a structured alternative.
_CHOICE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "LARGER_VENUE",
        re.compile(
            r"\b(escalat\w*|larger\s+venue|off[-\s]?site|bigger\s+(?:room|venue|space)|"
            r"outside\s+(?:venue|space)|auditorium)\b",
            re.I,
        ),
    ),
    (
        "DIFFERENT_TIME",
        re.compile(
            r"\b(different\s+(?:date|time|day|slot)|another\s+(?:date|time|day)|"
            r"change\s+(?:the\s+)?(?:date|time)|reschedul\w*|later\s+slot|"
            r"try\s+(?:a\s+)?different)\b",
            re.I,
        ),
    ),
    (
        "SPLIT_ROOMS",
        re.compile(
            r"\b(split\s+(?:into\s+)?(?:two|2)\s+rooms?|two\s+rooms?|split\s+rooms?)\b",
            re.I,
        ),
    ),
    (
        "REDUCE_HEADCOUNT",
        re.compile(
            r"\b(reduce\s+(?:headcount|attendees|people|count)|fewer\s+people|"
            r"smaller\s+(?:group|headcount)|cut\s+(?:headcount|attendees))\b",
            re.I,
        ),
    ),
]


def detect_no_resource_choice(
    text: str,
    alternatives: list[dict[str, Any]] | None = None,
) -> Optional[dict[str, Any]]:
    """Map free-text reply onto one offered alternative (or None)."""
    blob = (text or "").strip()
    if len(blob) < 3:
        return None
    offered = {str(a.get("code") or "") for a in (alternatives or []) if a.get("code")}
    # Prefer matching against offered codes when present; still allow LARGER_VENUE etc.
    for code, pattern in _CHOICE_PATTERNS:
        if offered and code not in offered and code != "REVIEW_NEAR_MISS":
            # Still accept if they clearly said it — ops may have offered a subset
            pass
        if pattern.search(blob):
            label = next(
                (str(a.get("label") or code) for a in (alternatives or []) if a.get("code") == code),
                code.replace("_", " ").title(),
            )
            return {"code": code, "label": label}
    # Exact / near label match from offered alternatives
    lower = blob.lower()
    for alt in alternatives or []:
        code = str(alt.get("code") or "")
        if not code or code == "REVIEW_NEAR_MISS":
            continue
        label = str(alt.get("label") or "").strip().lower()
        if label and (label in lower or lower in label):
            return {"code": code, "label": alt.get("label") or code}
    return None


def search_relevant_changed(prior: dict[str, Any], current: dict[str, Any]) -> bool:
    """True when booking-search fields changed (re-search warranted)."""
    return requirement_fingerprint(prior) != requirement_fingerprint(current)


def open_request_delta(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> list[Any]:
    """New open_requests entries since prior snapshot."""
    prior_list = list(prior.get("open_requests") or [])
    now_list = list(current.get("open_requests") or [])
    if len(now_list) <= len(prior_list):
        # Also catch text-normalized new items
        def _norm(x: Any) -> str:
            if isinstance(x, dict):
                return str(x.get("text") or "").strip().lower()
            return str(x or "").strip().lower()

        seen = {_norm(x) for x in prior_list if _norm(x)}
        return [x for x in now_list if _norm(x) and _norm(x) not in seen]
    return now_list[len(prior_list) :]


def diagnose_no_resource(
    *,
    attendees: Any,
    max_capacity: int | None,
    zero_scores: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Honest why-no-room summary for requester + ops."""
    reason_counts: Counter[str] = Counter()
    for row in zero_scores or []:
        for r in row.get("reasons") or []:
            reason_counts[str(r)] += 1
    try:
        needed = int(attendees or 0)
    except (TypeError, ValueError):
        needed = 0
    top = [r for r, _ in reason_counts.most_common(3)]
    capacity_only = bool(top) and all("insufficient capacity" in r for r in top)
    display_block = any("display" in r.lower() for r in top)
    vc_block = any("vc" in r.lower() for r in top)

    if capacity_only and max_capacity and needed > max_capacity:
        line = (
            f"No room fits {needed} people in person "
            f"(largest inventory room holds {max_capacity})."
        )
        primary = "capacity"
    elif capacity_only and max_capacity:
        line = (
            f"No available room currently fits {needed} people "
            f"for this slot (inventory largest is {max_capacity}, but none scored as a fit)."
        )
        primary = "capacity_slot"
    elif display_block or vc_block:
        blockers = ", ".join(top[:2]) if top else "equipment mismatch"
        line = (
            f"No room matched this request for {needed or 'your'} people "
            f"(main blockers: {blockers})."
        )
        primary = "equipment"
    elif top:
        line = (
            f"No room matched this request"
            + (f" for {needed} people" if needed else "")
            + f" (main blockers: {', '.join(top[:2])})."
        )
        primary = "scored_fail"
    else:
        line = (
            f"We could not find a suitable room"
            + (f" for {needed} people" if needed else "")
            + "."
        )
        primary = "unknown"

    return {
        "primary": primary,
        "line": line,
        "top_reasons": top,
        "max_capacity": max_capacity,
        "requested_attendees": needed or None,
    }


def format_outbound_greeting(name: str) -> str:
    """Never 'Dear there' — fall back to Hello,."""
    n = (name or "").strip()
    if not n or n.lower() in {"there", "team", "user", "unknown"}:
        return "Hello,"
    return f"Dear {n},"


def short_case_subject(*, case_reference: str, action_label: str, summary: str, title: str) -> str:
    """Stage + case + short human hint — not a Gemini narrative dump."""
    summary = (summary or "").strip()
    title = (title or "").strip()
    hint = summary or title
    low = hint.lower()
    if low.startswith(
        (
            "the user ",
            "user ",
            "user is ",
            "user provided",
            "requester ",
        )
    ):
        hint = summary if summary and not summary.lower().startswith(low[:12]) else ""
    if not hint:
        hint = "Update"
    if len(hint) > 90:
        hint = hint[:87] + "…"
    return f"[{action_label}] [{case_reference}] {hint}"


def same_no_resource_fingerprint(facts: dict[str, Any], fingerprint: str | None = None) -> bool:
    """True when we already mailed no-room for this search fingerprint."""
    stored = facts.get("no_resource_fingerprint")
    now = fingerprint or requirement_fingerprint(facts)
    return bool(stored) and stored == now
