"""Inbound email webhooks (CloudMailin) → Intake → pipeline.

Public endpoint (no JWT). Protected by shared secret query/header when configured.
Returns 2xx quickly after durable ingest; AI/outcome runs in a background task so
CloudMailin does not time out on Render cold starts.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.connectors.cloudmailin import PROVIDER, normalize_cloudmailin_payload
from app.core.config import get_settings
from app.core.database import get_engine
from app.core.logging import get_logger
from app.engine.pipeline import ProcessingPipeline
from app.models.org import Tenant
from app.services.intake import IntakeService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


def _assert_webhook_auth(
    *,
    secret_query: Optional[str],
    secret_header: Optional[str],
) -> None:
    settings = get_settings()
    expected = (settings.cloudmailin_webhook_secret or "").strip()
    if not expected:
        if settings.is_production:
            raise HTTPException(503, "CLOUDMAILIN_WEBHOOK_SECRET must be set in production")
        return
    provided = (secret_header or secret_query or "").strip()
    if provided != expected:
        raise HTTPException(401, "Invalid CloudMailin webhook secret")


def _default_tenant_id(session) -> str:
    tenant = session.exec(select(Tenant)).first()
    if not tenant:
        raise HTTPException(400, "No tenant seeded")
    return tenant.tenant_id


def _process_event_background(event_id: str, tenant_id: str) -> None:
    try:
        with Session(get_engine()) as session:
            result = ProcessingPipeline(session, tenant_id).process_event(event_id)
            logger.info(
                "cloudmailin_background_processed",
                event_id=event_id,
                status=result.get("status"),
                outcome_id=result.get("outcome_id"),
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cloudmailin_background_failed", event_id=event_id, error=str(exc))


@router.get("/cloudmailin")
def cloudmailin_status(session: SessionDep):
    from app.connectors.cloudmailin import CloudMailinProvider

    settings = get_settings()
    provider = CloudMailinProvider(session=session)
    cfg = provider._send_config() or {}
    return {
        "provider": PROVIDER,
        "email_provider": settings.email_provider,
        "enabled": True,
        "address": settings.cloudmailin_address or None,
        "from_email": provider.get_account_email(),
        "webhook_path": f"{settings.api_prefix}/webhooks/cloudmailin",
        "format": "JSON Normalized",
        "secret_configured": bool(settings.cloudmailin_webhook_secret),
        "smtp_configured": provider.can_send(),
        "can_send_replies": provider.can_send(),
        "outbound_channel": cfg.get("channel") or None,
        "outbound": "cloudmailin" if cfg.get("channel") == "cloudmailin" else ("gmail_smtp" if cfg.get("channel") == "gmail_smtp" else "none"),
        "note": (
            "Inbound: CloudMailin webhook. "
            "Outbound: prefer CLOUDMAILIN_SMTP_URL + CLOUDMAILIN_FROM_EMAIL on verified domain "
            "(HTTPS API works on Render). Gmail SMTP is fallback."
        ),
    }


@router.post("/cloudmailin")
async def cloudmailin_inbound(
    request: Request,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    process: bool = Query(True),
    secret: Optional[str] = Query(None, description="Shared secret (or use X-Webhook-Secret)"),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
):
    """Receive CloudMailin JSON Normalized POST → store → background AI pipeline."""
    _assert_webhook_auth(secret_query=secret, secret_header=x_webhook_secret)

    content_type = (request.headers.get("content-type") or "").lower()
    payload: dict[str, Any]
    if "application/json" in content_type or content_type.endswith("+json"):
        payload = await request.json()
    elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        payload = {}
        for key in ("plain", "html", "reply_plain"):
            if key in form:
                payload[key] = form.get(key)
        envelope: dict[str, Any] = {}
        headers_map: dict[str, Any] = {}
        for k, v in form.multi_items():
            if k.startswith("envelope[") and k.endswith("]"):
                envelope[k[9:-1]] = v
            elif k.startswith("headers[") and k.endswith("]"):
                headers_map[k[8:-1]] = v
        if envelope:
            payload["envelope"] = envelope
        if headers_map:
            payload["headers"] = headers_map
    else:
        try:
            payload = await request.json()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                400, f"Unsupported CloudMailin content-type: {content_type or 'unknown'}"
            ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(400, "Expected JSON object body")

    try:
        normalized = normalize_cloudmailin_payload(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cloudmailin_normalize_failed", error=str(exc))
        raise HTTPException(400, f"Invalid CloudMailin payload: {exc}") from exc

    tenant_id = _default_tenant_id(session)
    intake = IntakeService(session, tenant_id)
    try:
        ingested = intake.ingest(
            message_id=normalized.provider_message_id,
            thread_id=normalized.provider_conversation_id,
            sender=normalized.sender,
            recipients=normalized.recipients,
            cc=normalized.cc,
            subject=normalized.subject,
            body_text=normalized.body_text,
            source=PROVIDER,
            attachments=[a.model_dump() for a in normalized.attachments],
            headers=normalized.original_metadata.get("headers") or {},
            body_html=normalized.body_html,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cloudmailin_ingest_failed", error=str(exc))
        raise HTTPException(500, f"Ingest failed: {exc}") from exc

    queued = False
    if process and ingested.get("status") == "queued" and ingested.get("event_id"):
        background_tasks.add_task(_process_event_background, ingested["event_id"], tenant_id)
        queued = True

    return {
        "ok": True,
        "provider": PROVIDER,
        "ingest": ingested,
        "processing": "queued" if queued else ingested.get("status"),
        "message_id": normalized.provider_message_id,
        "conversation_id": normalized.provider_conversation_id,
    }
