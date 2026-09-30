from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field

from app.models.org import TimestampMixin, new_id


class Department(TimestampMixin, table=True):
    """A team that receives work orders. The main admin mailbox stays in env (ADMIN_OPS_EMAIL)."""

    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_department_code"),)

    department_id: str = Field(default_factory=lambda: new_id("dep_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    code: str = Field(index=True)
    name: str
    # Request categories this team handles, e.g. ["maintenance", "housekeeping"]
    categories: list = Field(default_factory=list, sa_column=Column(JSON))
    primary_email: Optional[str] = None
    backup_emails: list = Field(default_factory=list, sa_column=Column(JSON))
    approver_email: Optional[str] = None
    sla_hours: int = 24
    spend_approval_limit: float = 0.0
    is_active: bool = True
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class KnowledgeEntry(TimestampMixin, table=True):
    """Office knowledge the AI admin answers from (company profile, offices, policies, FAQs)."""

    __tablename__ = "knowledge_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_knowledge_key"),)

    entry_id: str = Field(default_factory=lambda: new_id("kb_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    key: str = Field(index=True)
    section: str = "faq"
    title: str
    content: str = Field(sa_column=Column(Text))
    is_active: bool = True


class ServiceTicket(TimestampMixin, table=True):
    __tablename__ = "service_tickets"

    ticket_id: str = Field(default_factory=lambda: new_id("tkt_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    reference: str = Field(index=True)
    category: str = Field(index=True)
    title: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    location: Optional[str] = None
    priority: str = "MEDIUM"
    # OPEN | AWAITING_APPROVAL | ASSIGNED | IN_PROGRESS | RESOLVED | CLOSED | CANCELLED | REJECTED
    status: str = Field(default="OPEN", index=True)
    department_code: Optional[str] = None
    assignee_email: Optional[str] = None
    requester_email: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))


class VisitorPass(TimestampMixin, table=True):
    __tablename__ = "visitor_passes"

    pass_id: str = Field(default_factory=lambda: new_id("vis_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    pass_code: str = Field(index=True)
    visitor_name: str
    company: Optional[str] = None
    host_email: Optional[str] = None
    visit_date: Optional[str] = Field(default=None, index=True)
    visit_time: Optional[str] = None
    office: Optional[str] = None
    vehicle_number: Optional[str] = None
    parking_slot: Optional[str] = None
    purpose: Optional[str] = None
    status: str = "REGISTERED"
