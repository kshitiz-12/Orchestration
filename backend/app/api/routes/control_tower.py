"""Control tower / MI snapshot (M26) — governed metrics from live tables."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlmodel import func, select

from app.api.deps import DashboardOpsDep, SessionDep, TenantDep
from app.models.facilities import IncidentRecord, PreventiveSchedule
from app.models.finance import CostRequirement, ErpHandoff
from app.models.org import Invoice, OutboxEvent, Vendor
from app.models.outcome import Outcome, Task

router = APIRouter(prefix="/control-tower", tags=["control-tower"])


@router.get("/summary")
def summary(session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    def count(model, *extra):
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        for clause in extra:
            stmt = stmt.where(clause)
        return int(session.exec(stmt).one() or 0)

    open_outcomes = count(Outcome, Outcome.status.notin_(["CLOSED", "VERIFIED_CLOSED", "CANCELLED"]))
    open_tasks = count(Task, Task.status.notin_(["DONE", "CANCELLED", "WAIVED", "VERIFIED"]))
    active_vendors = count(Vendor, Vendor.status == "ACTIVE")
    open_incidents = count(IncidentRecord, IncidentRecord.status != "CLOSED")
    overdue_pm = count(
        PreventiveSchedule,
        PreventiveSchedule.status == "ACTIVE",
    )
    pending_outbox = count(OutboxEvent, OutboxEvent.status == "PENDING")
    invoices_pending = count(Invoice, Invoice.match_status != "MATCHED")
    erp_failed = count(ErpHandoff, ErpHandoff.status.in_(["FAILED", "REJECTED"]))
    cost_open = count(CostRequirement, CostRequirement.status.notin_(["CLOSED", "CANCELLED"]))

    return {
        "tenant_id": tenant_id,
        "operations": {
            "open_outcomes": open_outcomes,
            "open_tasks": open_tasks,
            "pending_outbox": pending_outbox,
        },
        "facilities": {
            "active_pm_schedules": overdue_pm,
            "open_incidents": open_incidents,
        },
        "vendors_p2p": {
            "active_vendors": active_vendors,
            "invoices_unmatched": invoices_pending,
            "erp_failed_or_rejected": erp_failed,
            "open_cost_requirements": cost_open,
        },
        "note": "Metrics are live counts — definitions versioned in V3 MI catalogue; no invented finance totals",
    }
