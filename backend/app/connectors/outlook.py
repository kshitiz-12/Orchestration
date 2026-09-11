"""Microsoft Graph / Outlook.com email provider.

All Graph HTTP + OAuth logic lives here. Core orchestration uses EmailProvider only.

Least-privilege delegated scopes (prototype):
  openid offline_access User.Read Mail.Read Mail.Send

We intentionally do NOT request Mail.ReadWrite. Processed messages are tracked in
our DB (RawEmailEvent.provider_message_id) instead of mutating isRead in Graph.
"""

from __future__ import annotations

import json
import secrets
import time
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from sqlmodel import Session, select

from app.connectors.base import EmailProvider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.integrations import IntegrationCredential
from app.models.intake import RawEmailEvent
from app.models.org import utcnow
from app.schemas.email import NormalizedAttachment, NormalizedEmailEvent

logger = get_logger(__name__)

PROVIDER = "OUTLOOK"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
AUTHORITY_TMPL = "https://login.microsoftonline.com/{tenant}"


def _parse_addr(raw: str) -> str:
    _, addr = parseaddr(raw or "")
    return (addr or raw or "").strip().lower()


def microsoft_auth_url(*, state: str) -> str:
    settings = get_settings()
    if not settings.microsoft_client_id:
        raise RuntimeError("MICROSOFT_CLIENT_ID is not configured")
    tenant = settings.microsoft_tenant_id or "common"
    scopes = settings.microsoft_scopes.replace(",", " ").split()
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_mode": "query",
        "scope": " ".join(scopes),
        "state": state,
        "prompt": "select_account",
    }
    return f"{AUTHORITY_TMPL.format(tenant=tenant)}/oauth2/v2.0/authorize?{urlencode(params)}"


def exchange_code_for_token(code: str) -> dict[str, Any]:
    settings = get_settings()
    tenant = settings.microsoft_tenant_id or "common"
    scopes = settings.microsoft_scopes.replace(",", " ").split()
    data = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "code": code,
        "redirect_uri": settings.microsoft_redirect_uri,
        "grant_type": "authorization_code",
        "scope": " ".join(scopes),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{AUTHORITY_TMPL.format(tenant=tenant)}/oauth2/v2.0/token",
            data=data,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Microsoft token exchange failed: {resp.status_code} {resp.text[:400]}")
        return resp.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    settings = get_settings()
    tenant = settings.microsoft_tenant_id or "common"
    scopes = settings.microsoft_scopes.replace(",", " ").split()
    data = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": " ".join(scopes),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{AUTHORITY_TMPL.format(tenant=tenant)}/oauth2/v2.0/token",
            data=data,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Microsoft token refresh failed: {resp.status_code} {resp.text[:400]}")
        return resp.json()


def save_outlook_credentials(session: Session, tenant_id: str, token_payload: dict) -> IntegrationCredential:
    settings = get_settings()
    access = token_payload.get("access_token")
    account_email = None
    if access:
        try:
            with httpx.Client(timeout=20.0) as client:
                me = client.get(
                    f"{GRAPH_BASE}/me",
                    headers={"Authorization": f"Bearer {access}"},
                )
                if me.status_code == 200:
                    body = me.json()
                    account_email = body.get("mail") or body.get("userPrincipalName")
        except Exception as exc:  # noqa: BLE001
            logger.warning("outlook_profile_fetch_failed", error=str(exc))

    if settings.microsoft_mailbox:
        account_email = account_email or settings.microsoft_mailbox

    existing = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.provider == PROVIDER,
        )
    ).first()
    token_json = json.dumps(token_payload)
    if existing:
        existing.token_json = token_json
        existing.account_email = account_email or existing.account_email
        existing.scopes = settings.microsoft_scopes
        existing.status = "ACTIVE"
        existing.updated_at = utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = IntegrationCredential(
        tenant_id=tenant_id,
        provider=PROVIDER,
        account_email=account_email,
        token_json=token_json,
        scopes=settings.microsoft_scopes,
        status="ACTIVE",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _graph_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    max_retries: int = 3,
    **kwargs: Any,
) -> httpx.Response:
    """Execute Graph call with basic 429/5xx backoff."""
    last: Optional[httpx.Response] = None
    for attempt in range(max_retries):
        resp = client.request(method, url, headers=headers, **kwargs)
        last = resp
        if resp.status_code != 429 and resp.status_code < 500:
            return resp
        retry_after = resp.headers.get("Retry-After")
        delay = float(retry_after) if retry_after and retry_after.isdigit() else (2**attempt)
        logger.warning(
            "graph_throttled_or_server_error",
            status=resp.status_code,
            attempt=attempt + 1,
            delay=delay,
            url=url,
        )
        time.sleep(min(delay, 30.0))
    assert last is not None
    return last


class OutlookGraphProvider(EmailProvider):
    def __init__(self, session: Optional[Session] = None, tenant_id: Optional[str] = None):
        self.settings = get_settings()
        self.session = session
        self.tenant_id = tenant_id
        self._credential_row: Optional[IntegrationCredential] = None
        self._access_token: Optional[str] = None

    @property
    def provider_name(self) -> str:
        return PROVIDER

    def is_connected(self) -> bool:
        try:
            row = self._load_row()
            if not row:
                return False
            payload = json.loads(row.token_json or "{}")
            return bool(payload.get("access_token") or payload.get("refresh_token"))
        except Exception:
            return False

    def get_account_email(self) -> Optional[str]:
        if self._credential_row:
            return self._credential_row.account_email
        if self.session and self.tenant_id:
            row = self._load_row()
            return row.account_email if row else self.settings.microsoft_mailbox or None
        return self.settings.microsoft_mailbox or None

    def _load_row(self) -> Optional[IntegrationCredential]:
        if not self.session or not self.tenant_id:
            return None
        return self.session.exec(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == self.tenant_id,
                IntegrationCredential.provider == PROVIDER,
                IntegrationCredential.status == "ACTIVE",
            )
        ).first()

    def _ensure_token(self) -> str:
        if self._access_token:
            return self._access_token
        row = self._load_row()
        self._credential_row = row
        if not row:
            raise RuntimeError("Outlook not connected. Complete Microsoft OAuth first.")
        payload = json.loads(row.token_json)
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        if refresh:
            try:
                refreshed = refresh_access_token(refresh)
                payload.update(refreshed)
                if "refresh_token" not in refreshed and refresh:
                    payload["refresh_token"] = refresh
                row.token_json = json.dumps(payload)
                row.updated_at = utcnow()
                if self.session:
                    self.session.add(row)
                    self.session.commit()
                access = payload.get("access_token")
            except Exception as exc:  # noqa: BLE001
                logger.warning("outlook_token_refresh_failed", error=str(exc))
                if not access:
                    raise
        if not access:
            raise RuntimeError("Outlook token missing. Reconnect Microsoft account.")
        self._access_token = access
        return access

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json",
        }

    def _mailbox_root(self) -> str:
        mailbox = (self.settings.microsoft_mailbox or "").strip()
        if mailbox:
            return f"/users/{mailbox}"
        return "/me"

    def _known_message_ids(self) -> set[str]:
        if not self.session or not self.tenant_id:
            return set()
        rows = self.session.exec(
            select(RawEmailEvent.provider_message_id).where(
                RawEmailEvent.tenant_id == self.tenant_id,
                RawEmailEvent.provider == PROVIDER,
            )
        ).all()
        return {r for r in rows if r}

    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        """Fetch recent inbox messages not yet stored locally.

        Uses Mail.Read only — does not rely on Graph isRead mutations.
        """
        root = self._mailbox_root()
        # Over-fetch slightly so DB filtering still yields work
        fetch_n = min(max(max_results * 3, max_results), 50)
        params = {
            "$top": str(fetch_n),
            "$orderby": "receivedDateTime desc",
            "$select": (
                "id,conversationId,subject,bodyPreview,body,from,toRecipients,"
                "ccRecipients,receivedDateTime,hasAttachments,internetMessageId"
            ),
        }
        known = self._known_message_ids()
        with httpx.Client(timeout=40.0) as client:
            resp = _graph_request(
                client,
                "GET",
                f"{GRAPH_BASE}{root}/mailFolders/inbox/messages",
                headers=self._headers(),
                params=params,
            )
            if resp.status_code == 401 and self._credential_row:
                self._access_token = None
                payload = json.loads(self._credential_row.token_json)
                if payload.get("refresh_token"):
                    refreshed = refresh_access_token(payload["refresh_token"])
                    payload.update(refreshed)
                    self._credential_row.token_json = json.dumps(payload)
                    if self.session:
                        self.session.add(self._credential_row)
                        self.session.commit()
                    self._access_token = payload.get("access_token")
                    resp = _graph_request(
                        client,
                        "GET",
                        f"{GRAPH_BASE}{root}/mailFolders/inbox/messages",
                        headers=self._headers(),
                        params=params,
                    )
            if resp.status_code >= 400:
                raise RuntimeError(f"Graph inbox fetch failed: {resp.status_code} {resp.text[:400]}")
            items = resp.json().get("value", [])

            results: list[dict[str, Any]] = []
            for item in items:
                mid = item.get("id")
                if not mid or mid in known:
                    continue
                attachments: list[NormalizedAttachment] = []
                if item.get("hasAttachments"):
                    att_resp = _graph_request(
                        client,
                        "GET",
                        f"{GRAPH_BASE}{root}/messages/{mid}/attachments",
                        headers=self._headers(),
                        params={"$select": "id,name,contentType,size"},
                    )
                    if att_resp.status_code == 200:
                        for a in att_resp.json().get("value", []):
                            attachments.append(
                                NormalizedAttachment(
                                    filename=a.get("name") or "attachment",
                                    mime_type=a.get("contentType"),
                                    size=int(a.get("size") or 0),
                                    attachment_id=a.get("id"),
                                )
                            )
                normalized = self._normalize(item, attachments)
                results.append(normalized.to_intake_dict())
                if len(results) >= max_results:
                    break

            if self._credential_row and self.session:
                self._credential_row.last_synced_at = utcnow()
                self.session.add(self._credential_row)
                self.session.commit()
            return results

    def _normalize(self, item: dict, attachments: list[NormalizedAttachment]) -> NormalizedEmailEvent:
        frm = ((item.get("from") or {}).get("emailAddress") or {})
        sender = (frm.get("address") or "").lower()
        recipients = [
            (r.get("emailAddress") or {}).get("address", "").lower()
            for r in (item.get("toRecipients") or [])
            if (r.get("emailAddress") or {}).get("address")
        ]
        cc = [
            (r.get("emailAddress") or {}).get("address", "").lower()
            for r in (item.get("ccRecipients") or [])
            if (r.get("emailAddress") or {}).get("address")
        ]
        body = item.get("body") or {}
        content = body.get("content") or item.get("bodyPreview") or ""
        content_type = (body.get("contentType") or "text").lower()
        body_text = content
        body_html = None
        if content_type == "html":
            body_html = content
            import re

            body_text = re.sub(r"<[^>]+>", " ", content)
        received_at = None
        if item.get("receivedDateTime"):
            try:
                received_at = datetime.fromisoformat(item["receivedDateTime"].replace("Z", "+00:00"))
                received_at = received_at.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                received_at = None
        return NormalizedEmailEvent(
            provider=PROVIDER,
            provider_message_id=item["id"],
            provider_conversation_id=item.get("conversationId") or item["id"],
            sender=sender,
            recipients=recipients,
            cc=cc,
            subject=item.get("subject") or "",
            body_text=body_text.strip(),
            body_html=body_html,
            received_at=received_at,
            attachments=attachments,
            original_metadata={
                "internetMessageId": item.get("internetMessageId"),
                "graph_id": item.get("id"),
                "conversationId": item.get("conversationId"),
            },
        )

    def send_reply(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        conversation_id: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> str:
        """Reply in the same Outlook conversation via Graph (Mail.Send)."""
        root = self._mailbox_root()
        with httpx.Client(timeout=40.0) as client:
            if in_reply_to_message_id:
                resp = _graph_request(
                    client,
                    "POST",
                    f"{GRAPH_BASE}{root}/messages/{in_reply_to_message_id}/reply",
                    headers=self._headers(),
                    json={"comment": body},
                )
                if resp.status_code in {200, 202}:
                    return in_reply_to_message_id
                logger.warning(
                    "outlook_reply_failed",
                    status=resp.status_code,
                    body=resp.text[:300],
                    message_id=in_reply_to_message_id,
                )

            if conversation_id:
                search = _graph_request(
                    client,
                    "GET",
                    f"{GRAPH_BASE}{root}/messages",
                    headers=self._headers(),
                    params={
                        "$top": "1",
                        "$filter": f"conversationId eq '{conversation_id}'",
                        "$orderby": "receivedDateTime desc",
                        "$select": "id",
                    },
                )
                if search.status_code == 200:
                    vals = search.json().get("value") or []
                    if vals:
                        mid = vals[0]["id"]
                        resp = _graph_request(
                            client,
                            "POST",
                            f"{GRAPH_BASE}{root}/messages/{mid}/reply",
                            headers=self._headers(),
                            json={"comment": body},
                        )
                        if resp.status_code in {200, 202}:
                            return mid

            # Last resort: sendMail (Mail.Send) — may start a related thread if reply failed
            message = {
                "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
            }
            if conversation_id:
                message["conversationId"] = conversation_id
            resp = _graph_request(
                client,
                "POST",
                f"{GRAPH_BASE}{root}/sendMail",
                headers=self._headers(),
                json={"message": message, "saveToSentItems": True},
            )
            if resp.status_code not in {200, 202}:
                raise RuntimeError(f"Graph sendMail failed: {resp.status_code} {resp.text[:400]}")
            return f"sent:{conversation_id or subject}"

    def mark_processed(self, message_id: str) -> None:
        """No Graph mutation — persistence of RawEmailEvent is the processed marker.

        Avoids Mail.ReadWrite. Idempotent intake already skips duplicates.
        """
        logger.debug("outlook_mark_processed_local_only", message_id=message_id)


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)
