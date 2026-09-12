from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

# Use plain str for emails — prototype domains like *.demo / *.local are intentional



class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class EmailIngestRequest(BaseModel):
    """Manual/demo email intake (also used when Gmail is unavailable)."""

    message_id: str
    thread_id: str
    sender: str
    recipients: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    received_at: Optional[datetime] = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    headers: dict[str, Any] = Field(default_factory=dict)


class TaskStatusUpdate(BaseModel):
    status: str
    resolution: Optional[str] = None


class ConfirmBookingRequest(BaseModel):
    """Operator confirms a meeting-room request and emails the requester."""

    room_name: Optional[str] = None
    note: Optional[str] = None


class EvidenceCreate(BaseModel):
    evidence_type: str
    description: Optional[str] = None
    record_ref: Optional[str] = None
    task_id: Optional[str] = None
    requirement_id: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    decision: str
    reason: Optional[str] = None


class HumanReviewDecision(BaseModel):
    action: str  # ACCEPT | CORRECT | CLARIFY | REJECT
    corrected_extraction: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    assign_to: Optional[str] = None


class ExceptionResolveRequest(BaseModel):
    resolution: str
    selected_option: Optional[str] = None
    status: str = "RESOLVED"
