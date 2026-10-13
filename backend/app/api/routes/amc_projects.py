"""AMC obligations + projects APIs (M04 / M25)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DashboardOpsDep, EntityDep, SessionDep, TenantDep
from app.services.amc_contracts import AmcContractsService

router = APIRouter(tags=["amc-projects"])


class AmcIn(BaseModel):
    contract_id: str
    title: str
    asset_id: Optional[str] = None
    sla_hours: int = 24
    inclusions: list[Any] = Field(default_factory=list)
    exclusions: list[Any] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    next_pm_due: Optional[str] = None


class ProjectIn(BaseModel):
    code: str
    name: str
    project_type: str = "FITOUT"
    budget_amount: float = 0.0
    location_id: Optional[str] = None
    vendor_id: Optional[str] = None
    milestones: list[Any] = Field(default_factory=list)


@router.post("/amc/obligations")
def create_amc(body: AmcIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = AmcContractsService(session, tenant_id).link_obligation(**body.model_dump())
    return {
        "obligation_id": row.obligation_id,
        "contract_id": row.contract_id,
        "title": row.title,
        "status": row.status,
    }


@router.get("/amc/obligations")
def list_amc(
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    contract_id: Optional[str] = None,
) -> dict[str, Any]:
    rows = AmcContractsService(session, tenant_id).list_obligations(contract_id=contract_id)
    return {
        "items": [
            {
                "obligation_id": r.obligation_id,
                "contract_id": r.contract_id,
                "title": r.title,
                "asset_id": r.asset_id,
                "status": r.status,
                "next_pm_due": r.next_pm_due,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/projects")
def create_project(
    body: ProjectIn,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = AmcContractsService(session, tenant_id).create_project(**body.model_dump(), entity_id=entity_id)
    return {
        "project_id": row.project_id,
        "code": row.code,
        "name": row.name,
        "status": row.status,
        "budget_amount": row.budget_amount,
    }


@router.post("/projects/{project_id}/status")
def project_status(
    project_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    status: str,
) -> dict[str, Any]:
    row = AmcContractsService(session, tenant_id).advance_project(project_id, status)
    return {"project_id": row.project_id, "status": row.status}
