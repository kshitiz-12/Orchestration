"""Provider-agnostic email channel contract.

Core orchestration talks only to EmailProvider — never to Graph/Gmail SDKs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class EmailProvider(ABC):
    """Replaceable inbound/outbound email channel (Outlook Graph, Gmail, …)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable source tag stored on RawEmailEvent.source (e.g. OUTLOOK, GMAIL)."""

    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        """Return normalized message dicts (see schemas.email.NormalizedEmailEvent)."""
        raise NotImplementedError

    @abstractmethod
    def send_reply(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        conversation_id: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> str:
        """Send a reply in the same conversation when possible. Returns provider message id."""
        raise NotImplementedError

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        """Backward-compatible alias used by CommunicationService."""
        return self.send_reply(
            to=to,
            subject=subject,
            body=body,
            conversation_id=thread_id,
            in_reply_to_message_id=None,
        )

    @abstractmethod
    def mark_processed(self, message_id: str) -> None:
        raise NotImplementedError

    def get_account_email(self) -> Optional[str]:
        return None


# Legacy name kept for existing imports
EmailChannel = EmailProvider
