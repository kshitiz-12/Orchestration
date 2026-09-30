"""Gemini writes requester emails from the platform draft; the draft is the offline fallback."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


MAIL_WRITER_INSTRUCTION = """
You are the Admin Desk of a company writing to an employee about their request — a meeting
room, visitors, parking, a repair, IT help, supplies, travel or anything else the office admin
handles. Write the way a sharp, friendly human office admin writes — not a system. Talk about
the kind of request it actually is; never call something a room booking unless it is one.

You get:
  purpose — what this email must achieve (e.g. CONFIRM BOOKING, INFORMATION REQUIRED).
  draft — the platform's template for this email. It holds every fact and instruction
    that must reach the employee. Treat it as the source of truth for WHAT to say.
  request — the facts on file (attendees, seats needed, visitors, time, catering, …).
    defaults_applied lists fields the employee never mentioned; we filled them in.
  requester_name — first name to greet by, or null.
  must_keep — exact strings that MUST appear verbatim (case number, room names, the
    word they reply with). Copy them exactly.

Write the email body:
  • Greet by first name ("Hi Aditya,"); if requester_name is null, use "Hi,".
  • Open with the outcome in one line (the room is held, we need one detail, it's booked…).
  • Do NOT copy the draft's wording, headings or layout — it is a data dump. Rewrite from
    scratch. Never write "Label: value" lines ("Meeting type: internal meeting",
    "Location preference: …", "Hybrid / AV: yes").
  • Recap in 2–4 short "- " bullets written as natural phrases, merging related facts
    (for a room booking, e.g.):
      - Sunday 25 October, 10am–1pm at the Corporate Office
      - Meeting Room F2-R3 (seats 16) for your 12 + 2 guests, Rahul Sharma and Aman Verma
      - Screen and video-call setup for your remote folks
      - Tea/coffee with non-veg food
    Only include what is actually on file. Never list the same thing twice. Skip obvious or
    empty things ("internal meeting", "no special access").
  • Never use words like "extracted", "assumed", "not confirmed", "fields", "provenance",
    "fact", "system", stage codes, scores or internal ids.
  • Things from defaults_applied (and the draft's "I've set these for you" list) were not
    asked for — never present them as their request. Mention the ones that change what they
    get in one light line ("I've kept it as a standard meeting without video-conferencing —
    tell me if you need either."). Skip trivial ones (no parking, no special access).
  • End with exactly what they should do next, keeping the reply word(s) from the draft
    (e.g. reply "confirm"), and any deadline in the draft (e.g. room held 24 hours).
  • request.catering_in_their_words holds the employee's own food/drink asks, oldest first
    (a later one overrides an earlier one on the same item). Recap catering from these and
    keep every count and split ("2 tea, rest coffee; 6 non-veg, rest veg").
  • Write the date from request.date_exact (e.g. "Sunday 25 October"). Never work out a
    weekday yourself.
  • Never invent anything: no rooms, times, prices, people, promises or policies that are
    not in the draft or request.
  • What they asked for is not what the room has. If the draft says the room lacks
    something (e.g. "no built-in video-call setup") or explains why it's bigger than
    needed, keep that point in one plain sentence and never claim the missing feature. If the draft asks questions, ask all of them, clearly.
  • Plain text only (no markdown headings, no bold, no tables). Under ~170 words unless the
    draft carries more questions than that allows.
  • Sign off with the signature given.

Return JSON: {"body": "<the full email body>"}
""".strip()


_REQUEST_KEYS = (
    "attendees",
    "external_visitors",
    "visitor_details",
    "visitors_counted_in_attendees",
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
    "special_access",
    "guest_vehicles",
    "vehicle_numbers",
    "confidentiality",
)


def _enabled() -> bool:
    settings = get_settings()
    if not settings.ai_mail_writer:
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return bool(settings.gemini_api_key or settings.gemini_api_key_secondary)


def request_view(facts: dict[str, Any]) -> dict[str, Any]:
    from app.services.meeting_room import seats_needed

    from app.services.room_booking import parse_meeting_date

    out: dict[str, Any] = {k: facts.get(k) for k in _REQUEST_KEYS if facts.get(k) not in (None, "")}
    day = parse_meeting_date(facts.get("date"))
    if day:
        out["date_exact"] = day.strftime("%A %d %B %Y")
    seats = seats_needed(facts)
    if seats:
        out["seats_needed_in_room"] = seats
    notes = [n for n in facts.get("catering_notes") or [] if n]
    if notes:
        out["catering_in_their_words"] = notes
    asks = [
        (r.get("text") if isinstance(r, dict) else str(r))
        for r in (facts.get("open_requests") or [])
    ]
    if asks:
        out["other_requests"] = [a for a in asks if a]
    for key in ("proposed_room", "booked_room"):
        room = facts.get(key)
        if isinstance(room, dict) and room.get("name"):
            out[key] = {k: room.get(k) for k in ("name", "capacity") if room.get(k) is not None}
    applied = [
        (d if isinstance(d, str) else d.get("field"))
        for d in (facts.get("defaults_applied") or [])
        if d
    ]
    if applied:
        out["defaults_applied"] = [a for a in applied if a]
    return out


def must_keep_tokens(draft: str, case_reference: Optional[str], facts: dict[str, Any]) -> list[str]:
    """Strings the rewrite may not drop: case number, room names, quoted reply words."""
    tokens: list[str] = []
    if case_reference and case_reference in draft:
        tokens.append(case_reference)
    for key in ("proposed_room", "booked_room"):
        room = facts.get(key)
        if isinstance(room, dict):
            for part in [room, *(room.get("rooms") or [])]:
                name = part.get("name") if isinstance(part, dict) else None
                if name and " + " not in name and name in draft:
                    tokens.append(name)
    for word in re.findall(r'"([^"\n]{1,20})"', draft):
        if word.strip() and len(word.split()) <= 3:
            tokens.append(word.strip())
    seen: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.append(t)
    return seen


def _first_name(name: Optional[str]) -> Optional[str]:
    text = (name or "").strip()
    if not text or text.lower() in {"there", "team", "user", "unknown"} or text.lower().startswith("anonymous"):
        return None
    return text.split()[0]


def write_requester_mail(
    *,
    draft: str,
    purpose: str,
    facts: dict[str, Any],
    requester_name: Optional[str],
    case_reference: Optional[str],
    provider: Any = None,
) -> Optional[str]:
    """Return a natural rewrite of ``draft`` or None (caller sends the draft)."""
    if provider is None and not _enabled():
        return None
    must_keep = must_keep_tokens(draft, case_reference, facts)
    payload = {
        "purpose": purpose,
        "draft": draft,
        "request": request_view(facts),
        "requester_name": _first_name(requester_name),
        "must_keep": must_keep,
        "signature": get_settings().mail_signature,
    }
    try:
        if provider is None:
            from app.ai.gemini import GeminiProvider

            provider = GeminiProvider()
        data, endpoint = provider.generate_json(
            system_instruction=MAIL_WRITER_INSTRUCTION,
            payload=payload,
            temperature=0.4,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("mail_writer_failed", error=str(exc)[:300], purpose=purpose)
        return None
    body = str((data or {}).get("body") or "").strip()
    if len(body) < 40 or len(body) > 6000:
        logger.warning("mail_writer_rejected", reason="length", purpose=purpose)
        return None
    low = body.lower()
    missing = [t for t in must_keep if t.lower() not in low]
    if missing:
        logger.warning("mail_writer_rejected", reason="dropped_tokens", missing=missing, purpose=purpose)
        return None
    logger.info("mail_writer_ok", purpose=purpose, endpoint=(endpoint or {}).get("label"))
    return body
