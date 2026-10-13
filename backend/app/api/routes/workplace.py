"""Workplace seating + visitor journey APIs (M02/M09)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DashboardOpsDep, SessionDep, TenantDep
from app.services.workplace import WorkplaceService

router = APIRouter(prefix="/workplace", tags=["workplace"])


class SeatAlloc(BaseModel):
    person_id: Optional[str] = None
    location_id: Optional[str] = None
    resource_id: Optional[str] = None
    outcome_id: Optional[str] = None


@router.get("/seats/available")
def seats(session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep, location_id: Optional[str] = None) -> dict[str, Any]:
    rows = WorkplaceService(session, tenant_id).available_seats(location_id=location_id)
    return {
        "items": [{"resource_id": r.resource_id, "name": r.name, "location_id": r.location_id} for r in rows],
        "count": len(rows),
    }


@router.post("/seats/allocate")
def allocate(body: SeatAlloc, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    return WorkplaceService(session, tenant_id).allocate_seat(**body.model_dump())


@router.post("/seats/{resource_id}/release")
def release(resource_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    return WorkplaceService(session, tenant_id).release_seat(resource_id)


@router.post("/visitors/{pass_id}/check-in")
def check_in(pass_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = WorkplaceService(session, tenant_id).check_in_visitor(pass_id)
    return {"pass_id": row.pass_id, "status": row.status, "visitor_name": row.visitor_name}


@router.post("/visitors/{pass_id}/check-out")
def check_out(pass_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = WorkplaceService(session, tenant_id).check_out_visitor(pass_id)
    return {"pass_id": row.pass_id, "status": row.status, "visitor_name": row.visitor_name}
