"""Grounded messy-mail signals for meeting-room extraction.

Used as a deterministic fill after Gemini (and inside the heuristic) so informal
typos / bare time ranges still become FactDelta fields when they appear in text.
Never invents values that are not grounded in the source string.
"""

from __future__ import annotations

import re
from typing import Any


def _hour_label(hour: int, *, pm: bool) -> str:
    if pm:
        display = hour if hour <= 12 else hour - 12
        if hour == 12:
            display = 12
        return f"{display}:00 PM"
    display = hour if hour != 0 else 12
    return f"{display}:00 AM"


def _to_24(label: str) -> float:
    tok = label.lower().replace(" ", "")
    ampm = "pm" if "pm" in tok else ("am" if "am" in tok else "")
    num = float(re.sub(r"[^0-9.]", "", tok.split(":")[0]) or 0)
    if ampm == "pm" and num != 12:
        num += 12
    if ampm == "am" and num == 12:
        num = 0
    return num


def parse_messy_meeting_signals(text: str) -> dict[str, Any]:
    """
    Extract high-signal messy phrases into entities.
    Safe to merge as candidates: every value is substring-grounded.
    """
    if not text:
        return {}
    raw = text
    lower = text.lower()
    out: dict[str, Any] = {}

    # "12-13 emplyees" / "10–12 employees" (newline-tolerant)
    m_people_range = re.search(
        r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+[a-z']{0,4}emp[a-z']{0,12}",
        raw,
        re.I,
    )
    if m_people_range:
        out["attendees"] = max(int(m_people_range.group(1)), int(m_people_range.group(2)))
    else:
        m_people = re.search(
            r"(\d+)\s*(?:people|attendees|persons?|pax|members|participants|heads|"
            r"emp+l?oy+e*e*'?s?|employees?|staff)",
            raw,
            re.I,
        )
        if not m_people:
            m_people = re.search(
                r"(?:for|of)\s+(\d+)\s+[a-z']{0,4}emp[a-z']{0,8}",
                raw,
                re.I,
            )
        if m_people:
            out["attendees"] = int(m_people.group(1))

    # Explicit am/pm range first
    m_range = re.search(
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*(?:to|-|–)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))",
        raw,
        re.I,
    )
    if m_range:
        out["preferred_time"] = m_range.group(1).strip()
        out["end_time"] = m_range.group(2).strip()
        try:
            out["duration_hours"] = max(
                0.5, _to_24(m_range.group(2)) - _to_24(m_range.group(1))
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        # "from 10 to 1ish" / "10 to 1ish" / "from 10 to 1"
        m_bare = re.search(
            r"(?:from\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:to|-|–)\s*(\d{1,2})(?::(\d{2}))?\s*ish\b",
            raw,
            re.I,
        )
        if not m_bare:
            m_bare = re.search(
                r"\bfrom\s+(\d{1,2})(?::(\d{2}))?\s*(?:to|-|–)\s*(\d{1,2})(?::(\d{2}))?\b",
                raw,
                re.I,
            )
        if m_bare:
            start_h = int(m_bare.group(1))
            end_h = int(m_bare.group(3))
            if end_h <= start_h:
                start_label = _hour_label(start_h, pm=False)
                end_label = _hour_label(end_h, pm=True)
                duration = float((end_h + 12) - start_h)
            else:
                # Both morning-ish business hours
                start_label = _hour_label(start_h, pm=start_h >= 13)
                if end_h >= 13:
                    end_label = _hour_label(end_h - 12 if end_h > 12 else end_h, pm=True)
                elif end_h == 12:
                    end_label = "12:00 PM"
                else:
                    end_label = _hour_label(end_h, pm=False)
                duration = max(0.5, _to_24(end_label) - _to_24(start_label))
            out["preferred_time"] = start_label
            out["end_time"] = end_label
            out["duration_hours"] = float(max(0.5, duration))

    # Additive: "1 more visitor: Priya Nair, Infosys" — do not treat as absolute count=1
    m_more = re.search(
        r"(\d+)\s+more\s+(?:external\s+)?visitors?\s*[:\-–]?\s*"
        r"([A-Za-z][A-Za-z0-9\s,.'&()-]{1,80})?",
        raw,
        re.I,
    )
    if m_more:
        out["external_visitors_add"] = int(m_more.group(1))
        extra_name = (m_more.group(2) or "").strip(" ,.")
        extra_name = re.split(
            r"\n|catering\b|parking\b|tea\b|coffee\b|display\b|rest stays\b|confirm\b",
            extra_name,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" ,.-")
        if extra_name and len(extra_name) > 1:
            out["visitor_details_append"] = extra_name[:200]

    # "2 extrnal visitors" / typo-tolerant external (absolute, not "N more")
    if not m_more:
        m_ext = re.search(
            r"(\d+)\s*(?:ext(?:er)?nal|external|extrnal|client)\s*(?:visitors?|guests?|clients?)?",
            raw,
            re.I,
        )
        if not m_ext:
            m_ext = re.search(r"(\d+)\s*(?:visitors?|guests?)\b", raw, re.I)
        if m_ext:
            out["external_visitors"] = int(m_ext.group(1))
            out["external_visitors_indicated"] = True
            out["special_access"] = "required"
        elif re.search(r"\b(?:ext(?:er)?nal|extrnal|external)\s+visitors?\b", lower):
            out["external_visitors_indicated"] = True
            out["special_access"] = "required"

        # Visitor names after "visitors ... - Name & Name"
        m_names = re.search(
            r"(?:ext(?:er)?nal|extrnal|external)?\s*visitors?\s+"
            r"(?:coming\s+also|will\s+(?:attend|join)|attend(?:ing)?|join(?:ing)?)\s*[-–:]?\s*"
            r"([A-Za-z][A-Za-z\s,.&'-]{2,120})",
            raw,
            re.I,
        )
        if m_names:
            names = m_names.group(1).strip(" ,.")
            names = re.split(
                r"\n|pls\b|please\b|tea\b|coffee\b|catering\b|display\b|no guest\b",
                names,
                maxsplit=1,
                flags=re.I,
            )[0].strip(" ,.")
            if names and len(names) > 2:
                out["visitor_details"] = names[:500]

    # Parking count: "parking needed for 1 car"
    m_park = re.search(
        r"parking\s+(?:needed\s+)?(?:for\s+)?(\d+)\s+(?:guest\s+)?(?:cars?|vehicles?)",
        raw,
        re.I,
    )
    if not m_park:
        m_park = re.search(
            r"(\d+)\s+(?:guest\s+)?(?:cars?|vehicles?)\b",
            raw,
            re.I,
        )
    if m_park:
        out["guest_vehicles"] = int(m_park.group(1))

    plates = parse_vehicle_plates(raw)
    if plates:
        out["vehicle_numbers"] = ", ".join(plates)
        out["guest_vehicles"] = out.get("guest_vehicles") or len(plates)

    return out


def parse_vehicle_plates(text: str) -> list[str]:
    """Indian-style plates with optional spaces/hyphens: HR26 AB 1234, HR26AB1234."""
    if not text:
        return []
    found = re.findall(
        r"\b([A-Z]{2}\s*-?\s*\d{1,2}\s*-?\s*[A-Z]{1,3}\s*-?\s*\d{3,4})\b",
        text.upper(),
    )
    out: list[str] = []
    for raw in found:
        norm = re.sub(r"[\s-]+", " ", raw).strip()
        if norm and norm not in out:
            out.append(norm)
    return out


_TRANSIENT_SIGNAL_KEYS = frozenset({"external_visitors_add", "visitor_details_append"})


def apply_grounded_reply_signals(
    merged: dict[str, Any],
    *,
    prior_facts: dict[str, Any] | None,
    source_text: str,
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Persist plate / additive visitor updates that extractors often leave in the
    summary or treat as a replacement count of 1.
    """
    out = dict(merged or {})
    prior = prior_facts or {}
    sig = dict(signals or parse_messy_meeting_signals(source_text))

    plates = sig.get("vehicle_numbers")
    if plates:
        out["vehicle_numbers"] = plates
        try:
            prior_cars = int(prior.get("guest_vehicles") or 0)
        except (TypeError, ValueError):
            prior_cars = 0
        try:
            cur_cars = int(out.get("guest_vehicles") or 0)
        except (TypeError, ValueError):
            cur_cars = 0
        if cur_cars <= 0:
            out["guest_vehicles"] = max(prior_cars, len(str(plates).split(",")))

    add = sig.get("external_visitors_add")
    if add:
        try:
            prior_n = int(prior.get("external_visitors") or 0)
        except (TypeError, ValueError):
            prior_n = 0
        expected = prior_n + int(add)
        try:
            current = int(out.get("external_visitors") or 0)
        except (TypeError, ValueError):
            current = 0
        if current < expected:
            out["external_visitors"] = expected
        out["external_visitors_indicated"] = True
        out["special_access"] = out.get("special_access") or "required"

    extra_name = sig.get("visitor_details_append")
    if extra_name:
        base = str(prior.get("visitor_details") or out.get("visitor_details") or "").strip()
        if extra_name.lower() not in base.lower():
            out["visitor_details"] = f"{base}; {extra_name}".strip("; ") if base else extra_name
        elif not str(out.get("visitor_details") or "").strip():
            out["visitor_details"] = base

    for key in _TRANSIENT_SIGNAL_KEYS:
        out.pop(key, None)
    return out
