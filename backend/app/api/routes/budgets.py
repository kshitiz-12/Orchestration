"""Budget master API (operational reservations; ERP remains financial SoR)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CompanyAdminDep, DashboardOpsDep, EntityDep, SessionDep, TenantDep
from app.engines.budget import BudgetEngine
from app.models.org import Budget

router = APIRouter(prefix="/budgets", tags=["budgets"])


class BudgetCreate(BaseModel):
    period: str
    category: str = "OPEX"
    cost_centre: Optional[str] = None
    entity_id: Optional[str] = None
    currency: str = "INR"
    original_amount: float = 0.0
    revised_amount: float = 0.0


class BudgetReserve(BaseModel):
    amount: float
    period: str
    category: str = "OPEX"
    cost_centre: Optional[str] = None


class BudgetCommit(BaseModel):
    amount: float
    budget_id: Optional[str] = None
    period: Optional[str] = None
    category: str = "OPEX"
    cost_centre: Optional[str] = None
    from_reservation: bool = True


class BudgetAmount(BaseModel):
    amount: float
    budget_id: str


class BudgetTransferBody(BaseModel):
    source_budget_id: str
    dest_budget_id: str
    amount: float
    justification: str
    approved_by: Optional[str] = None


def _ser(b: Budget) -> dict[str, Any]:
    ceiling = b.revised_amount if b.revised_amount else b.original_amount
    accrued = float(getattr(b, "accrued_amount", 0) or 0)
    used = (b.reserved_amount or 0) + (b.committed_amount or 0) + (b.actual_amount or 0) + accrued
    return {
        "budget_id": b.budget_id,
        "tenant_id": b.tenant_id,
        "entity_id": b.entity_id,
        "cost_centre": b.cost_centre,
        "category": b.category,
        "period": b.period,
        "currency": b.currency,
        "original_amount": b.original_amount,
        "revised_amount": b.revised_amount,
        "reserved_amount": b.reserved_amount,
        "committed_amount": b.committed_amount,
        "actual_amount": b.actual_amount,
        "accrued_amount": accrued,
        "available": float(ceiling) - float(used),
        "forecast_at_completion": float(b.actual_amount or 0)
        + float(b.committed_amount or 0)
        + accrued,
        "status": b.status,
    }


@router.get("")
def list_budgets(
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    period: Optional[str] = None,
) -> dict[str, Any]:
    stmt = select(Budget).where(Budget.tenant_id == tenant_id)
    if period:
        stmt = stmt.where(Budget.period == period)
    rows = session.exec(stmt.order_by(Budget.period)).all()
    return {"items": [_ser(r) for r in rows], "count": len(rows)}


@router.post("")
def create_budget(
    body: BudgetCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    row = Budget(
        tenant_id=tenant_id,
        entity_id=body.entity_id or entity_id,
        cost_centre=body.cost_centre,
        category=body.category.strip().upper(),
        period=body.period.strip(),
        currency=(body.currency or "INR").upper(),
        original_amount=body.original_amount,
        revised_amount=body.revised_amount or body.original_amount,
        status="ACTIVE",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser(row)


@router.post("/reserve")
def reserve_budget(
    body: BudgetReserve,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    eng = BudgetEngine(session, tenant_id, entity_id=entity_id)
    result = eng.reserve(
        amount=body.amount,
        period=body.period,
        category=body.category,
        cost_centre=body.cost_centre,
    )
    return {
        "ok": result.ok,
        "available": result.available,
        "budget_id": result.budget_id,
        "reason": result.reason,
    }


@router.post("/commit")
def commit_budget(
    body: BudgetCommit,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    eng = BudgetEngine(session, tenant_id, entity_id=entity_id)
    result = eng.commit(
        amount=body.amount,
        budget_id=body.budget_id,
        period=body.period,
        category=body.category,
        cost_centre=body.cost_centre,
        from_reservation=body.from_reservation,
    )
    return {"ok": result.ok, "available": result.available, "budget_id": result.budget_id, "reason": result.reason}


@router.post("/accrue")
def accrue_budget(
    body: BudgetAmount,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    result = BudgetEngine(session, tenant_id, entity_id=entity_id).accrue(amount=body.amount, budget_id=body.budget_id)
    return {"ok": result.ok, "available": result.available, "budget_id": result.budget_id, "reason": result.reason}


@router.post("/actual")
def post_actual(
    body: BudgetAmount,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    result = BudgetEngine(session, tenant_id, entity_id=entity_id).post_actual(
        amount=body.amount, budget_id=body.budget_id
    )
    return {"ok": result.ok, "available": result.available, "budget_id": result.budget_id, "reason": result.reason}


@router.post("/transfer")
def transfer_budget(
    body: BudgetTransferBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    xfer = BudgetEngine(session, tenant_id, entity_id=entity_id).transfer(
        source_budget_id=body.source_budget_id,
        dest_budget_id=body.dest_budget_id,
        amount=body.amount,
        justification=body.justification,
        approved_by=body.approved_by,
    )
    return {
        "transfer_id": xfer.transfer_id,
        "amount": xfer.amount,
        "source_budget_id": xfer.source_budget_id,
        "dest_budget_id": xfer.dest_budget_id,
        "status": xfer.status,
    }
