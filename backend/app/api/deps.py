from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import AuthError, get_subject
from app.models.org import LegalEntity, Person, Tenant

security = HTTPBearer(auto_error=False)

# Dashboard roles that may operate the console / decide approvals / ingest mail.
DASHBOARD_OPS_ROLES = frozenset({"OPERATOR", "ADMIN", "COMPANY_ADMIN", "BRANCH_ADMIN"})
# Destructive / company-wide actions (demo reset, wipe-style imports).
COMPANY_ADMIN_ROLES = frozenset({"OPERATOR", "ADMIN", "COMPANY_ADMIN"})
# Finance / procurement segregation roles (SoD).
PROCUREMENT_ROLES = frozenset({"PROCUREMENT", "BUYER", "COMPANY_ADMIN", "ADMIN", "OPERATOR"})
FINANCE_ROLES = frozenset({"FINANCE", "AP_APPROVER", "COMPANY_ADMIN", "ADMIN", "OPERATOR"})
# Roles that must not self-approve commercial / vendor activation decisions.
SOD_BLOCKED_SELF_APPROVE = frozenset({"EMPLOYEE", "VENDOR"})


def get_db(session: Session = Depends(get_session)) -> Session:
    return session


def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    session: Session = Depends(get_db),
) -> Person:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        email = get_subject(creds.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = session.exec(select(Person).where(Person.email == email.lower())).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user


def get_tenant_id(
    user: Annotated[Person, Depends(get_current_user)],
    session: Session = Depends(get_db),
) -> str:
    """Tenant comes from the authenticated user — never from 'first tenant in DB'."""
    tid = (user.tenant_id or "").strip()
    if tid:
        tenant = session.get(Tenant, tid)
        if tenant is None:
            raise HTTPException(status_code=400, detail="User tenant not found")
        return tid
    raise HTTPException(status_code=400, detail="User has no tenant — re-invite or re-seed login")


def get_entity_id(
    user: Annotated[Person, Depends(get_current_user)],
    session: Session = Depends(get_db),
) -> Optional[str]:
    """Optional legal-entity scope from the authenticated user."""
    eid = (user.entity_id or "").strip() or None
    if not eid:
        return None
    entity = session.get(LegalEntity, eid)
    if entity is None or entity.tenant_id != user.tenant_id:
        raise HTTPException(status_code=400, detail="User legal entity not found")
    if (entity.status or "").upper() != "ACTIVE":
        raise HTTPException(status_code=403, detail="Legal entity inactive")
    return eid


def require_dashboard_ops(user: Annotated[Person, Depends(get_current_user)]) -> Person:
    role = (user.role or "").strip().upper()
    if role not in DASHBOARD_OPS_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ops dashboard role required")
    return user


def require_company_admin(user: Annotated[Person, Depends(get_current_user)]) -> Person:
    role = (user.role or "").strip().upper()
    if role not in COMPANY_ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Company admin role required")
    return user


def require_procurement(user: Annotated[Person, Depends(get_current_user)]) -> Person:
    role = (user.role or "").strip().upper()
    if role not in PROCUREMENT_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Procurement role required")
    return user


def require_finance(user: Annotated[Person, Depends(get_current_user)]) -> Person:
    role = (user.role or "").strip().upper()
    if role not in FINANCE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Finance role required")
    return user


def assert_not_self_approve(*, actor: Person, subject_email: Optional[str]) -> None:
    """SoD: actor cannot approve their own commercial request."""
    if not subject_email:
        return
    if (actor.email or "").strip().lower() == subject_email.strip().lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self-approval is not allowed")


def assert_site_access(user: Person, site_id: Optional[str]) -> None:
    """Site-scoped ops: BRANCH_ADMIN limited to home + allowed_site_ids; company admins unrestricted."""
    if not site_id:
        return
    role = (user.role or "").strip().upper()
    if role in COMPANY_ADMIN_ROLES or role == "OPERATOR":
        return
    allowed = set(user.allowed_site_ids or [])
    if user.site_id:
        allowed.add(user.site_id)
    if site_id not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site out of scope")


def user_site_scope(user: Person) -> Optional[set[str]]:
    """None = unrestricted; set = allowed site IDs for filtering lists."""
    role = (user.role or "").strip().upper()
    if role in COMPANY_ADMIN_ROLES or role == "OPERATOR":
        return None
    allowed = set(user.allowed_site_ids or [])
    if user.site_id:
        allowed.add(user.site_id)
    return allowed


SessionDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[Person, Depends(get_current_user)]
TenantDep = Annotated[str, Depends(get_tenant_id)]
EntityDep = Annotated[Optional[str], Depends(get_entity_id)]
DashboardOpsDep = Annotated[Person, Depends(require_dashboard_ops)]
CompanyAdminDep = Annotated[Person, Depends(require_company_admin)]
ProcurementDep = Annotated[Person, Depends(require_procurement)]
FinanceDep = Annotated[Person, Depends(require_finance)]
