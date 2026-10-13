from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    # Naive UTC for SQLite compatibility (avoid aware/naive compare errors)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id(prefix: str = "") -> str:
    uid = uuid4().hex[:12]
    return f"{prefix}{uid}" if prefix else uid


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class Tenant(TimestampMixin, table=True):
    __tablename__ = "tenants"

    tenant_id: str = Field(default_factory=lambda: new_id("ten_"), primary_key=True)
    name: str
    region: str = "IN"
    status: str = "ACTIVE"
    default_timezone: str = "Asia/Kolkata"
    default_currency: str = "INR"
    retention_profile: Optional[str] = None


class LegalEntity(TimestampMixin, table=True):
    """Books / tax / approval scope inside a tenant (V3 multi-entity)."""

    __tablename__ = "legal_entities"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_legal_entity_code"),)

    entity_id: str = Field(default_factory=lambda: new_id("ent_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str = Field(index=True)
    legal_name: str
    country: str = "IN"
    currency: str = "INR"
    tax_ids: dict = Field(default_factory=dict, sa_column=Column(JSON))
    registrations: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "ACTIVE"
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


class Person(TimestampMixin, table=True):
    __tablename__ = "persons"

    person_id: str = Field(default_factory=lambda: new_id("per_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, foreign_key="legal_entities.entity_id", index=True)
    email: str = Field(index=True, unique=True)
    name: str
    role: str = "EMPLOYEE"
    department: Optional[str] = None
    manager_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    site_id: Optional[str] = Field(default=None, foreign_key="locations.location_id")
    # Extra sites the user may operate (BRANCH_ADMIN / site-scoped ops); empty = home site only / all for company admin
    allowed_site_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    is_active: bool = True
    password_hash: Optional[str] = None


class Location(TimestampMixin, table=True):
    __tablename__ = "locations"

    location_id: str = Field(default_factory=lambda: new_id("loc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    parent_id: Optional[str] = Field(default=None, foreign_key="locations.location_id")
    # REGION/CITY/BRANCH/BUILDING/FLOOR/ZONE/ROOM/DESK (SITE kept for older rows); see app.agent.places
    type: str
    name: str
    code: Optional[str] = Field(default=None, index=True)
    # Other names people use for it, separated by ';' (e.g. "BLR WF; Whitefield office")
    alias: Optional[str] = None
    site_id: Optional[str] = Field(default=None, index=True)
    # facilities.docx §2.3 location master (address, cost centre, owner, criticality, service bundle).
    # Lease/real-estate commercial fields intentionally omitted.
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Resource(TimestampMixin, table=True):
    __tablename__ = "resources"

    resource_id: str = Field(default_factory=lambda: new_id("res_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    type: str
    name: str
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id")
    status: str = "AVAILABLE"
    allocated_to_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class RoomBooking(TimestampMixin, table=True):
    """One hold or confirmed booking of a room (or off-site venue) for a time window."""

    __tablename__ = "room_bookings"

    booking_id: str = Field(default_factory=lambda: new_id("bkg_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    resource_id: Optional[str] = Field(default=None, foreign_key="resources.resource_id", index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    room_name: str
    # HELD (proposed, awaiting confirm) | CONFIRMED | RELEASED | CANCELLED | EXPIRED
    status: str = Field(default="HELD", index=True)
    starts_at: Optional[datetime] = Field(default=None, index=True)
    ends_at: Optional[datetime] = Field(default=None, index=True)
    hold_expires_at: Optional[datetime] = Field(default=None, index=True)
    reminder_sent_at: Optional[datetime] = None
    is_offsite: bool = False
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Asset(TimestampMixin, table=True):
    __tablename__ = "assets"

    asset_id: str = Field(default_factory=lambda: new_id("ast_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    type: str
    name: str
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id")
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id")
    contract_id: Optional[str] = Field(default=None, foreign_key="contracts.contract_id")
    status: str = "ACTIVE"
    assignee_email: Optional[str] = Field(default=None, index=True)
    tag: Optional[str] = Field(default=None, index=True)
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class StockSku(TimestampMixin, table=True):
    """Branch/store SKU for supplies — qty + reorder mins for mail-driven auto reorder.

    Item-master depth (facilities.docx §6.2) lives in attributes + typed flags below.
    """

    __tablename__ = "stock_skus"
    __table_args__ = (UniqueConstraint("tenant_id", "sku_code", "location_id", name="uq_stock_sku_place"),)

    sku_id: str = Field(default_factory=lambda: new_id("sku_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    sku_code: str = Field(index=True)
    name: str
    category: Optional[str] = Field(default=None, index=True)
    qty_on_hand: float = 0.0
    qty_reserved: float = 0.0
    reorder_min: float = 0.0
    reorder_qty: float = 0.0
    safety_stock: float = 0.0
    max_stock: float = 0.0
    unit: str = "each"
    pack_size: float = 1.0
    bin_code: Optional[str] = None
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
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id")
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class StockReservation(TimestampMixin, table=True):
    """Soft hold against SKU available qty until issue or release."""

    __tablename__ = "stock_reservations"

    reservation_id: str = Field(default_factory=lambda: new_id("sres_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    sku_id: str = Field(foreign_key="stock_skus.sku_id", index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    quantity: float
    status: str = "HELD"  # HELD | ISSUED | RELEASED | EXPIRED
    notes: Optional[str] = None


class ServiceCatalog(TimestampMixin, table=True):
    __tablename__ = "services"

    service_id: str = Field(default_factory=lambda: new_id("svc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    category: str
    name: str
    mandatory_questions: list = Field(default_factory=list, sa_column=Column(JSON))
    sla_hours: int = 48
    owner_role: str = "ADMIN"
    evidence_rules: list = Field(default_factory=list, sa_column=Column(JSON))


class Vendor(TimestampMixin, table=True):
    """Operational vendor master + BFSI lifecycle fields (invite → verify → activate).

    Desk / resolution / stock only use status=ACTIVE. Lifecycle states stay out of day-to-day ops.
    """

    __tablename__ = "vendors"

    vendor_id: str = Field(default_factory=lambda: new_id("ven_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, foreign_key="legal_entities.entity_id", index=True)
    name: str
    category: str
    contact_email: str
    location: Optional[str] = None
    # INVITED | UNDER_REVIEW | ACTIVE | SUSPENDED | BLACKLISTED
    status: str = "ACTIVE"
    approved_services: list = Field(default_factory=list, sa_column=Column(JSON))
    pricing: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Lifecycle / BFSI profile (additive — empty until onboarding)
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None
    msme_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    registered_address: Optional[str] = None
    coverage_states: list = Field(default_factory=list, sa_column=Column(JSON))
    coverage_cities: list = Field(default_factory=list, sa_column=Column(JSON))
    coverage_location_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    documents: dict = Field(default_factory=dict, sa_column=Column(JSON))
    compliance: dict = Field(default_factory=dict, sa_column=Column(JSON))
    references: list = Field(default_factory=list, sa_column=Column(JSON))
    manpower: dict = Field(default_factory=dict, sa_column=Column(JSON))
    equipment: list = Field(default_factory=list, sa_column=Column(JSON))
    financial: dict = Field(default_factory=dict, sa_column=Column(JSON))
    sla_terms: dict = Field(default_factory=dict, sa_column=Column(JSON))
    score: Optional[float] = None
    score_breakdown: dict = Field(default_factory=dict, sa_column=Column(JSON))
    vendor_tier: Optional[str] = None  # PREFERRED | APPROVED | CONDITIONAL
    invite_token: Optional[str] = Field(default=None, index=True)
    invite_expires_at: Optional[datetime] = None
    registration_submitted_at: Optional[datetime] = None
    invited_by: Optional[str] = None
    invited_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    suspended_reason: Optional[str] = None
    notes: Optional[str] = None
    contract_id: Optional[str] = None  # set on activate when a Contract row is created


class VendorCoverage(TimestampMixin, table=True):
    """State/city/office coverage for multi-location BFSI vendors."""

    __tablename__ = "vendor_coverage"

    coverage_id: str = Field(default_factory=lambda: new_id("vcov_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    vendor_id: str = Field(foreign_key="vendors.vendor_id", index=True)
    state: Optional[str] = None
    city: Optional[str] = None
    location_id: Optional[str] = Field(default=None, foreign_key="locations.location_id", index=True)
    team_count: int = 0
    notes: Optional[str] = None


class Contract(TimestampMixin, table=True):
    __tablename__ = "contracts"

    contract_id: str = Field(default_factory=lambda: new_id("ctr_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    vendor_id: str = Field(foreign_key="vendors.vendor_id", index=True)
    name: str
    rate_card: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "ACTIVE"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PurchaseOrder(TimestampMixin, table=True):
    __tablename__ = "purchase_orders"

    po_id: str = Field(default_factory=lambda: new_id("po_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    vendor_id: str = Field(foreign_key="vendors.vendor_id", index=True)
    po_number: str = Field(unique=True, index=True)
    description: str
    quantity: float
    unit_rate: float
    currency: str = "INR"
    status: str = "OPEN"
    contract_id: Optional[str] = Field(default=None, foreign_key="contracts.contract_id")


class Receipt(TimestampMixin, table=True):
    __tablename__ = "receipts"

    receipt_id: str = Field(default_factory=lambda: new_id("rcp_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    po_id: str = Field(foreign_key="purchase_orders.po_id", index=True)
    quantity_received: float
    received_date: str
    status: str = "CONFIRMED"
    notes: Optional[str] = None


class Invoice(TimestampMixin, table=True):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number", "vendor_id", name="uq_invoice_vendor"),)

    invoice_id: str = Field(default_factory=lambda: new_id("inv_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id")
    po_id: Optional[str] = Field(default=None, foreign_key="purchase_orders.po_id")
    receipt_id: Optional[str] = Field(default=None, foreign_key="receipts.receipt_id")
    invoice_number: str = Field(index=True)
    amount: float = 0.0
    quantity: float = 0.0
    unit_rate: float = 0.0
    currency: str = "INR"
    match_status: str = "PENDING_REVIEW"
    bank_details_changed: bool = False
    file_hash: Optional[str] = None
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id")
    erp_handoff_status: str = "NOT_STARTED"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class OutcomeTemplate(TimestampMixin, table=True):
    __tablename__ = "outcome_templates"

    template_id: str = Field(default_factory=lambda: new_id("tpl_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str = Field(index=True)
    name: str
    category: str
    case_prefix: str  # ONB, PARK, VND, INV
    requirements: list = Field(default_factory=list, sa_column=Column(JSON))
    tasks: list = Field(default_factory=list, sa_column=Column(JSON))
    mandatory_fields: list = Field(default_factory=list, sa_column=Column(JSON))
    evidence_rules: list = Field(default_factory=list, sa_column=Column(JSON))
    approval_rules: list = Field(default_factory=list, sa_column=Column(JSON))
    notification_rules: list = Field(default_factory=list, sa_column=Column(JSON))
    is_active: bool = True


class BusinessRule(TimestampMixin, table=True):
    __tablename__ = "business_rules"

    rule_id: str = Field(default_factory=lambda: new_id("rul_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, foreign_key="legal_entities.entity_id", index=True)
    code: str
    category: str
    description: str
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    version: int = 1
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    is_active: bool = True


class PolicyRule(TimestampMixin, table=True):
    """Versioned policy / entitlement rule (V3 control-engine input)."""

    __tablename__ = "policy_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "code", "version", name="uq_policy_rule_version"),)

    policy_id: str = Field(default_factory=lambda: new_id("pol_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, foreign_key="legal_entities.entity_id", index=True)
    code: str = Field(index=True)
    name: str
    rule_family: str  # ELIGIBILITY | APPROVAL | SLA | RATE | BUDGET | EVIDENCE | COMMUNICATION
    owner_role: str = "COMPANY_ADMIN"
    condition: dict = Field(default_factory=dict, sa_column=Column(JSON))
    decision: dict = Field(default_factory=dict, sa_column=Column(JSON))
    reason_template: Optional[str] = None
    priority: int = 100
    version: int = 1
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    is_active: bool = True


class Budget(TimestampMixin, table=True):
    """Entity / cost-centre / period budget master (operational reservation; ERP remains SoR for books)."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_id", "cost_centre", "category", "period", name="uq_budget_scope"),
    )

    budget_id: str = Field(default_factory=lambda: new_id("bud_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, foreign_key="legal_entities.entity_id", index=True)
    cost_centre: Optional[str] = None
    category: str = "OPEX"
    period: str  # e.g. 2026-Q1 or 2026-04
    currency: str = "INR"
    original_amount: float = 0.0
    revised_amount: float = 0.0
    reserved_amount: float = 0.0
    committed_amount: float = 0.0
    actual_amount: float = 0.0
    accrued_amount: float = 0.0  # consumed but unbilled (facilities.docx §7.3)
    status: str = "ACTIVE"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class OutboxEvent(TimestampMixin, table=True):
    """Transactional outbox for notifications / integration publish (idempotent consumers)."""

    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_outbox_idempotency"),)

    outbox_id: str = Field(default_factory=lambda: new_id("obx_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    event_type: str = Field(index=True)
    aggregate_type: Optional[str] = None
    aggregate_id: Optional[str] = Field(default=None, index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    idempotency_key: str = Field(index=True)
    status: str = Field(default="PENDING", index=True)  # PENDING | SENT | FAILED | DEAD
    attempts: int = 0
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))
    available_at: datetime = Field(default_factory=utcnow, index=True)
    sent_at: Optional[datetime] = None


class NotificationTemplate(TimestampMixin, table=True):
    __tablename__ = "notification_templates"

    template_id: str = Field(default_factory=lambda: new_id("ntpl_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str
    communication_type: str
    subject_template: str
    body_template: str = Field(sa_column=Column(Text))
    is_active: bool = True
