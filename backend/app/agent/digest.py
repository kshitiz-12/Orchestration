"""Daily summary of desk work for the admin (ADMIN_FYI_LEVEL=digest)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.enums import CommunicationType
from app.models.company import ServiceTicket
from app.models.org import utcnow

_IST = timedelta(hours=5, minutes=30)
_DONE = {"RESOLVED", "CLOSED", "CANCELLED", "REJECTED"}


def digest_mode() -> bool:
    return (get_settings().admin_fyi_level or "key").strip().lower() == "digest"


def build_digest(session: Session, tenant_id: str, since: datetime) -> Optional[str]:
    tickets = session.exec(
        select(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id, ServiceTicket.updated_at >= since)
    ).all()
    open_rows = session.exec(
        select(ServiceTicket).where(ServiceTicket.tenant_id == tenant_id, ServiceTicket.status.notin_(list(_DONE)))
    ).all()
    finished = [t for t in tickets if t.status in _DONE]
    if not finished and not open_rows:
        return None
    now = utcnow()
    lines = [f"Admin desk summary - {(now + _IST).strftime('%A %d %b %Y')}", ""]
    lines.append(f"Finished since yesterday ({len(finished)}):" if finished else "Nothing finished since yesterday.")
    for t in sorted(finished, key=lambda x: x.updated_at or now):
        lines.append(f"- {t.reference} {t.title} - {t.status.lower()} ({t.department_code or 'ADMIN'}, {t.requester_email})")
    if open_rows:
        overdue = [t for t in open_rows if t.sla_due_at and t.sla_due_at < now]
        lines += ["", f"Still open ({len(open_rows)}, {len(overdue)} past SLA):"]
        for t in sorted(open_rows, key=lambda x: x.sla_due_at or now)[:30]:
            late = " - PAST SLA" if t.sla_due_at and t.sla_due_at < now else ""
            lines.append(f"- {t.reference} {t.title} - {t.status.lower().replace('_', ' ')}{late}")
    lines += ["", "Reply on any case mail to act on it."]
    return "\n".join(lines) + "\n"


def send_admin_digest(session: Session, tenant_id: str, *, force: bool = False) -> dict[str, Any]:
    """Send at most one digest per IST day, after ADMIN_DIGEST_HOUR_IST (force = send now)."""
    from app.services.admin_ops import admin_ops_email
    from app.services.hold_sweeper import _comms

    admin = admin_ops_email()
    if not admin or (not force and not digest_mode()):
        return {"sent": False, "reason": "digest off or no admin mailbox"}
    local = utcnow() + _IST
    if not force and local.hour < int(get_settings().admin_digest_hour_ist or 19):
        return {"sent": False, "reason": "not yet time"}
    body = build_digest(session, tenant_id, since=utcnow() - timedelta(days=1))
    if not body:
        return {"sent": False, "reason": "nothing to report"}
    day = local.strftime("%Y-%m-%d")
    _comms(session, tenant_id).send(
        communication_type=CommunicationType.INFORMATION_ONLY.value,
        recipients=[admin],
        subject=f"Admin desk daily summary - {local.strftime('%d %b %Y')}",
        body=body + f"\n{get_settings().mail_signature}\n",
        idempotency_key=f"admin-digest:{tenant_id}:{day}",
    )
    session.commit()
    return {"sent": True, "day": day}
