"""Vendor sourcing APIs (M16)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DashboardOpsDep, EntityDep, ProcurementDep, SessionDep, TenantDep
from app.services.vendor_sourcing import VendorSourcingService

router = APIRouter(prefix="/sourcing", tags=["sourcing"])


class ReqIn(BaseModel):
    title: str
    category: str
    description: Optional[str] = None
    location_id: Optional[str] = None
    outcome_id: Optional[str] = None


class RfqIn(BaseModel):
    vendor_ids: list[str] = Field(default_factory=list)
    due_at: Optional[str] = None
    notes: Optional[str] = None


class QuoteIn(BaseModel):
    vendor_id: str
    amount: float
    currency: str = "INR"
    lead_time_days: Optional[int] = None
    notes: Optional[str] = None


@router.post("/requirements")
def create_req(body: ReqIn, session: SessionDep, tenant_id: TenantDep, entity_id: EntityDep, _: ProcurementDep) -> dict[str, Any]:
    row = VendorSourcingService(session, tenant_id, entity_id).create_requirement(**body.model_dump())
    return {"requirement_id": row.requirement_id, "status": row.status, "category": row.category}


@router.post("/requirements/{requirement_id}/rfq")
def open_rfq(
    requirement_id: str,
    body: RfqIn,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: ProcurementDep,
) -> dict[str, Any]:
    rfq = VendorSourcingService(session, tenant_id, entity_id).open_rfq(
        requirement_id, vendor_ids=body.vendor_ids, due_at=body.due_at, notes=body.notes
    )
    return {"rfq_id": rfq.rfq_id, "status": rfq.status, "vendor_ids": rfq.vendor_ids}


@router.post("/rfq/{rfq_id}/quotes")
def submit_quote(
    rfq_id: str,
    body: QuoteIn,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    q = VendorSourcingService(session, tenant_id, entity_id).submit_quote(rfq_id, **body.model_dump())
    return {"quote_id": q.quote_id, "score": q.score, "status": q.status}


@router.get("/rfq/{rfq_id}/compare")
def compare(rfq_id: str, session: SessionDep, tenant_id: TenantDep, entity_id: EntityDep, _: ProcurementDep) -> dict[str, Any]:
    items = VendorSourcingService(session, tenant_id, entity_id).compare_quotes(rfq_id)
    return {"items": items, "count": len(items)}


@router.post("/rfq/{rfq_id}/award/{quote_id}")
def award(
    rfq_id: str,
    quote_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: ProcurementDep,
) -> dict[str, Any]:
    return VendorSourcingService(session, tenant_id, entity_id).award(rfq_id, quote_id)
