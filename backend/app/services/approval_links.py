"""Signed one-click approve / reject links for approval mails (no login needed; the signature is the auth)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

from app.core.config import get_settings

DECISIONS = ("approve", "reject")


def public_base_url() -> Optional[str]:
    raw = (get_settings().public_base_url or os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
    return raw.rstrip("/") or None


def _sign(approval_id: str, decision: str, expires: int) -> str:
    key = (get_settings().secret_key or "").encode()
    msg = f"{approval_id}|{decision}|{expires}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:40]


def verify(approval_id: str, decision: str, expires: int, signature: str) -> bool:
    if decision not in DECISIONS or expires < int(time.time()):
        return False
    return hmac.compare_digest(_sign(approval_id, decision, expires), signature or "")


def approval_link(approval_id: str, decision: str) -> Optional[str]:
    base = public_base_url()
    if not base or decision not in DECISIONS:
        return None
    settings = get_settings()
    expires = int(time.time() + float(settings.approval_link_hours or 72) * 3600)
    sig = _sign(approval_id, decision, expires)
    return f"{base}{settings.api_prefix}/public/approvals/{approval_id}/{decision}?exp={expires}&sig={sig}"


def approval_links_block(approval_id: Optional[str]) -> str:
    """Two lines for the mail body, or empty when no public URL is configured."""
    if not approval_id:
        return ""
    yes, no = approval_link(approval_id, "approve"), approval_link(approval_id, "reject")
    if not (yes and no):
        return ""
    return f"Approve: {yes}\nReject: {no}"
