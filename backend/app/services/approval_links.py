"""Signed one-click approve / reject links for approval mails.

The HMAC binds approval_id + decision + expiry + intended approver email so a
forwarded/leaked link cannot be used as an unrestricted capability URL.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional
from urllib.parse import quote

from app.core.config import get_settings

DECISIONS = ("approve", "reject")


def public_base_url() -> Optional[str]:
    raw = (get_settings().public_base_url or os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
    return raw.rstrip("/") or None


def _norm_approver(approver_email: Optional[str]) -> str:
    return (approver_email or "").strip().lower()


def _sign(approval_id: str, decision: str, expires: int, approver_email: str) -> str:
    key = (get_settings().secret_key or "").encode()
    msg = f"{approval_id}|{decision}|{expires}|{_norm_approver(approver_email)}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:40]


def verify(
    approval_id: str,
    decision: str,
    expires: int,
    signature: str,
    approver_email: Optional[str] = None,
) -> bool:
    if decision not in DECISIONS or expires < int(time.time()):
        return False
    if not _norm_approver(approver_email):
        return False
    expected = _sign(approval_id, decision, expires, approver_email)
    return hmac.compare_digest(expected, signature or "")


def approval_link(
    approval_id: str,
    decision: str,
    *,
    approver_email: Optional[str] = None,
) -> Optional[str]:
    base = public_base_url()
    if not base or decision not in DECISIONS:
        return None
    from app.services.admin_ops import admin_ops_email

    approver = _norm_approver(approver_email) or _norm_approver(admin_ops_email())
    if not approver:
        return None
    settings = get_settings()
    expires = int(time.time() + float(settings.approval_link_hours or 72) * 3600)
    sig = _sign(approval_id, decision, expires, approver)
    return (
        f"{base}{settings.api_prefix}/public/approvals/{approval_id}/{decision}"
        f"?exp={expires}&sig={sig}&for={quote(approver)}"
    )


def approval_links_block(
    approval_id: Optional[str],
    *,
    approver_email: Optional[str] = None,
) -> str:
    """Two lines for the mail body, or empty when no public URL / approver is configured."""
    if not approval_id:
        return ""
    yes = approval_link(approval_id, "approve", approver_email=approver_email)
    no = approval_link(approval_id, "reject", approver_email=approver_email)
    if not (yes and no):
        return ""
    return f"Approve: {yes}\nReject: {no}"
