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


class Person(TimestampMixin, table=True):
    __tablename__ = "persons"

    person_id: str = Field(default_factory=lambda: new_id("per_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    email: str = Field(index=True, unique=True)
    name: str
    role: str = "EMPLOYEE"
    department: Optional[str] = None
    manager_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    site_id: Optional[str] = Field(default=None, foreign_key="locations.location_id")
    is_active: bool = True
    password_hash: Optional[str] = None  # only for prototype admin/operators


class Location(TimestampMixin, table=True):
    __tablename__ = "locations"

    location_id: str = Field(default_factory=lambda: new_id("loc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    parent_id: Optional[str] = Field(default=None, foreign_key="locations.location_id")
    type: str  # SITE/FLOOR/ZONE/ROOM
    name: str
    alias: Optional[str] = None
    site_id: Optional[str] = Field(default=None, index=True)


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
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


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
    __tablename__ = "vendors"

    vendor_id: str = Field(default_factory=lambda: new_id("ven_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    name: str
    category: str
    contact_email: str
    location: Optional[str] = None
    status: str = "ACTIVE"
    approved_services: list = Field(default_factory=list, sa_column=Column(JSON))
    pricing: dict = Field(default_factory=dict, sa_column=Column(JSON))


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
    code: str
    category: str
    description: str
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    is_active: bool = True


class NotificationTemplate(TimestampMixin, table=True):
    __tablename__ = "notification_templates"

    template_id: str = Field(default_factory=lambda: new_id("ntpl_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str
    communication_type: str
    subject_template: str
    body_template: str = Field(sa_column=Column(Text))
    is_active: bool = True
