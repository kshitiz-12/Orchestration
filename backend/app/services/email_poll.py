"""Provider-agnostic poll: unread mail → intake → process → mark read."""

from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session

from app.connectors.base import EmailProvider
from app.connectors.factory import get_email_provider
from app.core.logging import get_logger
from app.engine.pipeline import ProcessingPipeline
from app.services.intake import IntakeService

logger = get_logger(__name__)


def poll_and_process(
    session: Session,
    tenant_id: str,
    *,
    provider: Optional[EmailProvider] = None,
    max_results: int = 20,
    process: bool = True,
) -> dict[str, Any]:
    channel = provider or get_email_provider(session, tenant_id)
    if not channel.is_connected():
        return {
            "ok": False,
            "error": "email_not_connected",
            "provider": channel.provider_name,
            "ingested": [],
        }

    messages = channel.fetch_unread(max_results=max_results)
    intake = IntakeService(session, tenant_id)
    pipeline = ProcessingPipeline(session, tenant_id)
    results = []

    for msg in messages:
        try:
            ingested = intake.ingest(
                message_id=msg["message_id"],
                thread_id=msg.get("thread_id") or msg["message_id"],
                sender=msg.get("sender") or "unknown@unknown",
                recipients=msg.get("recipients") or [],
                cc=msg.get("cc") or [],
                subject=msg.get("subject") or "",
                body_text=msg.get("body_text") or "",
                source=channel.provider_name,
                attachments=msg.get("attachments") or [],
                headers=msg.get("headers") or {},
                received_at=msg.get("received_at"),
                body_html=msg.get("body_html"),
            )
            processed = None
            if process and ingested.get("status") == "queued" and ingested.get("event_id"):
                processed = pipeline.process_event(ingested["event_id"])
            if ingested.get("status") in {"queued", "deduplicated", "quarantined"}:
                try:
                    channel.mark_processed(msg["message_id"])
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "mark_read_failed",
                        provider=channel.provider_name,
                        message_id=msg["message_id"],
                        error=str(exc),
                    )
            results.append(
                {
                    "message_id": msg["message_id"],
                    "provider": channel.provider_name,
                    "ingest": ingested,
                    "process": processed,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "email_message_failed",
                provider=channel.provider_name,
                message_id=msg.get("message_id"),
                error=str(exc),
            )
            results.append({"message_id": msg.get("message_id"), "error": str(exc)})

    return {
        "ok": True,
        "provider": channel.provider_name,
        "fetched": len(messages),
        "results": results,
    }
