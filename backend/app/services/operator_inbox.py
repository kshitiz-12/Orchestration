"""Operator decision inbox — one source of truth for KPIs and /reviews."""

from __future__ import annotations

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session, select

from app.models.intake import AIDecision, HumanReviewItem, RawEmailEvent
from app.models.outcome import Approval, Outcome

OPEN_OUTCOME_STATUSES = frozenset(
    {"ACTIVE", "AT_RISK", "BLOCKED", "PARTIALLY_READY", "VALIDATING"}
)


def _dump(obj):
    if obj is None:
        return None
    return jsonable_encoder(obj)


def _created_at_key(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def list_operator_inbox(session: Session, tenant_id: str, status: str = "PENDING") -> list[dict]:
    """Human reviews + pending approvals on open cases + room proposals to confirm."""
    wanted = (status or "PENDING").strip().upper()
    items: list[dict] = []

    rows = session.exec(
        select(HumanReviewItem)
        .where(HumanReviewItem.tenant_id == tenant_id)
        .order_by(HumanReviewItem.created_at.desc())  # type: ignore
    ).all()
    for row in rows:
        if str(row.status or "").upper() != wanted:
            continue
        event = session.get(RawEmailEvent, row.event_id)
        decision = session.get(AIDecision, row.ai_decision_id) if row.ai_decision_id else None
        items.append(
            {
                "kind": "review",
                "review": _dump(row),
                "email": _dump(event),
                "ai_decision": _dump(decision),
                "created_at": _created_at_key(row.created_at),
            }
        )

    if wanted == "PENDING":
        approvals = session.exec(
            select(Approval).where(Approval.tenant_id == tenant_id, Approval.decision == "PENDING")
        ).all()
        for approval in approvals:
            outcome = session.get(Outcome, approval.outcome_id) if approval.outcome_id else None
            if not outcome or outcome.status not in OPEN_OUTCOME_STATUSES:
                continue
            items.append(
                {
                    "kind": "approval",
                    "approval": _dump(approval),
                    "outcome": {
                        "outcome_id": outcome.outcome_id,
                        "case_reference": outcome.case_reference,
                        "title": outcome.title,
                        "requester_email": outcome.requester_email,
                        "status": outcome.status,
                    },
                    "created_at": _created_at_key(approval.created_at),
                }
            )

        meetings = session.exec(
            select(Outcome).where(
                Outcome.tenant_id == tenant_id,
                Outcome.template_code == "MEETING_ROOM",
                Outcome.status.in_(list(OPEN_OUTCOME_STATUSES)),  # type: ignore
            )
        ).all()
        for outcome in meetings:
            facts = outcome.facts or {}
            if facts.get("pending_confirmation") and facts.get("proposed_room") and not facts.get("booked_room"):
                room = facts.get("proposed_room") or {}
                items.append(
                    {
                        "kind": "confirm_booking",
                        "outcome": {
                            "outcome_id": outcome.outcome_id,
                            "case_reference": outcome.case_reference,
                            "title": outcome.title,
                            "requester_email": outcome.requester_email,
                            "status": outcome.status,
                        },
                        "proposed_room": room.get("name") if isinstance(room, dict) else room,
                        "created_at": _created_at_key(outcome.updated_at or outcome.created_at),
                    }
                )

    items.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    return items


def inbox_kpi_counts(session: Session, tenant_id: str) -> dict[str, int]:
    inbox = list_operator_inbox(session, tenant_id, status="PENDING")
    human_reviews = sum(1 for row in inbox if row.get("kind") == "review")
    pending_approvals = sum(1 for row in inbox if row.get("kind") == "approval")
    pending_confirmations = sum(1 for row in inbox if row.get("kind") == "confirm_booking")
    return {
        "human_reviews": human_reviews,
        "pending_approvals": pending_approvals,
        "pending_confirmations": pending_confirmations,
        "waiting_on_you": human_reviews + pending_approvals + pending_confirmations,
    }
