from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    key: str
    value: Any
    confidence: float = 0.0
    source_span: Optional[str] = None


class ExtractedIssue(BaseModel):
    issue_type: str
    summary: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    entities: dict[str, Any] = Field(default_factory=dict)


class MissingInformation(BaseModel):
    field: str
    question: str
    blocking: bool = True


class ExtractionResult(BaseModel):
    """Structured AI output — extensible for all prototype scenarios."""

    event_type: str = Field(
        description="ONBOARDING | PARKING_CONFLICT | FURNITURE_ISSUE | VENDOR_ESCALATION | INVOICE | MEETING_ROOM | GENERAL | UNKNOWN"
    )
    category: str = ""
    summary: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    issues: list[ExtractedIssue] = Field(default_factory=list)
    missing_information: list[MissingInformation] = Field(default_factory=list)
    safety_concern: bool = False
    financial_action: bool = False
    access_control_action: bool = False
    vendor_sanction: bool = False
    recommended_priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    recommended_next_action: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    human_review_required: bool = False
    reason: str = ""
    is_reply: bool = False
    clarification_questions: list[str] = Field(default_factory=list)


class ConfidenceRoutingResult(BaseModel):
    route: Literal["AUTO", "OPERATOR_REVIEW", "CLARIFICATION", "HUMAN_REQUIRED"]
    reasons: list[str] = Field(default_factory=list)
    extraction: ExtractionResult
