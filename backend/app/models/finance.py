"""Financial / commercial states — separate from OpsLedger (V3 §29.5).

OpsLedger = operational typed spend.
CostRequirement / SES / Invoice ERP status = commercial & accounting truth references.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field

from app.models.org import TimestampMixin, new_id, utcnow


class CostRequirement(TimestampMixin, table=True):
    """Estimated / reserved / approved / committed cost for an outcome (not payment)."""

    __tablename__ = "cost_requirements"

    cost_id: str = Field(default_factory=lambda: new_id("cost_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id", index=True)
    budget_id: Optional[str] = Field(default=None, foreign_key="budgets.budget_id", index=True)
    category: str = "OPEX"
    currency: str = "INR"
    estimated_amount: float = 0.0
    reserved_amount: float = 0.0
    approved_amount: float = 0.0
    committed_amount: float = 0.0
    reported_amount: float = 0.0
    invoiced_amount: float = 0.0
    posted_amount: float = 0.0
    paid_amount: float = 0.0
    status: str = "DRAFT"  # DRAFT | RESERVED | APPROVED | COMMITTED | PARTIAL | CLOSED | CANCELLED
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ServiceEntry(TimestampMixin, table=True):
    """SES — service entry sheet against PO/contract (services counterpart to GRN)."""

    __tablename__ = "service_entries"

    ses_id: str = Field(default_factory=lambda: new_id("ses_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    po_id: Optional[str] = Field(default=None, foreign_key="purchase_orders.po_id", index=True)
    contract_id: Optional[str] = Field(default=None, foreign_key="contracts.contract_id", index=True)
    vendor_id: Optional[str] = Field(default=None, foreign_key="vendors.vendor_id", index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    quantity: float = 0.0
    unit_rate: float = 0.0
    amount: float = 0.0
    currency: str = "INR"
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    status: str = "DRAFT"  # DRAFT | SUBMITTED | ACCEPTED | REJECTED
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    accepted_at: Optional[datetime] = None


class ErpHandoff(TimestampMixin, table=True):
    """ERP post/pay status — AdminServices never invents payment completion."""

    __tablename__ = "erp_handoffs"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_erp_handoff_idem"),)

    handoff_id: str = Field(default_factory=lambda: new_id("erp_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    invoice_id: Optional[str] = Field(default=None, foreign_key="invoices.invoice_id", index=True)
    cost_id: Optional[str] = Field(default=None, foreign_key="cost_requirements.cost_id", index=True)
    direction: str = "OUTBOUND"  # OUTBOUND post | INBOUND status
    erp_system: str = "ERP"
    erp_document_ref: Optional[str] = None
    status: str = "NOT_STARTED"  # NOT_STARTED | QUEUED | SENT | ACCEPTED | REJECTED | PAID | FAILED
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))
    idempotency_key: str = Field(index=True)
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
