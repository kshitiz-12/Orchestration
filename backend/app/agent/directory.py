"""Who handles what: department routing, with the env admin as the fallback for unset contacts.

Teams can cover the whole company or one place in the tree (a region, city, branch, building ...). Work goes to the
nearest team above the place it is about; a place with no team of its own is covered from further up, so a new branch
works the moment it is added.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from app.agent.company_seed import is_placeholder
from app.agent.places import chain_ids
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
    handover_info: Optional[str] = None
    # Admin team for the place the work is at (empty when only the central admin covers it)
    local_admins: list[str] = field(default_factory=list)


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


def _scope_rank(dept: Department, places: list[str]) -> Optional[int]:
    """0 = team of the place itself, 1 = its parent's ... len(places) = company-wide; None = covers somewhere else."""
    if not dept.location_id:
        return len(places)
    return places.index(dept.location_id) if dept.location_id in places else None


def _in_scope(rows: list[Department], places: list[str]) -> list[tuple[int, Department]]:
    out = [(rank, d) for d in rows if (rank := _scope_rank(d, places)) is not None]
    return sorted(out, key=lambda item: item[0])


def _family(code: str, base: str) -> bool:
    """FACILITIES, FACILITIES_PUNE and FACILITIES_BLR_WF are all the facilities team."""
    return code == base or code.startswith(f"{base}_")


def _cats(dept: Department) -> list[str]:
    return [str(c).strip().lower() for c in dept.categories or []]


def department_for(
    session: Session, tenant_id: str, category: str, location_id: Optional[str] = None
) -> Optional[Department]:
    from app.agent.playbooks import has_playbook, normalize_category, playbook_for

    cat = (category or "general").strip().lower()
    norm = normalize_category(cat)
    owner = playbook_for(norm).department if has_playbook(norm) else None
    places = chain_ids(session, tenant_id, location_id)
    ranked = _in_scope(departments(session, tenant_id), places)

    # Nearest scope wins; at the same scope a team that lists the category beats the category's usual owner.
    def strength(dept: Department) -> int:
        cats = _cats(dept)
        if cat in cats:
            return 3
        if norm in cats:
            return 2
        return 1 if owner and _family(dept.code, owner) else 0

    best: Optional[tuple[int, int, Department]] = None
    for rank, dept in ranked:
        s = strength(dept)
        if s and (best is None or (rank, -s) < (best[0], -best[1])):
            best = (rank, s, dept)
    if best:
        return best[2]
    return admin_team(session, tenant_id, location_id, ranked=ranked)


def admin_team(
    session: Session,
    tenant_id: str,
    location_id: Optional[str] = None,
    *,
    ranked: Optional[list[tuple[int, Department]]] = None,
) -> Optional[Department]:
    """The nearest admin team (ADMIN, ADMIN_PUNE ...) covering the place."""
    if ranked is None:
        ranked = _in_scope(departments(session, tenant_id), chain_ids(session, tenant_id, location_id))
    return next((d for _, d in ranked if _family(d.code, "ADMIN")), None)


def local_admin_team(session: Session, tenant_id: str, location_id: Optional[str]) -> Optional[Department]:
    """A branch/region admin team for the place; the company-wide ADMIN team is the central admin, not local."""
    if not location_id:
        return None
    team = admin_team(session, tenant_id, location_id)
    return team if team is not None and team.location_id else None


def handles_category(session: Session, tenant_id: str, category: str) -> bool:
    cat = (category or "").strip().lower()
    return any(cat in _cats(d) for d in departments(session, tenant_id))


def find_department(
    session: Session, tenant_id: str, text: str, location_id: Optional[str] = None
) -> Optional[Department]:
    """Match an admin's free-text team name ("facilities", "IT", "Travel Desk") to a department.

    With several branch teams of that name, the one covering the case's place is picked.
    """
    want = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if not want:
        return None
    rows = departments(session, tenant_id)
    places = chain_ids(session, tenant_id, location_id)

    def nearest(found: list[Department]) -> Optional[Department]:
        if not found:
            return None
        scoped = _in_scope(found, places)
        return scoped[0][1] if scoped else found[0]

    exact = [d for d in rows if want == d.code.lower() or want == re.sub(r"[^a-z0-9]+", " ", d.name.lower()).strip()]
    family = [d for d in rows if _family(d.code.lower(), want.replace(" ", "_")) and d not in exact]
    return nearest(exact + family) or nearest(
        [d for d in rows if want in d.name.lower() or d.code.lower().startswith(want)]
    )


def route_for_case(session: Session, tenant_id: str, facts: dict) -> Route:
    """Route for an existing case: an admin's team override wins over the category's default team."""
    location_id = facts.get("location_id")
    override = facts.get("department_override")
    if override:
        dept = next((d for d in departments(session, tenant_id) if d.code == override), None)
        if dept is not None:
            return _route_from(dept, local_admin_team(session, tenant_id, location_id))
    return route_for(session, tenant_id, facts.get("agent_category") or "general", location_id)


def route_for(session: Session, tenant_id: str, category: str, location_id: Optional[str] = None) -> Route:
    return _route_from(
        department_for(session, tenant_id, category, location_id),
        local_admin_team(session, tenant_id, location_id),
    )


def _route_from(dept: Optional[Department], local_admin: Optional[Department] = None) -> Route:
    central = _admin()
    local = _real([local_admin.primary_email, *(local_admin.backup_emails or [])]) if local_admin else []
    local_approver = (_real([local_admin.approver_email]) or local or [None])[0] if local_admin else None
    fallback = local or ([central] if central else [])
    if dept is None:
        return Route("ADMIN", "Admin", fallback, approver=local_approver or central, redirected_to_admin=True,
                     local_admins=local)
    recipients = _real([dept.primary_email, *(dept.backup_emails or [])])
    approver = (_real([dept.approver_email]) or [None])[0]
    redirected = not recipients
    if redirected:
        recipients = list(fallback)
    return Route(
        department_code=dept.code,
        department_name=dept.name,
        recipients=recipients,
        approver=approver or local_approver or central,
        sla_hours=dept.sla_hours or 24,
        spend_approval_limit=float(dept.spend_approval_limit or 0),
        redirected_to_admin=redirected,
        handover_info=(dept.handover_info or "").strip() or None,
        local_admins=local,
    )


def department_emails(session: Session, tenant_id: Optional[str] = None) -> set[str]:
    """Real department mailboxes; they may reply to work orders like the admin does.

    A team on a sub-address (facilities+pune@co.com) answers from the mailbox itself (facilities@co.com), so the
    base address counts as the team too.
    """
    stmt = select(Department).where(Department.is_active == True)  # noqa: E712
    if tenant_id:
        stmt = stmt.where(Department.tenant_id == tenant_id)
    out: set[str] = set()
    for dept in session.exec(stmt).all():
        for addr in _real([dept.primary_email, dept.approver_email, *(dept.backup_emails or [])]):
            out.update({addr, base_mailbox(addr)})
    return out


def base_mailbox(addr: str) -> str:
    local, _, domain = (addr or "").strip().lower().partition("@")
    return f"{local.split('+', 1)[0]}@{domain}" if domain else local


def knowledge_text(session: Session, tenant_id: str, limit_chars: int = 6000) -> str:
    rows = session.exec(
        select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id, KnowledgeEntry.is_active == True)  # noqa: E712
    ).all()
    text = "\n\n".join(f"## {r.title}\n{r.content}" for r in rows)
    return text[:limit_chars]


def catalogue(session: Session, tenant_id: str) -> list[dict]:
    """What the desk can route, for the agent prompt.

    Branch copies of a team are folded into one line so the prompt stays the same size with 5 or 500 branches;
    the desk picks the branch team itself once it knows where the work is.
    """
    out = []
    rows = sorted(departments(session, tenant_id), key=lambda d: (d.location_id is not None, d.code))
    seen: set[tuple[str, ...]] = set()
    for d in rows:
        handles = tuple(sorted(_cats(d)))
        if d.location_id and (handles in seen or not handles):
            continue
        seen.add(handles)
        row = {"department": d.code, "name": d.name, "handles": list(d.categories or []), "sla_hours": d.sla_hours}
        if (d.handover_info or "").strip() and not d.location_id:
            row["collect_from"] = d.handover_info.strip()
        out.append(row)
    return out
