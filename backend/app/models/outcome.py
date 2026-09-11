from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.org import TimestampMixin, new_id, utcnow


class Outcome(TimestampMixin, table=True):
    __tablename__ = "outcomes"
    __table_args__ = (UniqueConstraint("case_reference", name="uq_case_reference"),)

    outcome_id: str = Field(default_factory=lambda: new_id("out_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    case_reference: str = Field(index=True)
    template_id: Optional[str] = Field(default=None, foreign_key="outcome_templates.template_id")
    template_code: str
    category: str
    title: str
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    owner_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    requester_email: Optional[str] = None
    requester_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    status: str = "DRAFT"
    readiness_pct: float = 0.0
    joining_day_readiness_pct: Optional[float] = None
    permanent_readiness_pct: Optional[float] = None
    due_at: Optional[datetime] = None
    business_event_id: Optional[str] = Field(default=None, foreign_key="raw_email_events.event_id")
    conversation_id: Optional[str] = Field(
        default=None, foreign_key="conversations.conversation_id", index=True
    )
    priority: str = "MEDIUM"
    facts: dict = Field(default_factory=dict, sa_column=Column(JSON))
    blockers: list = Field(default_factory=list, sa_column=Column(JSON))
    closed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class Requirement(TimestampMixin, table=True):
    __tablename__ = "requirements"

    requirement_id: str = Field(default_factory=lambda: new_id("req_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: str = Field(foreign_key="outcomes.outcome_id", index=True)
    code: str
    title: str
    applicability: str = "REQUIRED"
    status: str = "REQUIRED"
    is_mandatory: bool = True
    is_blocker: bool = False
    evidence_rule: Optional[str] = None
    evidence_required: bool = False
    notes: Optional[str] = None


class Task(TimestampMixin, table=True):
    __tablename__ = "tasks"

    task_id: str = Field(default_factory=lambda: new_id("tsk_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: str = Field(foreign_key="outcomes.outcome_id", index=True)
    requirement_id: Optional[str] = Field(default=None, foreign_key="requirements.requirement_id")
    code: str
    title: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    owner_role: Optional[str] = None
    owner_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    status: str = "NOT_STARTED"
    due_at: Optional[datetime] = None
    sla_hours: int = 48
    task_group: Optional[str] = None
    is_mandatory: bool = True
    evidence_required: bool = False
    depends_on_task_codes: list = Field(default_factory=list, sa_column=Column(JSON))
    blocked_by: list = Field(default_factory=list, sa_column=Column(JSON))
    is_blocked: bool = False
    resolution: Optional[str] = Field(default=None, sa_column=Column(Text))
    completed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class TaskDependency(TimestampMixin, table=True):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)

    dependency_id: str = Field(default_factory=lambda: new_id("dep_"), primary_key=True)
    task_id: str = Field(foreign_key="tasks.task_id", index=True)
    depends_on_task_id: str = Field(foreign_key="tasks.task_id", index=True)
    dependency_type: str = "BLOCKS"


class Approval(TimestampMixin, table=True):
    __tablename__ = "approvals"

    approval_id: str = Field(default_factory=lambda: new_id("apr_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.task_id")
    approval_type: str
    approver_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    approver_role: Optional[str] = None
    decision: str = "PENDING"
    reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    decided_at: Optional[datetime] = None
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))


class ExceptionRecord(TimestampMixin, table=True):
    __tablename__ = "exceptions"

    exception_id: str = Field(default_factory=lambda: new_id("exc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.task_id")
    exception_type: str
    severity: str = "MEDIUM"
    title: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    owner_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    owner_role: Optional[str] = None
    status: str = "OPEN"
    options: list = Field(default_factory=list, sa_column=Column(JSON))
    resolution: Optional[str] = Field(default=None, sa_column=Column(Text))
    resolved_at: Optional[datetime] = None


class Evidence(TimestampMixin, table=True):
    __tablename__ = "evidence"

    evidence_id: str = Field(default_factory=lambda: new_id("evd_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.task_id")
    requirement_id: Optional[str] = Field(default=None, foreign_key="requirements.requirement_id")
    evidence_type: str
    file_path: Optional[str] = None
    record_ref: Optional[str] = None
    description: Optional[str] = None
    status: str = "SUBMITTED"
    submitted_by: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    verifier_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    verified_at: Optional[datetime] = None
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Communication(TimestampMixin, table=True):
    __tablename__ = "communications"

    message_id: str = Field(default_factory=lambda: new_id("msg_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    conversation_id: Optional[str] = Field(
        default=None, foreign_key="conversations.conversation_id", index=True
    )
    outcome_id: Optional[str] = Field(default=None, foreign_key="outcomes.outcome_id")
    thread_id: Optional[str] = None
    gmail_message_id: Optional[str] = None  # legacy
    provider_message_id: Optional[str] = None
    communication_type: str
    sender: str
    recipients: list = Field(default_factory=list, sa_column=Column(JSON))
    subject: str
    body: str = Field(sa_column=Column(Text))
    idempotency_key: Optional[str] = Field(default=None, unique=True, index=True)
    sent_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    audit_id: str = Field(default_factory=lambda: new_id("aud_"), primary_key=True)
    tenant_id: str = Field(index=True)
    actor: str
    action: str
    entity_type: str
    entity_id: str
    before: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    after: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    source: str = "SYSTEM"
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=utcnow, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class VendorIssue(TimestampMixin, table=True):
    __tablename__ = "vendor_issues"

    issue_id: str = Field(default_factory=lambda: new_id("vis_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: str = Field(foreign_key="outcomes.outcome_id", index=True)
    issue_type: str
    workstream: str
    title: str
    allegation_status: str = "UNVERIFIED"
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    severity: str = "MEDIUM"
