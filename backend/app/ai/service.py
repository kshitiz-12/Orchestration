from typing import Optional

from app.ai.base import LLMProvider
from app.ai.gemini import GeminiProvider, HeuristicProvider
from app.core.config import get_settings
from app.core.enums import ConfidenceRoute
from app.core.logging import get_logger
from app.schemas.ai import ConfidenceRoutingResult, ExtractionResult

logger = get_logger(__name__)


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
        try:
            return self.provider.extract(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.error("ai_extraction_failed", error=str(exc))
            # Fall back to heuristic so original event is not lost
            fallback = HeuristicProvider()
            result = fallback.extract(**kwargs)
            result.human_review_required = True
            result.reason = f"Primary AI unavailable ({exc}); heuristic fallback used"
            result.confidence = min(result.confidence, 0.6)
            return result

    def route(self, extraction: ExtractionResult) -> ConfidenceRoutingResult:
        reasons: list[str] = []
        route = ConfidenceRoute.AUTO

        if (
            extraction.safety_concern
            or extraction.financial_action
            or extraction.access_control_action
            or extraction.vendor_sanction
            or extraction.human_review_required
        ):
            route = ConfidenceRoute.HUMAN_REQUIRED
            reasons.append("Sensitive action class requires human review")

        if extraction.confidence < 0.65:
            route = ConfidenceRoute.CLARIFICATION
            reasons.append("Confidence below 0.65")
        elif extraction.confidence < 0.85 and route == ConfidenceRoute.AUTO:
            route = ConfidenceRoute.OPERATOR_REVIEW
            reasons.append("Confidence between 0.65 and 0.84")

        if extraction.missing_information and any(m.blocking for m in extraction.missing_information):
            if route == ConfidenceRoute.AUTO:
                route = ConfidenceRoute.CLARIFICATION
            reasons.append("Blocking missing information present")

        return ConfidenceRoutingResult(route=route.value, reasons=reasons, extraction=extraction)
