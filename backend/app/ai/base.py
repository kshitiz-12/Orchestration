from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.ai import ExtractionResult


class LLMProvider(ABC):
    """Replaceable AI provider interface — never call Gemini from business logic directly."""

    @abstractmethod
    def extract(
        self,
        *,
        subject: str,
        body: str,
        attachment_summaries: Optional[list[str]] = None,
        prior_facts: Optional[dict] = None,
        allowed_context: Optional[dict] = None,
    ) -> ExtractionResult:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError
