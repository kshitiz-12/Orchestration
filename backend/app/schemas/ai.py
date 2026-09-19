from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

_PRIORITY_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})


def _normalize_priority(value: Any) -> str:
    """LLMs often emit 'medium' — coerce at the contract boundary, never fail the turn."""
    if value is None or value == "":
        return "MEDIUM"
    text = str(value).strip().upper()
    return text if text in _PRIORITY_LEVELS else "MEDIUM"


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

    @field_validator("severity", mode="before")
    @classmethod
    def coerce_severity(cls, value: Any) -> str:
        return _normalize_priority(value)


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
    fact_delta: dict[str, Any] = Field(
        default_factory=dict,
        description="Interpreter delta: {set, unset, assumptions, speech_acts}",
    )
    open_requests: list[Any] = Field(
        default_factory=list,
        description="User asks that are not known booking fields — never drop these.",
    )

    @field_validator("recommended_priority", mode="before")
    @classmethod
    def coerce_priority(cls, value: Any) -> str:
        return _normalize_priority(value)

    @field_validator("event_type", mode="before")
    @classmethod
    def coerce_event_type(cls, value: Any) -> str:
        if value is None or value == "":
            return "UNKNOWN"
        return str(value).strip().upper()


class ConfidenceRoutingResult(BaseModel):
    route: Literal["AUTO", "OPERATOR_REVIEW", "CLARIFICATION", "HUMAN_REQUIRED"]
    reasons: list[str] = Field(default_factory=list)
    extraction: ExtractionResult
