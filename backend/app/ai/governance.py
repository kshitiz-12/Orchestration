"""AI governance — prompt/model registry, confidence gates, emergency stop (V3 §10.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import get_settings


@dataclass
class ModelRegistration:
    model_id: str
    provider: str
    purpose: str
    version: str = "1"
    enabled: bool = True


@dataclass
class PromptRegistration:
    prompt_id: str
    purpose: str
    version: str
    template_hash: str
    enabled: bool = True


# In-process registry (Phase 4). Persist to DB in later hardening if needed.
_MODELS: dict[str, ModelRegistration] = {
    "desk-interpret-v1": ModelRegistration("desk-interpret-v1", "gemini", "desk_interpretation", "1"),
    "resolution-v1": ModelRegistration("resolution-v1", "gemini", "ops_resolution", "1"),
}
_PROMPTS: dict[str, PromptRegistration] = {
    "desk.interpret.v1": PromptRegistration("desk.interpret.v1", "desk_interpretation", "1", "sha256:desk"),
}


@dataclass
class GovernanceVerdict:
    allowed: bool
    reason: str = ""
    require_human_review: bool = False
    model_id: Optional[str] = None
    checks: list[str] = field(default_factory=list)


class AIGovernance:
    def __init__(self, *, min_confidence: float = 0.45):
        self.min_confidence = min_confidence
        self.settings = get_settings()

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "purpose": m.purpose,
                "version": m.version,
                "enabled": m.enabled,
            }
            for m in _MODELS.values()
        ]

    def list_prompts(self) -> list[dict[str, Any]]:
        return [
            {
                "prompt_id": p.prompt_id,
                "purpose": p.purpose,
                "version": p.version,
                "enabled": p.enabled,
            }
            for p in _PROMPTS.values()
        ]

    def before_inference(self, *, purpose: str, model_id: Optional[str] = None) -> GovernanceVerdict:
        if getattr(self.settings, "ai_emergency_stop", False):
            return GovernanceVerdict(
                allowed=False,
                reason="AI emergency stop is active",
                require_human_review=True,
                checks=["EMERGENCY_STOP"],
            )
        model = None
        if model_id and model_id in _MODELS:
            model = _MODELS[model_id]
        else:
            model = next((m for m in _MODELS.values() if m.purpose == purpose and m.enabled), None)
        if model is None or not model.enabled:
            return GovernanceVerdict(
                allowed=False,
                reason="No enabled model registered for purpose",
                require_human_review=True,
                checks=["MODEL_REGISTRY"],
            )
        return GovernanceVerdict(allowed=True, model_id=model.model_id, checks=["MODEL_REGISTRY"])

    def after_inference(self, *, confidence: float, structured_ok: bool = True) -> GovernanceVerdict:
        checks: list[str] = []
        if not structured_ok:
            return GovernanceVerdict(
                allowed=False,
                reason="Structured output validation failed",
                require_human_review=True,
                checks=["SCHEMA_VALIDATION"],
            )
        if confidence < self.min_confidence:
            checks.append("LOW_CONFIDENCE")
            return GovernanceVerdict(
                allowed=False,
                reason=f"Confidence {confidence:.2f} below {self.min_confidence}",
                require_human_review=True,
                checks=checks,
            )
        return GovernanceVerdict(allowed=True, checks=["CONFIDENCE_OK"])
