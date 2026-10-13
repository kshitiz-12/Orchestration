"""Admin module APIs — mailroom, joiner/leaver, utilities."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DashboardOpsDep, SessionDep, TenantDep
from app.services.admin_modules import AdminModulesService

router = APIRouter(prefix="/admin-modules", tags=["admin-modules"])


class MailIn(BaseModel):
    direction: str
    tracking_ref: Optional[str] = None
    carrier: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    sender_name: Optional[str] = None
    location_id: Optional[str] = None
    notes: Optional[str] = None


class LifecycleIn(BaseModel):
    event_type: str
    person_email: str
    site_id: Optional[str] = None
    outcome_id: Optional[str] = None


class UtilityIn(BaseModel):
    meter_code: str
    utility_type: str
    reading_value: float
    unit: str = "kWh"
    location_id: Optional[str] = None
    reading_at: Optional[str] = None


@router.post("/mail")
def log_mail(body: MailIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = AdminModulesService(session, tenant_id).log_mail(**body.model_dump())
    return {"mail_id": row.mail_id, "direction": row.direction, "status": row.status, "tracking_ref": row.tracking_ref}


@router.post("/lifecycle")
def start_lifecycle(body: LifecycleIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = AdminModulesService(session, tenant_id).start_lifecycle(**body.model_dump())
    return {
        "case_id": row.case_id,
        "event_type": row.event_type,
        "status": row.status,
        "checklist": row.checklist,
    }


@router.post("/lifecycle/{case_id}/complete/{code}")
def complete_item(
    case_id: str, code: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep
) -> dict[str, Any]:
    row = AdminModulesService(session, tenant_id).complete_checklist_item(case_id, code)
    return {"case_id": row.case_id, "status": row.status, "checklist": row.checklist}


@router.post("/utilities")
def utility(body: UtilityIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = AdminModulesService(session, tenant_id).record_utility(**body.model_dump())
    return {
        "reading_id": row.reading_id,
        "meter_code": row.meter_code,
        "utility_type": row.utility_type,
        "reading_value": row.reading_value,
    }
