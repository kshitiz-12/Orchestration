"""CloudMailin email channel — inbound webhook + optional SMTP outbound.

Inbound: CloudMailin POSTs JSON to /webhooks/cloudmailin (see routes/webhooks.py).
Outbound: SMTP with In-Reply-To / References so replies thread in the client's mailbox.

No Microsoft Graph. No Gmail API.
"""

from __future__ import annotations

import hashlib
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Any, Optional
from urllib.parse import unquote, urlparse

from app.connectors.base import EmailProvider
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.email import NormalizedAttachment, NormalizedEmailEvent

logger = get_logger(__name__)

PROVIDER = "CLOUDMAILIN"


def _header(headers: dict[str, Any], *names: str) -> Optional[str]:
    if not headers:
        return None
    lower = {str(k).lower().replace("-", "_"): v for k, v in headers.items()}
    for name in names:
        key = name.lower().replace("-", "_")
        val = lower.get(key)
        if val is None:
            continue
        if isinstance(val, list):
            return str(val[0]) if val else None
        return str(val)
    return None


def _parse_addr(raw: Optional[str]) -> str:
    if not raw:
        return ""
    _, addr = parseaddr(raw)
    return (addr or raw).strip().lower()


def _parse_addr_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"\s*,\s*", raw)
    return [a for a in (_parse_addr(p) for p in parts) if a]


def _thread_key(headers: dict[str, Any], message_id: str) -> str:
    in_reply = _header(headers, "in_reply_to", "In-Reply-To")
    if in_reply:
        return in_reply.strip()
    refs = _header(headers, "references", "References")
    if refs:
        tokens = refs.replace(",", " ").split()
        if tokens:
            return tokens[0].strip()
    return message_id


def normalize_cloudmailin_payload(payload: dict[str, Any]) -> NormalizedEmailEvent:
    headers = payload.get("headers") or {}
    envelope = payload.get("envelope") or {}

    message_id = _header(headers, "message_id", "Message-ID") or ""
    if not message_id:
        digest = hashlib.sha256(
            f"{envelope.get('from')}|{envelope.get('to')}|{_header(headers, 'subject')}|{payload.get('plain') or ''}".encode(
                "utf-8"
            )
        ).hexdigest()[:32]
        message_id = f"cloudmailin-{digest}"

    sender = _parse_addr(envelope.get("from") or _header(headers, "from", "From"))
    recipients = [_parse_addr(r) for r in (envelope.get("recipients") or []) if r]
    if not recipients:
        to = envelope.get("to") or _header(headers, "to", "To")
        recipients = _parse_addr_list(to)
    cc = _parse_addr_list(_header(headers, "cc", "Cc"))

    plain = payload.get("reply_plain") or payload.get("plain") or ""
    html = payload.get("html")
    subject = _header(headers, "subject", "Subject") or ""

    attachments: list[NormalizedAttachment] = []
    for att in payload.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        attachments.append(
            NormalizedAttachment(
                filename=att.get("file_name") or att.get("filename") or "attachment",
                mime_type=att.get("content_type") or att.get("contentType"),
                size=int(att.get("size") or 0),
                attachment_id=None,
            )
        )

    return NormalizedEmailEvent(
        provider=PROVIDER,
        provider_message_id=message_id,
        provider_conversation_id=_thread_key(headers, message_id),
        sender=sender or "unknown@unknown",
        recipients=recipients,
        cc=cc,
        subject=subject,
        body_text=(plain or "").strip(),
        body_html=html,
        received_at=None,
        attachments=attachments,
        original_metadata={
            "envelope": envelope,
            "headers": headers,
            "cloudmailin": True,
        },
    )


def parse_smtp_url(url: str) -> dict[str, Any]:
    """Parse smtp://user:pass@host:587 into connection fields."""
    parsed = urlparse(url)
    if parsed.scheme not in {"smtp", "smtps"}:
        raise ValueError("CLOUDMAILIN_SMTP_URL must start with smtp:// or smtps://")
    return {
        "host": parsed.hostname or "",
        "port": parsed.port or (465 if parsed.scheme == "smtps" else 587),
        "username": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "use_ssl": parsed.scheme == "smtps",
    }


class CloudMailinProvider(EmailProvider):
    """Push inbound via webhook; send replies via CloudMailin SMTP when configured."""

    def __init__(self, session=None, tenant_id: Optional[str] = None):
        self.settings = get_settings()
        self.session = session
        self.tenant_id = tenant_id

    @property
    def provider_name(self) -> str:
        return PROVIDER

    def _smtp_config(self) -> Optional[dict[str, Any]]:
        url = (self.settings.cloudmailin_smtp_url or "").strip()
        if url:
            try:
                return parse_smtp_url(url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("cloudmailin_smtp_url_invalid", error=str(exc))
                return None
        host = (self.settings.cloudmailin_smtp_host or "").strip()
        user = (self.settings.cloudmailin_smtp_username or "").strip()
        password = (self.settings.cloudmailin_smtp_password or "").strip()
        if host and user and password:
            return {
                "host": host,
                "port": int(self.settings.cloudmailin_smtp_port or 587),
                "username": user,
                "password": password,
                "use_ssl": False,
            }
        return None

    def is_connected(self) -> bool:
        """Ready to send live replies when SMTP is configured."""
        return self._smtp_config() is not None

    def get_account_email(self) -> Optional[str]:
        return (
            (self.settings.cloudmailin_from_email or "").strip()
            or (self.settings.cloudmailin_address or "").strip()
            or None
        )

    def fetch_unread(self, max_results: int = 20) -> list[dict[str, Any]]:
        # Inbound is push-based via webhook — nothing to poll.
        return []

    def mark_processed(self, message_id: str) -> None:
        return None

    def send_reply(
        self,
        *,
        to: list[str],
        subject: str,
        body: str,
        conversation_id: Optional[str] = None,
        in_reply_to_message_id: Optional[str] = None,
    ) -> str:
        cfg = self._smtp_config()
        if not cfg:
            raise RuntimeError(
                "CloudMailin SMTP not configured. Set CLOUDMAILIN_SMTP_URL "
                "(or HOST/USERNAME/PASSWORD) to send live replies."
            )
        from_addr = self.get_account_email()
        if not from_addr:
            raise RuntimeError("Set CLOUDMAILIN_FROM_EMAIL (or CLOUDMAILIN_ADDRESS) as the From address.")

        msg = EmailMessage()
        msg["From"] = formataddr(("Outcome Orchestration", from_addr))
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        new_id = make_msgid(domain=from_addr.split("@")[-1])
        msg["Message-ID"] = new_id
        if in_reply_to_message_id:
            msg["In-Reply-To"] = in_reply_to_message_id
            refs = conversation_id or in_reply_to_message_id
            msg["References"] = f"{refs} {in_reply_to_message_id}".strip()
        elif conversation_id:
            msg["In-Reply-To"] = conversation_id
            msg["References"] = conversation_id
        msg.set_content(body)

        context = ssl.create_default_context()
        if cfg.get("use_ssl"):
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=30) as smtp:
                smtp.login(cfg["username"], cfg["password"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(cfg["username"], cfg["password"])
                smtp.send_message(msg)

        logger.info(
            "cloudmailin_smtp_sent",
            to=to,
            subject=subject,
            message_id=new_id,
            in_reply_to=in_reply_to_message_id,
        )
        return new_id
