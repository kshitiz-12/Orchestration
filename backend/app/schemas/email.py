"""Normalized email representation for AI / intake — never raw Graph/Gmail objects."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NormalizedAttachment(BaseModel):
    filename: str
    mime_type: Optional[str] = None
    size: int = 0
    attachment_id: Optional[str] = None


class NormalizedEmailEvent(BaseModel):
    provider: str
    provider_message_id: str
    provider_conversation_id: str
    sender: str
    recipients: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = None
    received_at: Optional[datetime] = None
    attachments: list[NormalizedAttachment] = Field(default_factory=list)
    original_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_intake_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.provider_message_id,
            "thread_id": self.provider_conversation_id,
            "sender": self.sender,
            "recipients": self.recipients,
            "cc": self.cc,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "received_at": self.received_at,
            "attachments": [a.model_dump() for a in self.attachments],
            "headers": self.original_metadata,
        }
