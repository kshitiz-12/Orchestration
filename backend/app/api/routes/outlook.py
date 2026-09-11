"""Microsoft Outlook.com / Graph OAuth + poll into the outcome pipeline."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlmodel import select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.connectors import outlook as outlook_mod
from app.connectors.outlook import OutlookGraphProvider
from app.core.config import get_settings
from app.models.integrations import IntegrationCredential
from app.services.email_poll import poll_and_process

router = APIRouter(prefix="/integrations/outlook", tags=["outlook"])

_oauth_states: dict[str, str] = {}


@router.get("/status")
def outlook_status(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    settings = get_settings()
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.provider == "OUTLOOK",
            IntegrationCredential.status == "ACTIVE",
        )
    ).first()
    provider = OutlookGraphProvider(session, tenant_id)
    return {
        "email_provider": settings.email_provider,
        "configured": bool(settings.microsoft_client_id and settings.microsoft_client_secret),
        "connected": row is not None and provider.is_connected(),
        "account_email": (row.account_email if row else None) or settings.microsoft_mailbox or None,
        "mailbox": settings.microsoft_mailbox or None,
        "last_synced_at": row.last_synced_at if row else None,
        "redirect_uri": settings.microsoft_redirect_uri,
        "scopes": settings.microsoft_scopes,
        "active_provider": provider.provider_name,
        "environment": "prototype_local",
    }


@router.get("/connect")
def outlook_connect(_session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    settings = get_settings()
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise HTTPException(
            400,
            "Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET first.",
        )
    state = outlook_mod.new_oauth_state()
    _oauth_states[state] = tenant_id
    try:
        url = outlook_mod.microsoft_auth_url(state=state)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    return {
        "auth_url": url,
        "state": state,
        "hint": "Open auth_url, sign in with your Outlook.com test mailbox, approve User.Read + Mail.Read + Mail.Send.",
    }


@router.get("/callback")
def outlook_callback(code: str, state: str, session: SessionDep):
    tenant_id = _oauth_states.pop(state, None)
    if not tenant_id:
        from app.models.org import Tenant

        tenant = session.exec(select(Tenant)).first()
        if not tenant:
            raise HTTPException(400, "Invalid OAuth state and no tenant found")
        tenant_id = tenant.tenant_id
    try:
        token_payload = outlook_mod.exchange_code_for_token(code)
        row = outlook_mod.save_outlook_credentials(session, tenant_id, token_payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Outlook OAuth failed: {exc}") from exc

    email = row.account_email or "connected"
    html = f"""
    <html><body style="font-family:Segoe UI,sans-serif;padding:2rem;background:#f7f7f5;color:#1a1a1a">
      <h1>Outlook.com connected</h1>
      <p>Account: <strong>{email}</strong></p>
      <p>You can close this tab and return to the app → <em>Poll inbox</em>.</p>
      <p>Replies use Microsoft Graph and stay in the <em>same</em> Outlook conversation.</p>
      <p><a href="/docs">API docs</a></p>
    </body></html>
    """
    return HTMLResponse(html)


@router.post("/poll")
def outlook_poll(
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
    max_results: int = 20,
    process: bool = True,
):
    result = poll_and_process(
        session,
        tenant_id,
        provider=OutlookGraphProvider(session, tenant_id),
        max_results=max_results,
        process=process,
    )
    if not result.get("ok") and result.get("error") == "email_not_connected":
        raise HTTPException(400, "Outlook not connected. Call GET /integrations/outlook/connect first.")
    return result


@router.delete("/disconnect")
def outlook_disconnect(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.provider == "OUTLOOK",
        )
    ).first()
    if not row:
        return {"disconnected": False}
    row.status = "DISCONNECTED"
    session.add(row)
    session.commit()
    return {"disconnected": True}
