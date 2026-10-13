"""P2P HTTP API — PR/PO/GRN/SES/match/ERP (M19–M21)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import DashboardOpsDep, EntityDep, FinanceDep, ProcurementDep, SessionDep, TenantDep
from app.models.finance import CostRequirement
from app.models.org import PurchaseOrder, utcnow
from app.services.p2p import P2PService
from app.models.org import StockSku

router = APIRouter(prefix="/p2p", tags=["p2p"])


class POCreate(BaseModel):
    vendor_id: str
    po_number: str
    description: str
    quantity: float
    unit_rate: float
    currency: str = "INR"
    contract_id: Optional[str] = None
    outcome_id: Optional[str] = None


class PRCreate(BaseModel):
    description: str
    estimated_amount: float
    category: str = "OPEX"
    currency: str = "INR"
    vendor_id: Optional[str] = None
    outcome_id: Optional[str] = None
    cost_centre: Optional[str] = None


class GRNCreate(BaseModel):
    po_id: str
    quantity_received: float
    received_date: Optional[str] = None
    notes: Optional[str] = None
    post_to_stock_sku_code: Optional[str] = None
    location_id: Optional[str] = None


class SESCreate(BaseModel):
    po_id: str
    quantity: float
    unit_rate: float
    vendor_id: Optional[str] = None
    outcome_id: Optional[str] = None


@router.post("/purchase-requests")
def create_pr(
    body: PRCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: ProcurementDep,
) -> dict[str, Any]:
    from app.engines.budget import BudgetEngine

    period = date.today().isoformat()[:7]  # YYYY-MM
    check = BudgetEngine(session, tenant_id, entity_id=entity_id).check(
        amount=body.estimated_amount,
        period=period,
        category=body.category,
        cost_centre=body.cost_centre,
    )
    if not check.ok:
        return {"ok": False, "reason": check.reason, "available": check.available}

    if check.budget_id:
        BudgetEngine(session, tenant_id, entity_id=entity_id).reserve(
            amount=body.estimated_amount,
            period=period,
            category=body.category,
            cost_centre=body.cost_centre,
        )

    cost = CostRequirement(
        tenant_id=tenant_id,
        entity_id=entity_id,
        outcome_id=body.outcome_id,
        vendor_id=body.vendor_id,
        budget_id=check.budget_id,
        category=body.category.upper(),
        currency=body.currency,
        estimated_amount=body.estimated_amount,
        reserved_amount=body.estimated_amount if check.budget_id else 0.0,
        status="RESERVED" if check.budget_id else "DRAFT",
        notes=body.description,
        attributes={"cost_centre": body.cost_centre, "type": "PR"},
    )
    session.add(cost)
    session.commit()
    session.refresh(cost)
    return {
        "ok": True,
        "cost_id": cost.cost_id,
        "status": cost.status,
        "budget_id": check.budget_id,
        "available": check.available,
    }


@router.post("/purchase-orders")
def create_po(
    body: POCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: ProcurementDep,
) -> dict[str, Any]:
    po = P2PService(session, tenant_id, entity_id=entity_id).create_po(**body.model_dump())
    return {
        "po_id": po.po_id,
        "po_number": po.po_number,
        "status": po.status,
        "amount": po.quantity * po.unit_rate,
    }


@router.get("/purchase-orders")
def list_pos(session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    rows = session.exec(select(PurchaseOrder).where(PurchaseOrder.tenant_id == tenant_id)).all()
    return {
        "items": [
            {
                "po_id": p.po_id,
                "po_number": p.po_number,
                "vendor_id": p.vendor_id,
                "status": p.status,
                "quantity": p.quantity,
                "unit_rate": p.unit_rate,
            }
            for p in rows
        ],
        "count": len(rows),
    }


@router.post("/grn")
def create_grn(
    body: GRNCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: ProcurementDep,
) -> dict[str, Any]:
    receipt = P2PService(session, tenant_id, entity_id=entity_id).receive_goods(
        po_id=body.po_id,
        quantity_received=body.quantity_received,
        received_date=body.received_date or date.today().isoformat(),
        notes=body.notes,
    )
    stock_posted = None
    if body.post_to_stock_sku_code:
        sku = session.exec(
            select(StockSku).where(
                StockSku.tenant_id == tenant_id,
                StockSku.sku_code == body.post_to_stock_sku_code.strip(),
            )
        ).first()
        if sku:
            sku.qty_on_hand = float(sku.qty_on_hand or 0) + float(body.quantity_received)
            sku.updated_at = utcnow()
            session.add(sku)
            session.commit()
            stock_posted = {"sku_id": sku.sku_id, "qty_on_hand": sku.qty_on_hand}
    return {
        "receipt_id": receipt.receipt_id,
        "status": receipt.status,
        "quantity_received": receipt.quantity_received,
        "stock_posted": stock_posted,
    }


@router.post("/ses")
def create_ses(
    body: SESCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: ProcurementDep,
) -> dict[str, Any]:
    ses = P2PService(session, tenant_id, entity_id=entity_id).create_ses(**body.model_dump())
    return {"ses_id": ses.ses_id, "status": ses.status, "amount": ses.amount, "notes": ses.notes}


@router.post("/invoices/{invoice_id}/match-and-post")
def match_post(
    invoice_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: FinanceDep,
) -> dict[str, Any]:
    return P2PService(session, tenant_id, entity_id=entity_id).match_and_post_invoice(invoice_id)
