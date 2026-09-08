from abc import ABC, abstractmethod
from typing import Any, Optional


class EmailChannel(ABC):
    """Replaceable email channel abstraction (Gmail today, Outlook later)."""

    @abstractmethod
    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def mark_processed(self, message_id: str) -> None:
        raise NotImplementedError
