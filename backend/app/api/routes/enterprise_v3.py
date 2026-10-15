"""Enterprise V3 APIs — contracts, vendor workspace, sealed RFQ, ESG, learning sign-off, outbox DLQ."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CompanyAdminDep, DashboardOpsDep, EntityDep, SessionDep, TenantDep
from app.services.commercial_cost import CommercialCostService
from app.services.enterprise_v3 import EnterpriseV3Service
from app.services.outbox import OutboxService

router = APIRouter(tags=["enterprise-v3"])


class AmendBody(BaseModel):
    change_summary: str
    rate_card_delta: dict[str, Any] = Field(default_factory=dict)
    sla_credits: list[Any] = Field(default_factory=list)
    penalties: list[Any] = Field(default_factory=list)
    effective_from: Optional[str] = None
    approved_by: Optional[str] = None


class TerminateBody(BaseModel):
    reason: str
    approved_by: Optional[str] = None


class VendorWsBody(BaseModel):
    item_type: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)
    amount: float = 0.0
    outcome_id: Optional[str] = None
    rfq_id: Optional[str] = None
    file_refs: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class VendorWsDecide(BaseModel):
    status: str
    notes: Optional[str] = None


class MeterBody(BaseModel):
    meter_code: str
    utility_type: str
    reading_value: float
    location_id: Optional[str] = None
    max_dial: float = 999999.0


class WasteBody(BaseModel):
    waste_type: str
    quantity_kg: float
    location_id: Optional[str] = None
    disposer: Optional[str] = None
    manifest_no: Optional[str] = None
    disposed_on: Optional[str] = None
    certificate_ref: Optional[str] = None


class CarbonBody(BaseModel):
    period: str
    scope: str
    tco2e: float
    location_id: Optional[str] = None
    methodology: str = "MANUAL"
    factors: dict[str, Any] = Field(default_factory=dict)


class LearningSignBody(BaseModel):
    signed_by: str
    decision: str = "APPROVE"
    notes: Optional[str] = None


class ReportCostBody(BaseModel):
    amount: float
    actor: Optional[str] = None
    note: Optional[str] = None


@router.post("/contracts/{contract_id}/amendments")
def amend_contract(
    contract_id: str,
    body: AmendBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).amend_contract(contract_id, **body.model_dump())
    return {"amendment_id": row.amendment_id, "version": row.version, "status": row.status}


@router.post("/contracts/{contract_id}/terminate")
def terminate_contract(
    contract_id: str,
    body: TerminateBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).terminate_contract(
        contract_id, reason=body.reason, approved_by=body.approved_by
    )
    return {"contract_id": row.contract_id, "status": row.status, "end_date": row.end_date}


@router.post("/vendors/{vendor_id}/workspace")
def vendor_workspace_submit(
    vendor_id: str,
    body: VendorWsBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).vendor_submit(vendor_id, **body.model_dump())
    return {"item_id": row.item_id, "item_type": row.item_type, "status": row.status}


@router.post("/vendor-workspace/{item_id}/decide")
def vendor_workspace_decide(
    item_id: str,
    body: VendorWsDecide,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).vendor_ws_decide(item_id, status=body.status, notes=body.notes)
    return {"item_id": row.item_id, "status": row.status}


@router.post("/sourcing/rfq/{rfq_id}/sealed-score")
def sealed_score(
    rfq_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    unseal: bool = False,
) -> dict[str, Any]:
    return EnterpriseV3Service(session, tenant_id).score_quotes_sealed(rfq_id, unseal=unseal)


@router.post("/utilities/meters")
def meter_reading(
    body: MeterBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).record_meter(**body.model_dump())
    return {
        "reading_id": row.reading_id,
        "delta": row.delta,
        "rolled_over": row.rolled_over,
        "previous_value": row.previous_value,
        "reading_value": row.reading_value,
    }


@router.post("/esg/waste-manifests")
def waste_manifest(
    body: WasteBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).log_waste(**body.model_dump())
    return {"manifest_id": row.manifest_id, "waste_type": row.waste_type, "quantity_kg": row.quantity_kg}


@router.post("/esg/carbon")
def carbon(
    body: CarbonBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = EnterpriseV3Service(session, tenant_id).upsert_carbon(**body.model_dump())
    return {"carbon_id": row.carbon_id, "scope": row.scope, "tco2e": row.tco2e, "period": row.period}


@router.post("/learning/{record_id}/sign-off")
def learning_signoff(
    record_id: str,
    body: LearningSignBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    return EnterpriseV3Service(session, tenant_id).sign_off_learning(record_id, **body.model_dump())


@router.post("/outcomes/{outcome_id}/cost/report")
def report_cost(
    outcome_id: str,
    body: ReportCostBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = CommercialCostService(session, tenant_id, entity_id).report_operational(
        outcome_id, body.amount, actor=body.actor, note=body.note
    )
    return CommercialCostService(session, tenant_id, entity_id).snapshot(outcome_id) | {
        "cost_id": row.cost_id,
        "status": row.status,
    }


@router.get("/outcomes/{outcome_id}/cost")
def get_cost(
    outcome_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return CommercialCostService(session, tenant_id, entity_id).snapshot(outcome_id)


@router.get("/outbox/dead-letters")
def dead_letters(
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    rows = OutboxService(session, tenant_id).dead_letters()
    return {
        "items": [
            {
                "outbox_id": r.outbox_id,
                "event_type": r.event_type,
                "attempts": r.attempts,
                "last_error": r.last_error,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/outbox/dead-letters/{outbox_id}/requeue")
def requeue_dead(
    outbox_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    row = OutboxService(session, tenant_id).requeue_dead(outbox_id)
    return {"outbox_id": row.outbox_id, "status": row.status}


@router.post("/integrations/erp/reconcile")
def erp_reconcile(
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    return OutboxService(session, tenant_id).reconcile_erp_handoffs()
