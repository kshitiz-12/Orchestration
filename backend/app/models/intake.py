from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field

from app.models.org import TimestampMixin, new_id, utcnow


class RawEmailEvent(TimestampMixin, table=True):
    """Immutable storage of original email before any AI processing."""

    __tablename__ = "raw_email_events"
    __table_args__ = (
        UniqueConstraint("source", "provider_message_id", name="uq_source_provider_message"),
    )

    event_id: str = Field(default_factory=lambda: new_id("evt_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    processing_id: str = Field(default_factory=lambda: new_id("proc_"), index=True, unique=True)
    idempotency_key: str = Field(index=True, unique=True)

    # Provider-agnostic identifiers (Outlook conversationId, Gmail threadId, …)
    provider: str = Field(default="OUTLOOK", index=True)
    provider_message_id: str = Field(index=True)
    provider_conversation_id: Optional[str] = Field(default=None, index=True)

    # Legacy aliases — dual-written for compatibility with earlier prototype columns
    gmail_message_id: str = Field(index=True)
    gmail_thread_id: Optional[str] = Field(default=None, index=True)

    source: str = "OUTLOOK"
    sender: str
    recipients: list = Field(default_factory=list, sa_column=Column(JSON))
    cc: list = Field(default_factory=list, sa_column=Column(JSON))
    subject: str = ""
    body_text: str = Field(default="", sa_column=Column(Text))
    body_html: Optional[str] = Field(default=None, sa_column=Column(Text))
    body_for_ai: str = Field(default="", sa_column=Column(Text))
    received_at: datetime = Field(default_factory=utcnow, index=True)
    attachments: list = Field(default_factory=list, sa_column=Column(JSON))
    headers: dict = Field(default_factory=dict, sa_column=Column(JSON))
    safety_flags: dict = Field(default_factory=dict, sa_column=Column(JSON))
    processing_stage: str = "INTAKE"
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversations.conversation_id")
    deduplicated: bool = False


class Conversation(TimestampMixin, table=True):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("tenant_id", "thread_id", name="uq_tenant_thread"),)

    conversation_id: str = Field(default_factory=lambda: new_id("conv_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    thread_id: str = Field(index=True)
    requester_email: str = Field(index=True)
    requester_person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    current_outcome_id: Optional[str] = Field(default=None, index=True)
    status: str = "OPEN"
    subject: str = ""
    facts: dict = Field(default_factory=dict, sa_column=Column(JSON))
    missing_information: list = Field(default_factory=list, sa_column=Column(JSON))


class ProcessingJob(TimestampMixin, table=True):
    __tablename__ = "processing_jobs"

    job_id: str = Field(default_factory=lambda: new_id("job_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    job_type: str
    status: str = "PENDING"
    event_id: Optional[str] = Field(default=None, foreign_key="raw_email_events.event_id", index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    idempotency_key: str = Field(index=True)
    attempts: int = 0
    max_attempts: int = 5
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text))
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    available_at: datetime = Field(default_factory=utcnow, index=True)
    completed_at: Optional[datetime] = None
    stage: str = "QUEUED"


class DownstreamAction(TimestampMixin, table=True):
    __tablename__ = "downstream_actions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_downstream_idempotency"),)

    action_id: str = Field(default_factory=lambda: new_id("act_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    action_type: str
    idempotency_key: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    status: str = "SUCCEEDED"
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))


class AIDecision(TimestampMixin, table=True):
    __tablename__ = "ai_decisions"

    decision_id: str = Field(default_factory=lambda: new_id("aid_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    event_id: Optional[str] = Field(default=None, foreign_key="raw_email_events.event_id", index=True)
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversations.conversation_id")
    model: str
    model_version: str
    prompt_version: str
    confidence: float = 0.0
    output: dict = Field(default_factory=dict, sa_column=Column(JSON))
    recommendation: Optional[str] = None
    rationale: Optional[str] = Field(default=None, sa_column=Column(Text))
    route: str = "AUTO"
    human_corrected: bool = False
    correction: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    corrected_by: Optional[str] = None


class HumanReviewItem(TimestampMixin, table=True):
    __tablename__ = "human_review_queue"

    review_id: str = Field(default_factory=lambda: new_id("rev_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    event_id: str = Field(foreign_key="raw_email_events.event_id", index=True)
    conversation_id: Optional[str] = Field(default=None, foreign_key="conversations.conversation_id")
    ai_decision_id: Optional[str] = Field(default=None, foreign_key="ai_decisions.decision_id")
    status: str = "PENDING"
    reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    assigned_to: Optional[str] = Field(default=None, foreign_key="persons.person_id")
    resolution: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    resolved_at: Optional[datetime] = None
