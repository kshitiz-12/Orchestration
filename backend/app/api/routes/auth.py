from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import create_access_token, verify_password
from app.models.org import Person
from app.schemas.api import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDep):
    user = session.exec(select(Person).where(Person.email == payload.email.lower())).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.email, extra={"role": user.role, "person_id": user.person_id})
    return TokenResponse(access_token=token)
