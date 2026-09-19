"""Open request ledger — persist asks that are not booking-schema fields."""

from __future__ import annotations

import re
from typing import Any

from app.domain.meeting import PLATFORM_KEYS, REQUIREMENT_FIELDS


def _answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return bool(str(value).strip())

_SKIP_ENTITY_KEYS = frozenset(REQUIREMENT_FIELDS) | frozenset(PLATFORM_KEYS) | {
    "issues",
    "raw_reply",
    "open_requests",
    "additional_requests",
    "external_visitors_add",
    "visitor_details_append",
    "booking_confirmed",
    "employee_satisfied",
    "new_request",
    "update_existing",
    "post_booking_requests",
}

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip(" .;-")


def _as_texts(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        text = value.get("text") or value.get("request") or value.get("value")
        return [str(text)] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_as_texts(item))
        return out
    return [str(value)]


def merge_open_requests(
    prior_facts: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Append unique user asks. Never drop an unmapped entity."""
    existing = [
        dict(x) if isinstance(x, dict) else {"text": str(x), "status": "noted", "source": "prior"}
        for x in list((prior_facts or {}).get("open_requests") or [])
        if x
    ]
    seen = {_norm(str(x.get("text") or "")).lower() for x in existing if _norm(str(x.get("text") or ""))}

    def add(text: str, *, source: str) -> None:
        t = _norm(text)
        if len(t) < 3:
            return
        key = t.lower()
        if key in seen:
            return
        seen.add(key)
        existing.append({"text": t[:400], "status": "noted", "source": source})

    incoming = incoming or {}
    for text in _as_texts(incoming.get("open_requests")) + _as_texts(incoming.get("additional_requests")):
        add(text, source="extracted")

    for key, value in incoming.items():
        if key in _SKIP_ENTITY_KEYS or not _answered(value):
            continue
        if isinstance(value, (dict, list)) and key not in {"open_requests", "additional_requests"}:
            # structured extras: keep a readable line
            add(f"{key.replace('_', ' ')}: {value}", source="entity")
            continue
        add(f"{key.replace('_', ' ')}: {value}", source="entity")

    return existing
