"""Append-only operational ledger + query helpers for admin Q&A."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, col, select

from app.core.logging import get_logger
from app.models.ops_ledger import OpsLedgerEvent
from app.models.org import utcnow

logger = get_logger(__name__)


def record(
    session: Session,
    tenant_id: str,
    *,
    event_type: str,
    summary: str,
    actor_email: Optional[str] = None,
    actor_role: str = "system",
    department_code: Optional[str] = None,
    location_id: Optional[str] = None,
    category: Optional[str] = None,
    outcome_id: Optional[str] = None,
    case_reference: Optional[str] = None,
    amount: Optional[float] = None,
    currency: str = "INR",
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    sku_code: Optional[str] = None,
    asset_tag: Optional[str] = None,
    payload: Optional[dict] = None,
    occurred_at: Optional[datetime] = None,
) -> OpsLedgerEvent:
    row = OpsLedgerEvent(
        tenant_id=tenant_id,
        occurred_at=occurred_at or utcnow(),
        actor_email=(actor_email or "").strip().lower() or None,
        actor_role=actor_role,
        department_code=department_code,
        location_id=location_id,
        category=category,
        outcome_id=outcome_id,
        case_reference=case_reference,
        event_type=event_type,
        amount=amount,
        currency=currency or "INR",
        quantity=quantity,
        unit=unit,
        sku_code=sku_code,
        asset_tag=asset_tag,
        summary=(summary or "")[:500],
        payload=payload or {},
    )
    session.add(row)
    session.flush()
    return row


def record_from_outcome(
    session: Session,
    tenant_id: str,
    outcome: Any,
    *,
    event_type: str,
    summary: str,
    actor_email: Optional[str] = None,
    actor_role: str = "system",
    amount: Optional[float] = None,
    quantity: Optional[float] = None,
    unit: Optional[str] = None,
    sku_code: Optional[str] = None,
    asset_tag: Optional[str] = None,
    payload: Optional[dict] = None,
) -> OpsLedgerEvent:
    facts = getattr(outcome, "facts", None) or {}
    return record(
        session,
        tenant_id,
        event_type=event_type,
        summary=summary,
        actor_email=actor_email or getattr(outcome, "requester_email", None),
        actor_role=actor_role,
        department_code=facts.get("department_code"),
        location_id=facts.get("location_id"),
        category=facts.get("agent_category") or getattr(outcome, "category", None),
        outcome_id=getattr(outcome, "outcome_id", None),
        case_reference=getattr(outcome, "case_reference", None),
        amount=amount,
        quantity=quantity,
        unit=unit,
        sku_code=sku_code,
        asset_tag=asset_tag,
        payload=payload,
    )


def _window(days: int = 30, since: Optional[datetime] = None, until: Optional[datetime] = None) -> tuple[datetime, datetime]:
    end = until or utcnow()
    start = since or (end - timedelta(days=max(1, days)))
    return start, end


def query_events(
    session: Session,
    tenant_id: str,
    *,
    event_types: Optional[list[str]] = None,
    department_code: Optional[str] = None,
    location_id: Optional[str] = None,
    category: Optional[str] = None,
    case_reference: Optional[str] = None,
    days: int = 30,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
) -> list[OpsLedgerEvent]:
    start, end = _window(days, since, until)
    q = select(OpsLedgerEvent).where(
        OpsLedgerEvent.tenant_id == tenant_id,
        OpsLedgerEvent.occurred_at >= start,
        OpsLedgerEvent.occurred_at <= end,
    )
    if event_types:
        q = q.where(col(OpsLedgerEvent.event_type).in_(event_types))
    if department_code:
        q = q.where(OpsLedgerEvent.department_code == department_code)
    if location_id:
        q = q.where(OpsLedgerEvent.location_id == location_id)
    if category:
        q = q.where(OpsLedgerEvent.category == category.lower())
    if case_reference:
        q = q.where(OpsLedgerEvent.case_reference == case_reference.upper())
    q = q.order_by(col(OpsLedgerEvent.occurred_at).desc()).limit(limit)
    return list(session.exec(q).all())


def spend_summary(
    session: Session,
    tenant_id: str,
    *,
    department_code: Optional[str] = None,
    location_id: Optional[str] = None,
    category: Optional[str] = None,
    days: int = 30,
) -> dict[str, Any]:
    rows = query_events(
        session,
        tenant_id,
        event_types=["SPEND_RECORDED", "STOCK_REORDER", "STOCK_REFILL", "VENDOR_ASSIGNED", "TEAM_DONE"],
        department_code=department_code,
        location_id=location_id,
        category=category,
        days=days,
        limit=500,
    )
    total = 0.0
    with_amount = []
    for r in rows:
        if r.amount is not None:
            total += float(r.amount)
            with_amount.append(r)
    return {
        "total": round(total, 2),
        "currency": "INR",
        "rows": len(with_amount),
        "scanned": len(rows),
        "days": days,
        "department_code": department_code,
        "location_id": location_id,
        "category": category,
        "top": [
            {
                "when": r.occurred_at.isoformat(),
                "case": r.case_reference,
                "amount": r.amount,
                "summary": r.summary,
                "dept": r.department_code,
                "actor": r.actor_email,
            }
            for r in with_amount[:20]
        ],
    }


def repairs_summary(
    session: Session,
    tenant_id: str,
    *,
    location_id: Optional[str] = None,
    department_code: Optional[str] = None,
    days: int = 30,
) -> dict[str, Any]:
    cats = {"maintenance", "hvac", "electrical", "plumbing", "furniture", "pest_control", "health_safety"}
    rows = query_events(
        session,
        tenant_id,
        event_types=["TEAM_DONE", "CLOSED", "CASE_OPENED", "WORK_ORDER_SENT"],
        location_id=location_id,
        department_code=department_code,
        days=days,
        limit=300,
    )
    repairs = [r for r in rows if (r.category or "").lower() in cats]
    return {
        "count": len(repairs),
        "days": days,
        "items": [
            {
                "when": r.occurred_at.isoformat(),
                "case": r.case_reference,
                "type": r.event_type,
                "category": r.category,
                "summary": r.summary,
                "actor": r.actor_email,
                "dept": r.department_code,
            }
            for r in repairs[:40]
        ],
    }


def who_did_what(
    session: Session,
    tenant_id: str,
    *,
    case_reference: Optional[str] = None,
    department_code: Optional[str] = None,
    days: int = 14,
) -> dict[str, Any]:
    rows = query_events(
        session,
        tenant_id,
        case_reference=case_reference,
        department_code=department_code,
        days=days,
        limit=150,
    )
    return {
        "count": len(rows),
        "items": [
            {
                "when": r.occurred_at.isoformat(),
                "actor": r.actor_email,
                "role": r.actor_role,
                "type": r.event_type,
                "case": r.case_reference,
                "summary": r.summary,
                "amount": r.amount,
            }
            for r in rows
        ],
    }
