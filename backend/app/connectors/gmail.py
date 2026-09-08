import base64
import json
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

from app.connectors.base import EmailChannel
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GmailConnector(EmailChannel):
    """Gmail API + OAuth. Never stores passwords."""

    def __init__(self):
        self.settings = get_settings()
        self._service = None

    def _credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        token_path = Path(self.settings.gmail_token_path)
        scopes = [s.strip() for s in self.settings.gmail_scopes.split(",") if s.strip()]
        creds = None
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.settings.gmail_client_id or not self.settings.gmail_client_secret:
                    raise RuntimeError("Gmail OAuth client not configured")
                client_config = {
                    "installed": {
                        "client_id": self.settings.gmail_client_id,
                        "client_secret": self.settings.gmail_client_secret,
                        "redirect_uris": [self.settings.gmail_redirect_uri, "http://localhost"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, scopes)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    def _get_service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("gmail", "v1", credentials=self._credentials())
        return self._service

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
        return messages

    def _normalize(self, full: dict) -> dict[str, Any]:
        headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
        body_text = self._extract_body(full.get("payload", {}))
        attachments = []
        for part in full.get("payload", {}).get("parts", []) or []:
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
        return {
            "message_id": full["id"],
            "thread_id": full.get("threadId"),
            "sender": headers.get("from", ""),
            "recipients": [headers.get("to", "")],
            "cc": [headers.get("cc", "")] if headers.get("cc") else [],
            "subject": headers.get("subject", ""),
            "body_text": body_text,
            "attachments": attachments,
            "headers": headers,
        }

    def _extract_body(self, payload: dict) -> str:
        if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload.get("parts", []) or []:
            text = self._extract_body(part)
            if text:
                return text
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return ""

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


class InMemoryEmailChannel(EmailChannel):
    """Sandbox channel for tests and demos without Gmail."""

    def __init__(self):
        self.outbox: list[dict] = []
        self.inbox: list[dict] = []

    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        return self.inbox[:max_results]

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
