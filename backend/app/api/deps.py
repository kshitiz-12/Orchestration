from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import AuthError, get_subject
from app.models.org import Person, Tenant

security = HTTPBearer(auto_error=False)


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
    return user


def get_tenant_id(session: Session = Depends(get_db)) -> str:
    tenant = session.exec(select(Tenant)).first()
    if not tenant:
        raise HTTPException(status_code=400, detail="No tenant seeded — run scripts/seed.py")
    return tenant.tenant_id


SessionDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[Person, Depends(get_current_user)]
TenantDep = Annotated[str, Depends(get_tenant_id)]
