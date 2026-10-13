"""Facilities module APIs — PM, soft services, incidents, catalogue, space, compliance, WO."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DashboardOpsDep, EntityDep, SessionDep, TenantDep
from app.services.facilities_enterprise import FacilitiesEnterpriseService
from app.services.facilities_ops import FacilitiesOpsService

router = APIRouter(prefix="/facilities", tags=["facilities"])


class PmCreate(BaseModel):
    title: str
    frequency_days: int = 30
    asset_id: Optional[str] = None
    location_id: Optional[str] = None
    checklist: list[Any] = Field(default_factory=list)
    owner_role: str = "FACILITIES"
    job_plan_id: Optional[str] = None
    safety_permit_required: bool = False
    competency_required: Optional[str] = None


class SoftRoundBody(BaseModel):
    service_type: str
    location_id: Optional[str] = None
    score: Optional[float] = None
    findings: list[Any] = Field(default_factory=list)
    notes: Optional[str] = None


class IncidentCreate(BaseModel):
    incident_type: str
    title: str
    severity: str = "MEDIUM"
    description: Optional[str] = None
    location_id: Optional[str] = None
    outcome_id: Optional[str] = None
    reported_by: Optional[str] = None
    deterministic_urgent: bool = False


class LocationProfileBody(BaseModel):
    address: Optional[str] = None
    cost_centre: Optional[str] = None
    owner_email: Optional[str] = None
    criticality: Optional[str] = None
    service_bundle: Optional[list[str]] = None
    timezone: Optional[str] = None
    operating_hours: Optional[str] = None
    headcount: Optional[int] = None
    area_sqft: Optional[float] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class SpaceBody(BaseModel):
    code: str
    name: str
    space_type: str = "ROOM"
    location_id: Optional[str] = None
    parent_space_id: Optional[str] = None
    room_type: Optional[str] = None
    capacity_seats: int = 0
    area_sqft: float = 0.0
    amenities: list[Any] = Field(default_factory=list)
    accessibility: list[Any] = Field(default_factory=list)
    hvac_zone: Optional[str] = None
    fire_zone: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ServiceItemBody(BaseModel):
    service_code: str
    service_family: str
    service_item: str
    description: Optional[str] = None
    inclusions: list[Any] = Field(default_factory=list)
    exclusions: list[Any] = Field(default_factory=list)
    dependencies: list[Any] = Field(default_factory=list)
    eligible_requesters: list[str] = Field(default_factory=lambda: ["EMPLOYEE"])
    applicable_site_types: list[str] = Field(default_factory=lambda: ["BRANCH", "BUILDING"])
    criticality: str = "MEDIUM"
    operating_window: str = "BUSINESS_HOURS"
    mandatory_fields: list[Any] = Field(default_factory=list)
    attachment_requirements: list[Any] = Field(default_factory=list)
    approval_conditions: list[Any] = Field(default_factory=list)
    fulfilment_checklist: list[Any] = Field(default_factory=list)
    sla_response_hours: float = 4.0
    sla_attendance_hours: float = 8.0
    sla_resolution_hours: float = 48.0
    sla_restoration_hours: Optional[float] = None
    owner_team: str = "FACILITIES"
    primary_vendor_id: Optional[str] = None
    backup_vendor_id: Optional[str] = None
    escalation_chain: list[Any] = Field(default_factory=list)
    after_hours_contact: Optional[str] = None
    unit_of_measure: str = "each"
    rate: float = 0.0
    currency: str = "INR"
    tax_code: Optional[str] = None
    minimum_billing: float = 0.0
    free_entitlement: float = 0.0
    chargeback_rule_code: Optional[str] = None
    closure_codes: list[str] = Field(default_factory=lambda: ["RESOLVED", "DUPLICATE", "CANCELLED"])
    evidence_retention_days: int = 365
    reopen_window_hours: int = 72


class AssetEnrichBody(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    criticality: Optional[str] = None
    commissioned_on: Optional[str] = None
    warranty_end: Optional[str] = None
    owner_email: Optional[str] = None
    capacity: Optional[str] = None
    redundancy: Optional[str] = None
    maintenance_category: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class JobPlanBody(BaseModel):
    code: str
    title: str
    asset_types: list[str] = Field(default_factory=list)
    tasks: list[Any] = Field(default_factory=list)
    parts: list[Any] = Field(default_factory=list)
    estimated_hours: float = 1.0
    safety_permit: Optional[str] = None
    competency: Optional[str] = None
    evidence_required: list[Any] = Field(default_factory=list)


class SoftScheduleBody(BaseModel):
    service_type: str
    frequency_days: int = 1
    location_id: Optional[str] = None
    vendor_id: Optional[str] = None
    contract_id: Optional[str] = None
    checklist: list[Any] = Field(default_factory=list)


class SoftCompleteBody(BaseModel):
    score: Optional[float] = None
    findings: list[Any] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class WorkOrderCreate(BaseModel):
    title: str
    priority: str = "P3"
    description: Optional[str] = None
    location_id: Optional[str] = None
    asset_id: Optional[str] = None
    service_code: Optional[str] = None
    requester_email: Optional[str] = None
    outcome_id: Optional[str] = None


class WorkOrderAdvance(BaseModel):
    status: str
    assignee_email: Optional[str] = None
    closure_code: Optional[str] = None
    evidence_ids: Optional[list[str]] = None
    parts_used: Optional[list[Any]] = None
    labour_hours: Optional[float] = None
    cost_amount: Optional[float] = None


class ItemMasterBody(BaseModel):
    sku_code: str
    name: str
    location_id: Optional[str] = None
    category: Optional[str] = None
    qty_on_hand: float = 0.0
    reorder_min: float = 0.0
    reorder_qty: float = 0.0
    safety_stock: float = 0.0
    max_stock: float = 0.0
    unit: str = "each"
    pack_size: float = 1.0
    batch_code: Optional[str] = None
    expires_on: Optional[str] = None
    controlled_item: bool = False
    hazardous: bool = False
    standard_item: bool = True
    contracted_rate: float = 0.0
    lead_time_days: int = 0
    min_order_qty: float = 0.0
    substitute_sku_code: Optional[str] = None
    gl_account: Optional[str] = None
    budget_head: Optional[str] = None
    chargeback_rule_code: Optional[str] = None
    vendor_id: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntitlementBody(BaseModel):
    sku_code: str
    monthly_qty: float
    role: str = "*"
    location_type: str = "*"
    max_per_request: float = 0.0
    requires_approval_above: Optional[float] = None


class CycleCountBody(BaseModel):
    sku_id: str
    counted_qty: float
    counted_by: Optional[str] = None
    notes: Optional[str] = None
    adjust: bool = False


class ChargebackBody(BaseModel):
    code: str
    name: str
    method: str
    drivers: dict[str, Any] = Field(default_factory=dict)
    allocations: list[Any] = Field(default_factory=list)
    subsidy_pct: float = 0.0


class AllocateBody(BaseModel):
    amount: float


class ComplianceBody(BaseModel):
    requirement_code: str
    law_or_standard: str
    jurisdiction: str = "IN"
    location_ids: list[str] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    licence_type: Optional[str] = None
    authority: Optional[str] = None
    certificate_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    renewal_lead_days: int = 30
    owner_email: Optional[str] = None
    risk_rating: str = "MEDIUM"
    grace_days: int = 0
    business_restriction: Optional[str] = None


class RiskBody(BaseModel):
    title: str
    location_id: Optional[str] = None
    category: str = "OPERATIONAL"
    likelihood: str = "MEDIUM"
    impact: str = "MEDIUM"
    inherent_score: float = 0.0
    residual_score: float = 0.0
    controls: list[Any] = Field(default_factory=list)
    owner_email: Optional[str] = None
    treatment: str = "MITIGATE"
    next_review_date: Optional[str] = None


class BcpBody(BaseModel):
    plan_type: str
    title: str
    location_id: Optional[str] = None
    bia: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[Any] = Field(default_factory=list)
    contact_tree: list[Any] = Field(default_factory=list)
    command_roles: dict[str, Any] = Field(default_factory=dict)
    assembly_points: list[Any] = Field(default_factory=list)
    alternate_workspace: Optional[str] = None
    vendor_mobilisation: list[Any] = Field(default_factory=list)
    critical_spares: list[Any] = Field(default_factory=list)


class DrillBody(BaseModel):
    score: Optional[float] = None
    lessons: list[Any] = Field(default_factory=list)
    actions: list[Any] = Field(default_factory=list)
    participants: list[Any] = Field(default_factory=list)
    notes: Optional[str] = None


class EsgBody(BaseModel):
    metric_type: str
    period: str
    value: float
    location_id: Optional[str] = None
    unit: str = ""
    source: str = "MANUAL"


class AmcCallBody(BaseModel):
    category: str
    asset_id: Optional[str] = None
    location_id: Optional[str] = None


# ── Legacy PM / soft / incident ─────────────────────────────────────────────


@router.post("/pm-schedules")
def create_pm(
    body: PmCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesOpsService(session, tenant_id, entity_id).create_pm_schedule(
        title=body.title,
        frequency_days=body.frequency_days,
        asset_id=body.asset_id,
        location_id=body.location_id,
        checklist=body.checklist,
        owner_role=body.owner_role,
    )
    if body.job_plan_id or body.safety_permit_required or body.competency_required:
        row.job_plan_id = body.job_plan_id
        row.safety_permit_required = body.safety_permit_required
        row.competency_required = body.competency_required
        session.add(row)
        session.commit()
        session.refresh(row)
    return {
        "schedule_id": row.schedule_id,
        "title": row.title,
        "next_due_at": row.next_due_at.isoformat() if row.next_due_at else None,
        "status": row.status,
        "job_plan_id": getattr(row, "job_plan_id", None),
    }


@router.post("/pm-schedules/{schedule_id}/complete")
def complete_pm(
    schedule_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    row = FacilitiesOpsService(session, tenant_id, entity_id).complete_pm(schedule_id, notes=notes)
    return {
        "schedule_id": row.schedule_id,
        "last_completed_at": row.last_completed_at.isoformat() if row.last_completed_at else None,
        "next_due_at": row.next_due_at.isoformat() if row.next_due_at else None,
    }


@router.get("/pm-schedules/overdue")
def overdue_pm(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    rows = FacilitiesOpsService(session, tenant_id, entity_id).overdue_pm()
    return {
        "items": [
            {
                "schedule_id": r.schedule_id,
                "title": r.title,
                "next_due_at": r.next_due_at.isoformat() if r.next_due_at else None,
                "asset_id": r.asset_id,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/soft-rounds")
def soft_round(
    body: SoftRoundBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesOpsService(session, tenant_id, entity_id).log_soft_round(
        service_type=body.service_type,
        location_id=body.location_id,
        score=body.score,
        findings=body.findings,
        notes=body.notes,
    )
    return {"round_id": row.round_id, "service_type": row.service_type, "status": row.status, "score": row.score}


@router.post("/incidents")
def raise_incident(
    body: IncidentCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesOpsService(session, tenant_id, entity_id).raise_incident(
        incident_type=body.incident_type,
        title=body.title,
        severity=body.severity,
        description=body.description,
        location_id=body.location_id,
        outcome_id=body.outcome_id,
        reported_by=body.reported_by,
        deterministic_urgent=body.deterministic_urgent,
    )
    return {
        "incident_id": row.incident_id,
        "status": row.status,
        "severity": row.severity,
        "deterministic_urgent": row.deterministic_urgent,
        "fanout_notified": getattr(row, "fanout_notified", []) or [],
    }


# ── Enterprise masters ──────────────────────────────────────────────────────


@router.put("/locations/{location_id}/profile")
def location_profile(
    location_id: str,
    body: LocationProfileBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    svc = FacilitiesEnterpriseService(session, tenant_id, entity_id)
    loc = svc.upsert_location_profile(
        location_id,
        address=body.address,
        cost_centre=body.cost_centre,
        owner_email=body.owner_email,
        criticality=body.criticality,
        service_bundle=body.service_bundle,
        timezone=body.timezone,
        operating_hours=body.operating_hours,
        headcount=body.headcount,
        area_sqft=body.area_sqft,
        extra=body.extra,
    )
    return {"location_id": loc.location_id, "attributes": loc.attributes or {}, **svc.location_completeness(location_id)}


@router.get("/locations/{location_id}/completeness")
def location_completeness(
    location_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).location_completeness(location_id)


@router.post("/spaces")
def upsert_space(
    body: SpaceBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_space(**body.model_dump())
    return {
        "space_id": row.space_id,
        "code": row.code,
        "name": row.name,
        "space_type": row.space_type,
        "capacity_seats": row.capacity_seats,
        "amenities": row.amenities,
    }


@router.get("/spaces")
def list_spaces(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
    location_id: Optional[str] = None,
) -> dict[str, Any]:
    rows = FacilitiesEnterpriseService(session, tenant_id, entity_id).list_spaces(location_id=location_id)
    return {
        "items": [
            {
                "space_id": r.space_id,
                "code": r.code,
                "name": r.name,
                "space_type": r.space_type,
                "capacity_seats": r.capacity_seats,
                "area_sqft": r.area_sqft,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/catalogue")
def upsert_catalogue(
    body: ServiceItemBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_service_item(**body.model_dump())
    return {
        "item_id": row.item_id,
        "service_code": row.service_code,
        "service_family": row.service_family,
        "sla_response_hours": row.sla_response_hours,
        "sla_resolution_hours": row.sla_resolution_hours,
        "chargeback_rule_code": row.chargeback_rule_code,
        "status": row.status,
    }


@router.get("/catalogue")
def list_catalogue(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
    family: Optional[str] = None,
) -> dict[str, Any]:
    rows = FacilitiesEnterpriseService(session, tenant_id, entity_id).list_service_items(family=family)
    return {
        "items": [
            {
                "service_code": r.service_code,
                "service_family": r.service_family,
                "service_item": r.service_item,
                "criticality": r.criticality,
                "rate": r.rate,
                "sla_resolution_hours": r.sla_resolution_hours,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/assets/{asset_id}/enrich")
def enrich_asset(
    asset_id: str,
    body: AssetEnrichBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    profile = {k: v for k, v in body.model_dump().items() if k != "extra" and v is not None}
    profile.update(body.extra or {})
    svc = FacilitiesEnterpriseService(session, tenant_id, entity_id)
    asset = svc.enrich_asset(asset_id, profile)
    return {"asset_id": asset.asset_id, "attributes": asset.attributes, **svc.asset_completeness(asset_id)}


@router.get("/assets/{asset_id}/completeness")
def asset_completeness(
    asset_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).asset_completeness(asset_id)


@router.post("/amc/vendor-call")
def amc_vendor_call(
    body: AmcCallBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).resolve_amc_vendor_call(
        category=body.category,
        asset_id=body.asset_id,
        location_id=body.location_id,
    )


@router.post("/job-plans")
def upsert_job_plan(
    body: JobPlanBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_job_plan(**body.model_dump())
    return {"plan_id": row.plan_id, "code": row.code, "title": row.title, "tasks": row.tasks}


@router.post("/soft-schedules")
def soft_schedule(
    body: SoftScheduleBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).create_soft_schedule(**body.model_dump())
    return {"schedule_id": row.schedule_id, "service_type": row.service_type, "next_due_at": row.next_due_at.isoformat() if row.next_due_at else None}


@router.post("/soft-schedules/generate")
def generate_soft_rounds(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    created = FacilitiesEnterpriseService(session, tenant_id, entity_id).generate_due_soft_rounds()
    return {"created": created, "count": len(created)}


@router.post("/soft-rounds/{round_id}/complete-ses")
def complete_soft_ses(
    round_id: str,
    body: SoftCompleteBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).complete_soft_round_with_ses(
        round_id,
        score=body.score,
        findings=body.findings,
        evidence_ids=body.evidence_ids,
        notes=body.notes,
    )


@router.post("/work-orders")
def create_wo(
    body: WorkOrderCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).create_work_order(**body.model_dump())
    return {
        "work_order_id": row.work_order_id,
        "status": row.status,
        "priority": row.priority,
        "vendor_id": row.vendor_id,
        "amc_obligation_id": row.amc_obligation_id,
        "duplicate_of": row.duplicate_of,
        "sla_resolve_at": row.sla_resolve_at.isoformat() if row.sla_resolve_at else None,
    }


@router.post("/work-orders/{work_order_id}/advance")
def advance_wo(
    work_order_id: str,
    body: WorkOrderAdvance,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).advance_work_order(
        work_order_id,
        body.status,
        assignee_email=body.assignee_email,
        closure_code=body.closure_code,
        evidence_ids=body.evidence_ids,
        parts_used=body.parts_used,
        labour_hours=body.labour_hours,
        cost_amount=body.cost_amount,
    )
    return {"work_order_id": row.work_order_id, "status": row.status, "closure_code": row.closure_code}


@router.post("/inventory/items")
def upsert_item(
    body: ItemMasterBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_item_master(**body.model_dump())
    return {
        "sku_id": row.sku_id,
        "sku_code": row.sku_code,
        "name": row.name,
        "controlled_item": row.controlled_item,
        "expires_on": row.expires_on,
        "qty_on_hand": row.qty_on_hand,
    }


@router.post("/inventory/entitlements")
def set_entitlement(
    body: EntitlementBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).set_entitlement(**body.model_dump())
    return {"entitlement_id": row.entitlement_id, "sku_code": row.sku_code, "monthly_qty": row.monthly_qty}


@router.get("/inventory/entitlements/check")
def check_entitlement(
    sku_code: str,
    qty: float,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
    role: str = "*",
    location_type: str = "*",
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).check_issue_entitlement(
        sku_code=sku_code, qty=qty, role=role, location_type=location_type
    )


@router.post("/inventory/cycle-counts")
def cycle_count(
    body: CycleCountBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).record_cycle_count(**body.model_dump())
    return {
        "count_id": row.count_id,
        "variance": row.variance,
        "status": row.status,
        "system_qty": row.system_qty,
        "counted_qty": row.counted_qty,
    }


@router.get("/inventory/expiring")
def expiring(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
    within_days: int = 30,
) -> dict[str, Any]:
    items = FacilitiesEnterpriseService(session, tenant_id, entity_id).expiring_batches(within_days)
    return {"items": items, "count": len(items)}


@router.post("/chargeback/rules")
def chargeback_rule(
    body: ChargebackBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_chargeback_rule(**body.model_dump())
    return {"rule_id": row.rule_id, "code": row.code, "method": row.method}


@router.post("/chargeback/rules/{code}/allocate")
def allocate(
    code: str,
    body: AllocateBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).allocate_chargeback(code, body.amount)


@router.post("/compliance")
def upsert_compliance(
    body: ComplianceBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_compliance(**body.model_dump())
    return {
        "requirement_id": row.requirement_id,
        "requirement_code": row.requirement_code,
        "expiry_date": row.expiry_date,
        "status": row.status,
    }


@router.get("/compliance/due")
def compliance_due(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
    within_days: int = 30,
) -> dict[str, Any]:
    rows = FacilitiesEnterpriseService(session, tenant_id, entity_id).compliance_due(within_days)
    return {
        "items": [
            {
                "requirement_id": r.requirement_id,
                "requirement_code": r.requirement_code,
                "expiry_date": r.expiry_date,
                "status": r.status,
                "risk_rating": r.risk_rating,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.post("/risks")
def upsert_risk(
    body: RiskBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_risk(**body.model_dump())
    return {"risk_id": row.risk_id, "title": row.title, "status": row.status}


@router.post("/bcp/plans")
def upsert_bcp(
    body: BcpBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).upsert_bcp_plan(**body.model_dump())
    return {"plan_id": row.plan_id, "plan_type": row.plan_type, "title": row.title}


@router.post("/bcp/plans/{plan_id}/drills")
def record_drill(
    plan_id: str,
    body: DrillBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).record_drill(plan_id, **body.model_dump())
    return {"drill_id": row.drill_id, "score": row.score, "status": row.status}


@router.post("/esg/metrics")
def esg_metric(
    body: EsgBody,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = FacilitiesEnterpriseService(session, tenant_id, entity_id).record_esg_metric(**body.model_dump())
    return {"metric_id": row.metric_id, "metric_type": row.metric_type, "value": row.value, "period": row.period}


@router.get("/dashboard")
def dashboard(
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return FacilitiesEnterpriseService(session, tenant_id, entity_id).facilities_dashboard()
