"""Facilities domain — PM, soft services, incidents, space, compliance, inventory controls.

Excludes real-estate/lease masters and mobile/IoT field capture (out of scope by product decision).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field

from app.models.org import TimestampMixin, new_id, utcnow


class PreventiveSchedule(TimestampMixin, table=True):
    __tablename__ = "preventive_schedules"

    schedule_id: str = Field(default_factory=lambda: new_id("pms_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    asset_id: Optional[str] = Field(default=None, foreign_key="assets.asset_id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    job_plan_id: Optional[str] = Field(default=None, index=True)
    title: str
    checklist: list = Field(default_factory=list, sa_column=Column(JSON))
    frequency_days: int = 30
    next_due_at: Optional[datetime] = Field(default=None, index=True)
    last_completed_at: Optional[datetime] = None
    owner_role: str = "FACILITIES"
    safety_permit_required: bool = False
    competency_required: Optional[str] = None
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class PmJobPlan(TimestampMixin, table=True):
    """Reusable PM job plan: tasks, parts, safety, competency (facilities.docx §5.4)."""

    __tablename__ = "pm_job_plans"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_pm_job_plan_code"),)

    plan_id: str = Field(default_factory=lambda: new_id("pjp_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str = Field(index=True)
    title: str
    asset_types: list = Field(default_factory=list, sa_column=Column(JSON))
    tasks: list = Field(default_factory=list, sa_column=Column(JSON))
    parts: list = Field(default_factory=list, sa_column=Column(JSON))
    estimated_hours: float = 1.0
    safety_permit: Optional[str] = None
    competency: Optional[str] = None
    evidence_required: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class SoftServiceSchedule(TimestampMixin, table=True):
    """Recurring soft-service schedule that generates SoftServiceRound rows."""

    __tablename__ = "soft_service_schedules"

    schedule_id: str = Field(default_factory=lambda: new_id("sss_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    service_type: str  # HOUSEKEEPING | HYGIENE | PEST | LANDSCAPING | WASTE
    frequency_days: int = 1
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id")
    contract_id: Optional[str] = Field(default=None, foreign_key="contracts.contract_id")
    checklist: list = Field(default_factory=list, sa_column=Column(JSON))
    next_due_at: Optional[datetime] = Field(default=None, index=True)
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class SoftServiceRound(TimestampMixin, table=True):
    __tablename__ = "soft_service_rounds"

    round_id: str = Field(default_factory=lambda: new_id("ssr_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    schedule_id: Optional[str] = Field(default=None, index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    service_type: str  # HOUSEKEEPING | HYGIENE | PEST | LANDSCAPING | WASTE
    scheduled_for: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    findings: list = Field(default_factory=list, sa_column=Column(JSON))
    evidence_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    ses_id: Optional[str] = None  # service entry sheet / certification link
    status: str = "SCHEDULED"  # SCHEDULED | DONE | MISSED | CANCELLED
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class IncidentRecord(TimestampMixin, table=True):
    __tablename__ = "incident_records"

    incident_id: str = Field(default_factory=lambda: new_id("inc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    work_order_id: Optional[str] = Field(default=None, index=True)
    incident_type: str  # SAFETY | SECURITY | FIRE | MEDICAL | BCP | OTHER
    severity: str = "MEDIUM"
    title: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    status: str = "OPEN"  # OPEN | INVESTIGATING | CONTAINED | CLOSED
    reported_by: Optional[str] = None
    deterministic_urgent: bool = False
    fanout_notified: list = Field(default_factory=list, sa_column=Column(JSON))
    capa: list = Field(default_factory=list, sa_column=Column(JSON))
    closed_at: Optional[datetime] = None


class WorkOrder(TimestampMixin, table=True):
    """Facilities work order / ticket fulfilment spine (facilities.docx §9.3)."""

    __tablename__ = "work_orders"

    work_order_id: str = Field(default_factory=lambda: new_id("wo_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    asset_id: Optional[str] = Field(default=None, foreign_key="assets.asset_id", index=True)
    service_code: Optional[str] = Field(default=None, index=True)
    title: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    priority: str = "P3"  # P1 | P2 | P3 | P4
    # OPEN | TRIAGED | APPROVED | ASSIGNED | IN_PROGRESS | PENDING_PARTS | PENDING_ACCEPTANCE | CLOSED | CANCELLED
    status: str = Field(default="OPEN", index=True)
    requester_email: Optional[str] = None
    assignee_email: Optional[str] = None
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id")
    amc_obligation_id: Optional[str] = None
    budget_id: Optional[str] = None
    sla_response_at: Optional[datetime] = None
    sla_resolve_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    attended_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    closure_code: Optional[str] = None
    evidence_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    parts_used: list = Field(default_factory=list, sa_column=Column(JSON))
    labour_hours: float = 0.0
    cost_amount: float = 0.0
    duplicate_of: Optional[str] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class SpaceUnit(TimestampMixin, table=True):
    """Space catalogue (building/floor/room) — capacity & amenities; no lease/rent fields."""

    __tablename__ = "space_units"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_space_unit_code"),)

    space_id: str = Field(default_factory=lambda: new_id("spc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    parent_space_id: Optional[str] = Field(default=None, index=True)
    code: str = Field(index=True)
    name: str
    # BUILDING | WING | FLOOR | ZONE | ROOM | DESK_BANK | PARKING | COMMON
    space_type: str = "ROOM"
    room_type: Optional[str] = None  # MEETING | CABIN | OPEN | SERVER | STORE | PANTRY | ...
    capacity_seats: int = 0
    area_sqft: float = 0.0
    amenities: list = Field(default_factory=list, sa_column=Column(JSON))
    accessibility: list = Field(default_factory=list, sa_column=Column(JSON))
    hvac_zone: Optional[str] = None
    fire_zone: Optional[str] = None
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class EnterpriseServiceItem(TimestampMixin, table=True):
    """Full enterprise service catalogue item (facilities.docx §4.1)."""

    __tablename__ = "enterprise_service_items"
    __table_args__ = (UniqueConstraint("tenant_id", "service_code", name="uq_ent_svc_code"),)

    item_id: str = Field(default_factory=lambda: new_id("esi_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    service_code: str = Field(index=True)
    service_family: str
    service_item: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    inclusions: list = Field(default_factory=list, sa_column=Column(JSON))
    exclusions: list = Field(default_factory=list, sa_column=Column(JSON))
    dependencies: list = Field(default_factory=list, sa_column=Column(JSON))
    eligible_requesters: list = Field(default_factory=list, sa_column=Column(JSON))
    applicable_site_types: list = Field(default_factory=list, sa_column=Column(JSON))
    criticality: str = "MEDIUM"
    operating_window: str = "BUSINESS_HOURS"
    mandatory_fields: list = Field(default_factory=list, sa_column=Column(JSON))
    attachment_requirements: list = Field(default_factory=list, sa_column=Column(JSON))
    approval_conditions: list = Field(default_factory=list, sa_column=Column(JSON))
    fulfilment_checklist: list = Field(default_factory=list, sa_column=Column(JSON))
    sla_response_hours: float = 4.0
    sla_attendance_hours: float = 8.0
    sla_resolution_hours: float = 48.0
    sla_restoration_hours: Optional[float] = None
    pause_rules: list = Field(default_factory=list, sa_column=Column(JSON))
    business_calendar: str = "DEFAULT"
    owner_team: str = "FACILITIES"
    primary_vendor_id: Optional[str] = None
    backup_vendor_id: Optional[str] = None
    escalation_chain: list = Field(default_factory=list, sa_column=Column(JSON))
    after_hours_contact: Optional[str] = None
    unit_of_measure: str = "each"
    rate: float = 0.0
    currency: str = "INR"
    tax_code: Optional[str] = None
    minimum_billing: float = 0.0
    escalation_formula: Optional[str] = None
    free_entitlement: float = 0.0
    chargeback_rule_code: Optional[str] = None
    closure_codes: list = Field(default_factory=list, sa_column=Column(JSON))
    evidence_retention_days: int = 365
    reopen_window_hours: int = 72
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ComplianceRequirement(TimestampMixin, table=True):
    """Compliance register (facilities.docx §10.2)."""

    __tablename__ = "compliance_requirements"
    __table_args__ = (UniqueConstraint("tenant_id", "requirement_code", name="uq_compliance_req"),)

    requirement_id: str = Field(default_factory=lambda: new_id("cmp_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    requirement_code: str = Field(index=True)
    law_or_standard: str
    jurisdiction: str = "IN"
    applicability: dict = Field(default_factory=dict, sa_column=Column(JSON))
    location_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    asset_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    licence_type: Optional[str] = None
    authority: Optional[str] = None
    certificate_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = Field(default=None, index=True)
    renewal_lead_days: int = 30
    owner_email: Optional[str] = None
    reviewer_email: Optional[str] = None
    approver_email: Optional[str] = None
    provider: Optional[str] = None
    evidence_refs: list = Field(default_factory=list, sa_column=Column(JSON))
    inspection_frequency_days: Optional[int] = None
    findings: list = Field(default_factory=list, sa_column=Column(JSON))
    corrective_actions: list = Field(default_factory=list, sa_column=Column(JSON))
    retention_days: int = 2555
    status: str = "COMPLIANT"  # COMPLIANT | DUE | OVERDUE | WAIVED | N/A
    risk_rating: str = "MEDIUM"
    grace_days: int = 0
    business_restriction: Optional[str] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class RiskRegisterItem(TimestampMixin, table=True):
    """Operational risk register (facilities.docx §10.3)."""

    __tablename__ = "risk_register_items"

    risk_id: str = Field(default_factory=lambda: new_id("rsk_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    title: str
    category: str = "OPERATIONAL"
    likelihood: str = "MEDIUM"
    impact: str = "MEDIUM"
    inherent_score: float = 0.0
    residual_score: float = 0.0
    controls: list = Field(default_factory=list, sa_column=Column(JSON))
    owner_email: Optional[str] = None
    treatment: str = "MITIGATE"  # ACCEPT | MITIGATE | TRANSFER | AVOID
    status: str = "OPEN"
    next_review_date: Optional[str] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class BcpPlan(TimestampMixin, table=True):
    """Site BCP / emergency readiness (facilities.docx §10.4) — no mobile/sensor telemetry."""

    __tablename__ = "bcp_plans"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "plan_type", name="uq_bcp_site_type"),)

    plan_id: str = Field(default_factory=lambda: new_id("bcp_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    plan_type: str  # FIRE | MEDICAL | FLOOD | WEATHER | CIVIL | UTILITY | SECURITY | GENERAL
    title: str
    bia: dict = Field(default_factory=dict, sa_column=Column(JSON))  # business impact assessment
    dependencies: list = Field(default_factory=list, sa_column=Column(JSON))
    contact_tree: list = Field(default_factory=list, sa_column=Column(JSON))
    command_roles: dict = Field(default_factory=dict, sa_column=Column(JSON))
    assembly_points: list = Field(default_factory=list, sa_column=Column(JSON))
    alternate_workspace: Optional[str] = None
    vendor_mobilisation: list = Field(default_factory=list, sa_column=Column(JSON))
    critical_spares: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "ACTIVE"
    last_drill_at: Optional[datetime] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class EmergencyDrill(TimestampMixin, table=True):
    __tablename__ = "emergency_drills"

    drill_id: str = Field(default_factory=lambda: new_id("drl_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    plan_id: str = Field(index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    conducted_at: datetime = Field(default_factory=utcnow)
    participants: list = Field(default_factory=list, sa_column=Column(JSON))
    score: Optional[float] = None
    lessons: list = Field(default_factory=list, sa_column=Column(JSON))
    actions: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "COMPLETED"
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class ChargebackRule(TimestampMixin, table=True):
    """Cost allocation / chargeback rule (facilities.docx §7.5)."""

    __tablename__ = "chargeback_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_chargeback_rule"),)

    rule_id: str = Field(default_factory=lambda: new_id("cbr_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str = Field(index=True)
    name: str
    # DIRECT | SHARED_FIXED | AREA | HEADCOUNT | METERED | TRANSACTION | HYBRID | CENTRAL
    method: str = "DIRECT"
    drivers: dict = Field(default_factory=dict, sa_column=Column(JSON))
    allocations: list = Field(default_factory=list, sa_column=Column(JSON))
    subsidy_pct: float = 0.0
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class BudgetTransfer(TimestampMixin, table=True):
    __tablename__ = "budget_transfers"

    transfer_id: str = Field(default_factory=lambda: new_id("btr_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    source_budget_id: str = Field(index=True)
    dest_budget_id: str = Field(index=True)
    amount: float
    justification: str
    approved_by: Optional[str] = None
    status: str = "APPROVED"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ItemEntitlement(TimestampMixin, table=True):
    """Per role/site monthly entitlement for inventory items (facilities.docx §6.2)."""

    __tablename__ = "item_entitlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku_code", "role", "location_type", name="uq_item_entitlement"),
    )

    entitlement_id: str = Field(default_factory=lambda: new_id("entl_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    sku_code: str = Field(index=True)
    role: str = "*"
    location_type: str = "*"
    monthly_qty: float = 0.0
    max_per_request: float = 0.0
    requires_approval_above: Optional[float] = None
    status: str = "ACTIVE"


class InventoryCycleCount(TimestampMixin, table=True):
    __tablename__ = "inventory_cycle_counts"

    count_id: str = Field(default_factory=lambda: new_id("icc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    sku_id: Optional[str] = Field(default=None, foreign_key="stock_skus.sku_id", index=True)
    counted_qty: float
    system_qty: float
    variance: float = 0.0
    counted_by: Optional[str] = None
    counted_at: datetime = Field(default_factory=utcnow)
    status: str = "RECORDED"  # RECORDED | ADJUSTED | DISPUTED
    notes: Optional[str] = None


class EsgMetric(TimestampMixin, table=True):
    """ESG / utilities tracking without IoT sensors — manual or integration readings."""

    __tablename__ = "esg_metrics"

    metric_id: str = Field(default_factory=lambda: new_id("esg_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    metric_type: str  # ENERGY_KWH | WATER_KL | WASTE_KG | CARBON_TCO2E | PAPER_REAMS
    period: str
    value: float = 0.0
    unit: str = ""
    source: str = "MANUAL"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))
