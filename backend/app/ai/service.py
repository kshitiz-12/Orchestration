from typing import Optional

from app.ai.base import LLMProvider
from app.ai.gemini import GeminiProvider, HeuristicProvider
from app.ai.meeting_extract import refine_meeting_room_extraction
from app.core.config import get_settings
from app.core.enums import ConfidenceRoute
from app.core.logging import get_logger
from app.schemas.ai import ConfidenceRoutingResult, ExtractionResult

logger = get_logger(__name__)


def _looks_like_meeting_room(subject: str, body: str, prior_facts: Optional[dict] = None) -> bool:
    text = f"{subject}\n{body}".lower()
    prior = prior_facts or {}
    if prior.get("date") or prior.get("attendees") or prior.get("registration_ack_sent"):
        if any(k in text for k in ["room", "meeting", "information required", "room-"]):
            return True
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
        "room-",
    ]
    if any(k in text for k in keys):
        return True
    return ("room" in text or "meeting" in text or "members" in text or "participants" in text) and any(
        k in text for k in ["people", "attendees", "members", "participants", "pm", "am", "hours", "tomorrow"]
    )


class LLMService:
    """AI gateway. Business logic consumes this — never GeminiProvider directly."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        settings = get_settings()
        if provider is not None:
            self.provider = provider
        elif settings.gemini_api_key or settings.gemini_api_key_secondary:
            self.provider = GeminiProvider()
        else:
            logger.warning("gemini_api_key_missing_using_heuristic_provider")
            self.provider = HeuristicProvider()

    def extract(self, **kwargs) -> ExtractionResult:
        subject = kwargs.get("subject") or ""
        body = kwargs.get("body") or ""
        prior_facts = kwargs.get("prior_facts") or {}
        used_fallback = False
        result: ExtractionResult | None = None
        last_exc: Exception | None = None

        try:
            # GeminiProvider already fails over across model + secondary API key
            result = self.provider.extract(**kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.error("ai_extraction_failed", error=str(exc)[:400])

        if result is None:
            used_fallback = True
            result = HeuristicProvider().extract(**kwargs)
            result.reason = f"Primary AI unavailable ({last_exc}); heuristic fallback used"

        looks_meeting = result.event_type == "MEETING_ROOM" or _looks_like_meeting_room(
            subject, body, prior_facts
        )
        if looks_meeting:
            heuristic_entities = None
            primary_is_heuristic = used_fallback or isinstance(self.provider, HeuristicProvider)
            if not primary_is_heuristic:
                # Candidates only fill fields the model left unknown — never overwrite Gemini
                heuristic_entities = HeuristicProvider().extract(**kwargs).entities
            result = refine_meeting_room_extraction(
                result,
                subject=subject,
                body=body,
                prior_facts=prior_facts,
                heuristic_entities=heuristic_entities,
                primary_is_heuristic=primary_is_heuristic,
            )
            if used_fallback:
                result.reason = (result.reason or "") + " | reducer + heuristic candidates"
            else:
                result.reason = (result.reason or "") + " | gemini delta + reducer"
            return result

        if used_fallback:
            sensitive = (
                result.safety_concern
                or result.financial_action
                or result.access_control_action
                or result.vendor_sanction
            )
            if not sensitive:
                result.human_review_required = True
                result.confidence = min(result.confidence, 0.6)
        return result

    def route(self, extraction: ExtractionResult) -> ConfidenceRoutingResult:
        reasons: list[str] = []
        is_meeting = (extraction.event_type or "").upper() == "MEETING_ROOM"
        if is_meeting:
            sensitive = bool(extraction.safety_concern or extraction.vendor_sanction)
        else:
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
        elif is_meeting and extraction.confidence >= 0.78:
            route = ConfidenceRoute.AUTO
            reasons.append("Meeting room facts ready for orchestration")
        elif extraction.confidence < 0.85:
            route = ConfidenceRoute.OPERATOR_REVIEW
            reasons.append("Confidence between 0.65 and 0.84")
        else:
            route = ConfidenceRoute.AUTO

        return ConfidenceRoutingResult(route=route.value, reasons=reasons, extraction=extraction)
