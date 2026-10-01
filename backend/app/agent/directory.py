"""Who handles what: department routing, with the env admin as the fallback for unset contacts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from app.agent.company_seed import is_placeholder
from app.models.company import Department, KnowledgeEntry


@dataclass
class Route:
    department_code: str
    department_name: str
    recipients: list[str] = field(default_factory=list)
    approver: Optional[str] = None
    sla_hours: int = 24
    spend_approval_limit: float = 0.0
    # True when the department has no real mailbox yet and the work order goes to the main admin
    redirected_to_admin: bool = False


def _admin() -> Optional[str]:
    from app.services.admin_ops import admin_ops_email

    return admin_ops_email()


def _real(emails: list[Optional[str]]) -> list[str]:
    out: list[str] = []
    for e in emails:
        addr = (e or "").strip().lower()
        if addr and not is_placeholder(addr) and addr not in out:
            out.append(addr)
    return out


def departments(session: Session, tenant_id: str) -> list[Department]:
    return list(
        session.exec(
            select(Department).where(Department.tenant_id == tenant_id, Department.is_active == True)  # noqa: E712
        ).all()
    )


def department_for(session: Session, tenant_id: str, category: str) -> Optional[Department]:
    from app.agent.playbooks import has_playbook, normalize_category, playbook_for

    cat = (category or "general").strip().lower()
    rows = departments(session, tenant_id)
    for dept in rows:
        if cat in [str(c).strip().lower() for c in dept.categories or []]:
            return dept
    norm = normalize_category(cat)
    if norm != cat:
        for dept in rows:
            if norm in [str(c).strip().lower() for c in dept.categories or []]:
                return dept
    if has_playbook(norm):
        owner = playbook_for(norm).department
        found = next((d for d in rows if d.code == owner), None)
        if found:
            return found
    return next((d for d in rows if d.code == "ADMIN"), None)


def handles_category(session: Session, tenant_id: str, category: str) -> bool:
    cat = (category or "").strip().lower()
    return any(cat in [str(c).strip().lower() for c in d.categories or []] for d in departments(session, tenant_id))


def find_department(session: Session, tenant_id: str, text: str) -> Optional[Department]:
    """Match an admin's free-text team name ("facilities", "IT", "Travel Desk") to a department."""
    want = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if not want:
        return None
    rows = departments(session, tenant_id)
    for dept in rows:
        if want in {dept.code.lower(), re.sub(r"[^a-z0-9]+", " ", dept.name.lower()).strip()}:
            return dept
    return next((d for d in rows if want in d.name.lower() or d.code.lower().startswith(want)), None)


def route_for_case(session: Session, tenant_id: str, facts: dict) -> Route:
    """Route for an existing case: an admin's team override wins over the category's default team."""
    override = facts.get("department_override")
    if override:
        dept = next((d for d in departments(session, tenant_id) if d.code == override), None)
        if dept is not None:
            return _route_from(dept)
    return route_for(session, tenant_id, facts.get("agent_category") or "general")


def route_for(session: Session, tenant_id: str, category: str) -> Route:
    return _route_from(department_for(session, tenant_id, category))


def _route_from(dept: Optional[Department]) -> Route:
    admin = _admin()
    if dept is None:
        return Route("ADMIN", "Admin", [admin] if admin else [], approver=admin, redirected_to_admin=True)
    recipients = _real([dept.primary_email, *(dept.backup_emails or [])])
    approver = (_real([dept.approver_email]) or [None])[0]
    redirected = not recipients
    if redirected and admin:
        recipients = [admin]
    return Route(
        department_code=dept.code,
        department_name=dept.name,
        recipients=recipients,
        approver=approver or admin,
        sla_hours=dept.sla_hours or 24,
        spend_approval_limit=float(dept.spend_approval_limit or 0),
        redirected_to_admin=redirected,
    )


def department_emails(session: Session, tenant_id: Optional[str] = None) -> set[str]:
    """Real department mailboxes; they may reply to work orders like the admin does."""
    stmt = select(Department).where(Department.is_active == True)  # noqa: E712
    if tenant_id:
        stmt = stmt.where(Department.tenant_id == tenant_id)
    out: set[str] = set()
    for dept in session.exec(stmt).all():
        out.update(_real([dept.primary_email, dept.approver_email, *(dept.backup_emails or [])]))
    return out


def knowledge_text(session: Session, tenant_id: str, limit_chars: int = 6000) -> str:
    rows = session.exec(
        select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id, KnowledgeEntry.is_active == True)  # noqa: E712
    ).all()
    text = "\n\n".join(f"## {r.title}\n{r.content}" for r in rows)
    return text[:limit_chars]


def catalogue(session: Session, tenant_id: str) -> list[dict]:
    """What the desk can route, for the agent prompt."""
    return [
        {"department": d.code, "name": d.name, "handles": list(d.categories or []), "sla_hours": d.sla_hours}
        for d in departments(session, tenant_id)
    ]
