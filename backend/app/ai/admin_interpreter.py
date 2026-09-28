"""Gemini reads an ops-mailbox reply the way a human coordinator would."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.meeting import REQUIREMENT_FIELDS

logger = get_logger(__name__)

ADMIN_ACTIONS = (
    "APPROVE",
    "REJECT",
    "BOOK",
    "CHOOSE_ALTERNATIVE",
    "UPDATE_FACTS",
    "MESSAGE_REQUESTER",
    "HOLD",
    "CANCEL",
    "NONE",
)
ALTERNATIVE_CODES = ("LARGER_VENUE", "SPLIT_ROOMS", "DIFFERENT_TIME", "REDUCE_HEADCOUNT")

ADMIN_SYSTEM_INSTRUCTION = """
You are the operations brain of a workplace meeting-room desk. An ops admin has replied BY EMAIL
to a case briefing. Read their reply like an experienced coordinator reads a colleague's note —
any wording, typos, Hinglish, one word or a paragraph, several instructions in one line.

You get:
- admin_typed: ONLY what the admin wrote now (the quoted briefing is removed).
- briefing_they_replied_to: the ops mail they are answering (context for "approve", "yes", "do it").
- case: stage, facts on file, requester choice, pending approvals, proposed/booked room,
  no-room alternatives, open special requests, the requester's latest message.
- rooms_in_inventory: rooms the system can book (name, capacity, status).

Decide what the admin wants done. Return JSON only:
{
  "action": one of APPROVE | REJECT | BOOK | CHOOSE_ALTERNATIVE | UPDATE_FACTS | MESSAGE_REQUESTER | HOLD | CANCEL | NONE,
  "room": exact inventory room name, or the off-site venue name they gave, else null,
  "rooms": list of room names when they want the group split across several rooms, else [],
  "choice_code": LARGER_VENUE | SPLIT_ROOMS | DIFFERENT_TIME | REDUCE_HEADCOUNT | null,
  "fact_updates": { requirement field -> new value } for anything they changed (headcount, date, time, location…), else {},
  "reason": why they rejected / held, in their words, else null,
  "message_to_requester": text the admin wants the requester to see (rewrite politely in first-person plural
      "we", keep every concrete detail — dates, venues, names), else null,
  "understood_as": one plain-English line of what you will do, e.g. "Approve the requester's larger-venue choice",
  "confidence": 0.0-1.0,
  "needs_clarification": true if the instruction is ambiguous or contradicts the case,
  "clarification_question": short question back to the admin when needs_clarification
}

How to decide:
- "approve / ok / go ahead / haan kar do / fine / 👍" → APPROVE whatever the briefing asked them to decide
  (pending approval, requester's alternative, or the proposed room).
- "no / reject / not possible / budget nahi hai" → REJECT with reason.
- Naming a room or venue to use ("put them in F2-R2", "go with Hyatt ballroom", "book the auditorium") → BOOK.
  Match inventory names loosely (f2 r2 → F2-R2). Off-site names are allowed.
  Prefer rooms marked free_for_this_meeting; if they name a busy one, still return it (the system will refuse and tell them).
  "put them in F2-R1 and F2-R2" → BOOK with rooms ["Meeting Room F2-R1", "Huddle Room F2-R2"].
  Naming a room when the case is ALREADY booked means move the booking → BOOK.
- Picking an option for a no-room case ("split it", "try another day", "escalate") → CHOOSE_ALTERNATIVE.
- Changing requirements ("make it 25 people", "move to 3pm", "friday instead") → UPDATE_FACTS with fact_updates.
  If they change facts AND say go ahead, still UPDATE_FACTS (the system re-searches and proposes).
- Only wants to tell the requester something → MESSAGE_REQUESTER.
- "wait / hold / checking with finance / will revert" → HOLD with reason.
- "cancel this / close the case / meeting is off / drop it" → CANCEL with reason (frees the room, tells the requester).
  Rejecting one approval is REJECT, not CANCEL.
- Changes after a room is already booked (new headcount/time) → UPDATE_FACTS; the system re-checks the booking.
- Nothing actionable (thanks, signature only) → NONE.
- Put any extra line the admin wants passed on into message_to_requester, whatever the action.
- Never invent rooms, dates or approvals the admin did not say. If unsure, needs_clarification=true.
"""


class AdminInterpreter(Protocol):
    def interpret(self, payload: dict) -> tuple[dict, dict]: ...


class GeminiAdminInterpreter:
    def __init__(self, provider=None):
        from app.ai.gemini import GeminiProvider

        self.provider = provider or GeminiProvider()

    def interpret(self, payload: dict) -> tuple[dict, dict]:
        return self.provider.generate_json(
            system_instruction=ADMIN_SYSTEM_INSTRUCTION,
            payload=payload,
            temperature=0.1,
        )


def default_admin_interpreter() -> Optional[AdminInterpreter]:
    settings = get_settings()
    if settings.gemini_api_key or settings.gemini_api_key_secondary:
        return GeminiAdminInterpreter()
    return None


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_admin_decision(data: dict) -> dict[str, Any]:
    """Coerce model output into the command shape the handler executes."""
    action = str(data.get("action") or "NONE").strip().upper().replace(" ", "_")
    if action not in ADMIN_ACTIONS:
        action = "NONE"
    choice = _clean_str(data.get("choice_code"))
    choice = choice.upper().replace(" ", "_") if choice else None
    if choice not in ALTERNATIVE_CODES:
        choice = None
    updates_raw = data.get("fact_updates") if isinstance(data.get("fact_updates"), dict) else {}
    updates = {
        k: v
        for k, v in updates_raw.items()
        if k in REQUIREMENT_FIELDS and v not in (None, "")
    }
    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    rooms_raw = data.get("rooms") if isinstance(data.get("rooms"), list) else []
    rooms = [r for r in (_clean_str(x) for x in rooms_raw) if r]
    return {
        "action": action,
        "room": _clean_str(data.get("room")),
        "rooms": rooms if len(rooms) > 1 else [],
        "choice_code": choice,
        "fact_updates": updates,
        "reason": _clean_str(data.get("reason")),
        "message_to_requester": _clean_str(data.get("message_to_requester")),
        "understood_as": _clean_str(data.get("understood_as")) or action.replace("_", " ").title(),
        "confidence": max(0.0, min(1.0, confidence)),
        "needs_clarification": bool(data.get("needs_clarification")),
        "clarification_question": _clean_str(data.get("clarification_question")),
    }
