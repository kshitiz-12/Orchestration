"""Gmail OAuth connect + poll unread mail into the outcome pipeline."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.connectors import gmail as gmail_mod
from app.connectors.gmail import GmailConnector
from app.core.config import get_settings
from app.models.integrations import IntegrationCredential
from app.services.email_poll import poll_and_process

router = APIRouter(prefix="/integrations/gmail", tags=["gmail"])

# In-memory OAuth state (prototype). Survives one request cycle.
_oauth_states: dict[str, str] = {}


@router.get("/status")
def gmail_status(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    settings = get_settings()
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.provider == "GMAIL",
            IntegrationCredential.status == "ACTIVE",
        )
    ).first()
    return {
        "configured": bool(settings.gmail_client_id and settings.gmail_client_secret),
        "connected": row is not None,
        "account_email": row.account_email if row else None,
        "last_synced_at": row.last_synced_at if row else None,
        "redirect_uri": settings.gmail_redirect_uri,
    }


@router.get("/connect")
def gmail_connect(_session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    """Start Google OAuth — returns auth URL (open in browser)."""
    settings = get_settings()
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise HTTPException(
            400,
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET on the server first.",
        )
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = tenant_id
    try:
        url = gmail_mod.build_auth_url(state=state)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    return {"auth_url": url, "state": state, "hint": "Open auth_url in browser and approve Gmail access."}


@router.get("/callback")
def gmail_callback(code: str, state: str, session: SessionDep):
    """Google redirects here after user approves."""
    tenant_id = _oauth_states.pop(state, None)
    if not tenant_id:
        from app.models.org import Tenant

        tenant = session.exec(select(Tenant)).first()
        if not tenant:
            raise HTTPException(400, "Invalid OAuth state and no tenant found")
        tenant_id = tenant.tenant_id
    try:
        creds = gmail_mod.exchange_code_for_credentials(code, state)
        row = gmail_mod.save_credentials(session, tenant_id, creds)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Gmail OAuth failed: {exc}") from exc

    email = row.account_email or "connected"
    html = f"""
    <html><body style="font-family:sans-serif;padding:2rem">
      <h1>Gmail connected</h1>
      <p>Account: <strong>{email}</strong></p>
      <p>Unread emails will be ingested when you run Poll, or via the worker.</p>
      <p><a href="/docs">Back to API docs</a></p>
    </body></html>
    """
    return HTMLResponse(html)


@router.post("/poll")
def gmail_poll(
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
    max_results: int = 20,
    process: bool = True,
):
    """Fetch unread Gmail messages → store → process into outcomes."""
    result = poll_and_process(
        session,
        tenant_id,
        provider=GmailConnector(session, tenant_id),
        max_results=max_results,
        process=process,
    )
    if not result.get("ok") and result.get("error") in {"email_not_connected", "gmail_not_connected"}:
        raise HTTPException(400, "Gmail not connected. Call GET /integrations/gmail/connect first.")
    return result


@router.delete("/disconnect")
def gmail_disconnect(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.provider == "GMAIL",
        )
    ).first()
    if not row:
        return {"disconnected": False}
    row.status = "DISCONNECTED"
    session.add(row)
    session.commit()
    return {"disconnected": True}
