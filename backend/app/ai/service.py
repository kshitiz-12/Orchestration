from typing import Optional

from app.ai.base import LLMProvider
from app.ai.gemini import GeminiProvider, HeuristicProvider
from app.core.config import get_settings
from app.core.enums import ConfidenceRoute
from app.core.logging import get_logger
from app.schemas.ai import ConfidenceRoutingResult, ExtractionResult

logger = get_logger(__name__)


def _looks_like_meeting_room(subject: str, body: str) -> bool:
    text = f"{subject}\n{body}".lower()
    keys = [
        "meeting room",
        "conference room",
        "book a room",
        "need a room",
        "need a meeting",
        "room booking",
        "meeting space",
        "information required",
        "evt-",
    ]
    if any(k in text for k in keys):
        return True
    return ("room" in text or "meeting" in text or "members" in text) and any(
        k in text for k in ["people", "attendees", "members", "pm", "am", "hours", "tomorrow"]
    )


class LLMService:
    """AI gateway. Business logic consumes this — never GeminiProvider directly."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        settings = get_settings()
        if provider is not None:
            self.provider = provider
        elif settings.gemini_api_key:
            self.provider = GeminiProvider()
        else:
            logger.warning("gemini_api_key_missing_using_heuristic_provider")
            self.provider = HeuristicProvider()

    def extract(self, **kwargs) -> ExtractionResult:
        subject = kwargs.get("subject") or ""
        body = kwargs.get("body") or ""
        try:
            result = self.provider.extract(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.error("ai_extraction_failed", error=str(exc))
            fallback = HeuristicProvider()
            result = fallback.extract(**kwargs)
            result.human_review_required = True
            result.reason = f"Primary AI unavailable ({exc}); heuristic fallback used"
            result.confidence = min(result.confidence, 0.6)
            return result

        # Enrich weak Gemini results for clear meeting-room prototypes
        if result.event_type in {"UNKNOWN", "GENERAL"} and _looks_like_meeting_room(subject, body):
            heuristic = HeuristicProvider().extract(**kwargs)
            if heuristic.event_type == "MEETING_ROOM":
                logger.info("ai_enriched_with_meeting_room_heuristic")
                result.event_type = "MEETING_ROOM"
                result.category = "MEETING_ROOM"
                result.entities = {**(result.entities or {}), **(heuristic.entities or {})}
                if not result.missing_information and heuristic.missing_information:
                    result.missing_information = heuristic.missing_information
                if not result.clarification_questions and heuristic.clarification_questions:
                    result.clarification_questions = heuristic.clarification_questions
                result.confidence = max(result.confidence, heuristic.confidence)
                result.reason = (result.reason or "") + " | enriched with meeting-room heuristic"
                if heuristic.missing_information and any(m.blocking for m in heuristic.missing_information):
                    result.recommended_next_action = "clarification"
        return result

    def route(self, extraction: ExtractionResult) -> ConfidenceRoutingResult:
        reasons: list[str] = []
        sensitive = (
            extraction.safety_concern
            or extraction.financial_action
            or extraction.access_control_action
            or extraction.vendor_sanction
            or extraction.human_review_required
        )
        has_blocking = extraction.missing_information and any(
            m.blocking for m in extraction.missing_information
        )

        if sensitive:
            route = ConfidenceRoute.HUMAN_REQUIRED
            reasons.append("Sensitive action class requires human review")
        elif has_blocking or extraction.confidence < 0.65:
            route = ConfidenceRoute.CLARIFICATION
            if has_blocking:
                reasons.append("Blocking missing information present")
            if extraction.confidence < 0.65:
                reasons.append("Confidence below 0.65")
        elif extraction.confidence < 0.85:
            route = ConfidenceRoute.OPERATOR_REVIEW
            reasons.append("Confidence between 0.65 and 0.84")
        else:
            route = ConfidenceRoute.AUTO

        return ConfidenceRoutingResult(route=route.value, reasons=reasons, extraction=extraction)
