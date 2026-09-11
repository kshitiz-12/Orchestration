"""Gmail connector — OAuth web flow + unread poll. Never stores mailbox passwords."""

from __future__ import annotations

import base64
import json
import re
from email.mime.text import MIMEText
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session, select

from app.connectors.base import EmailProvider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.integrations import IntegrationCredential
from app.models.org import utcnow

logger = get_logger(__name__)

PROVIDER = "GMAIL"


def _scopes() -> list[str]:
    settings = get_settings()
    return [s.strip() for s in settings.gmail_scopes.split(",") if s.strip()]


def _client_config() -> dict:
    settings = get_settings()
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise RuntimeError(
            "Gmail OAuth not configured. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET."
        )
    return {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }


def build_auth_url(*, state: str) -> str:
    from google_auth_oauthlib.flow import Flow

    settings = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=_scopes(), state=state)
    flow.redirect_uri = settings.gmail_redirect_uri
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url


def exchange_code_for_credentials(code: str, state: str):
    import os

    from google_auth_oauthlib.flow import Flow

    # Google may return slightly broader scopes than requested
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

    settings = get_settings()
    flow = Flow.from_client_config(_client_config(), scopes=_scopes(), state=state)
    flow.redirect_uri = settings.gmail_redirect_uri
    flow.fetch_token(code=code)
    return flow.credentials


def save_credentials(session: Session, tenant_id: str, creds) -> IntegrationCredential:
    token_json = creds.to_json()
    account_email = None
    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        account_email = profile.get("emailAddress")
    except Exception as exc:  # noqa: BLE001
        logger.warning("gmail_profile_fetch_failed", error=str(exc))

    existing = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.tenant_id == tenant_id,
            IntegrationCredential.provider == PROVIDER,
        )
    ).first()
    if existing:
        existing.token_json = token_json
        existing.account_email = account_email or existing.account_email
        existing.scopes = " ".join(_scopes())
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
        scopes=" ".join(_scopes()),
        status="ACTIVE",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def load_credentials(session: Optional[Session], tenant_id: Optional[str]):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if session and tenant_id:
        row = session.exec(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == tenant_id,
                IntegrationCredential.provider == PROVIDER,
                IntegrationCredential.status == "ACTIVE",
            )
        ).first()
        if row:
            creds = Credentials.from_authorized_user_info(json.loads(row.token_json), _scopes())
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                row.token_json = creds.to_json()
                row.updated_at = utcnow()
                session.add(row)
                session.commit()
            return creds, row

    settings = get_settings()
    token_path = Path(settings.gmail_token_path)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _scopes())
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds, None
    return None, None


def parse_email_address(raw: str) -> str:
    _, addr = parseaddr(raw or "")
    return (addr or raw or "").strip().lower()


class GmailConnector(EmailProvider):
    def __init__(self, session: Optional[Session] = None, tenant_id: Optional[str] = None):
        self.settings = get_settings()
        self.session = session
        self.tenant_id = tenant_id
        self._service = None
        self._credential_row: Optional[IntegrationCredential] = None

    @property
    def provider_name(self) -> str:
        return PROVIDER

    def is_connected(self) -> bool:
        return self.connected()

    def _get_service(self):
        if self._service is not None:
            return self._service
        from googleapiclient.discovery import build

        creds, row = load_credentials(self.session, self.tenant_id)
        self._credential_row = row
        if not creds:
            raise RuntimeError("Gmail not connected. Open Connect Gmail first.")
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def connected(self) -> bool:
        try:
            creds, _ = load_credentials(self.session, self.tenant_id)
            return creds is not None
        except Exception:
            return False

    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        service = self._get_service()
        resp = (
            service.users()
            .messages()
            .list(userId=self.settings.gmail_user_id, q="is:unread", maxResults=max_results)
            .execute()
        )
        messages = []
        for item in resp.get("messages", []):
            full = (
                service.users()
                .messages()
                .get(userId=self.settings.gmail_user_id, id=item["id"], format="full")
                .execute()
            )
            messages.append(self._normalize(full))
        if self._credential_row and self.session:
            self._credential_row.last_synced_at = utcnow()
            self.session.add(self._credential_row)
            self.session.commit()
        return messages

    def _normalize(self, full: dict) -> dict[str, Any]:
        headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
        body_text = self._extract_body(full.get("payload", {}))
        attachments = []
        for part in self._walk_parts(full.get("payload", {})):
            filename = part.get("filename")
            if filename and part.get("body", {}).get("attachmentId"):
                attachments.append(
                    {
                        "filename": filename,
                        "mime_type": part.get("mimeType"),
                        "size": part.get("body", {}).get("size", 0),
                        "attachment_id": part["body"]["attachmentId"],
                    }
                )
        to_raw = headers.get("to", "")
        cc_raw = headers.get("cc", "")
        return {
            "message_id": full["id"],
            "thread_id": full.get("threadId"),
            "sender": parse_email_address(headers.get("from", "")),
            "recipients": [parse_email_address(x) for x in re.split(r"[,;]", to_raw) if x.strip()],
            "cc": [parse_email_address(x) for x in re.split(r"[,;]", cc_raw) if x.strip()],
            "subject": headers.get("subject", ""),
            "body_text": body_text,
            "attachments": attachments,
            "headers": headers,
        }

    def _walk_parts(self, payload: dict) -> list[dict]:
        parts = [payload]
        for part in payload.get("parts", []) or []:
            parts.extend(self._walk_parts(part))
        return parts

    def _extract_body(self, payload: dict) -> str:
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload.get("parts", []) or []:
            text = self._extract_body(part)
            if text:
                return text
        if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
            html = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", html)
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

    def send_reply(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        conversation_id: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> str:
        return self.send(to=to, subject=subject, body=body, thread_id=conversation_id)

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        service = self._get_service()
        message = MIMEText(body)
        message["to"] = ", ".join(to)
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body_obj: dict[str, Any] = {"raw": raw}
        if thread_id:
            body_obj["threadId"] = thread_id
        sent = (
            service.users()
            .messages()
            .send(userId=self.settings.gmail_user_id, body=body_obj)
            .execute()
        )
        return sent["id"]

    def mark_processed(self, message_id: str) -> None:
        service = self._get_service()
        service.users().messages().modify(
            userId=self.settings.gmail_user_id,
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()


class InMemoryEmailChannel(EmailProvider):
    def __init__(self):
        self.outbox: list[dict] = []
        self.inbox: list[dict] = []

    @property
    def provider_name(self) -> str:
        return "MEMORY"

    def is_connected(self) -> bool:
        return True

    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        return self.inbox[:max_results]

    def send_reply(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        conversation_id: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> str:
        return self.send(to=to, subject=subject, body=body, thread_id=conversation_id)

    def send(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> str:
        msg_id = f"mem_{len(self.outbox)+1}"
        self.outbox.append(
            {"id": msg_id, "to": to, "subject": subject, "body": body, "thread_id": thread_id}
        )
        return msg_id

    def mark_processed(self, message_id: str) -> None:
        self.inbox = [m for m in self.inbox if m.get("message_id") != message_id]
