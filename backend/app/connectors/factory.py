"""Resolve the active EmailProvider from configuration + tenant credentials."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.connectors.base import EmailProvider
from app.connectors.cloudmailin import CloudMailinProvider
from app.connectors.gmail import GmailConnector
from app.connectors.outlook import OutlookGraphProvider
from app.core.config import get_settings


def get_email_provider(session: Optional[Session] = None, tenant_id: Optional[str] = None) -> EmailProvider:
    settings = get_settings()
    provider = (settings.email_provider or "cloudmailin").strip().lower()
    if provider in {"cloudmailin", "cloud_mailin", "cmi"}:
        return CloudMailinProvider(session=session, tenant_id=tenant_id)
    if provider in {"outlook", "microsoft", "graph"}:
        return OutlookGraphProvider(session=session, tenant_id=tenant_id)
    if provider in {"gmail", "google"}:
        return GmailConnector(session=session, tenant_id=tenant_id)
    raise RuntimeError(f"Unsupported EMAIL_PROVIDER={settings.email_provider!r}")
