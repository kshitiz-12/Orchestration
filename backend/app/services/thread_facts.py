"""Merge facts across emails in the same conversation (short replies)."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.ai.gemini import HeuristicProvider
from app.models.intake import Conversation, RawEmailEvent
from app.services.meeting_room import (  # noqa: F401 — re-export for existing imports
    MEETING_ROOM_REQUIRED,
    default_meeting_room_questions,
    is_booking_confirmation,
    meeting_room_details_complete,
    meeting_room_gaps,
)


def merge_thread_prior_facts(
    session: Session,
    *,
    tenant_id: str,
    conversation: Conversation,
    exclude_event_id: str | None = None,
) -> dict[str, Any]:
    """Build prior facts from conversation.facts + heuristic extraction of earlier mails."""
    facts: dict[str, Any] = dict(conversation.facts or {})
    rows = session.exec(
        select(RawEmailEvent)
        .where(
            RawEmailEvent.tenant_id == tenant_id,
            RawEmailEvent.conversation_id == conversation.conversation_id,
        )
        .order_by(RawEmailEvent.created_at.asc())  # type: ignore[attr-defined]
    ).all()
    heuristic = HeuristicProvider()
    for row in rows:
        if exclude_event_id and row.event_id == exclude_event_id:
            continue
        body = (row.body_for_ai or row.body_text or "").strip()
        if not body:
            continue
        extracted = heuristic.extract(
            subject=row.subject or conversation.subject or "",
            body=body,
            prior_facts=facts,
        )
        for key, value in (extracted.entities or {}).items():
            if value is not None and value != "":
                facts[key] = value
    # Drop non-fact noise
    facts.pop("issues", None)
    return facts
