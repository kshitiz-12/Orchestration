"""Legal entity master — multi-entity isolation (V3 Phase 1)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CompanyAdminDep, DashboardOpsDep, SessionDep, TenantDep
from app.models.org import LegalEntity, utcnow

router = APIRouter(prefix="/entities", tags=["entities"])


class EntityCreate(BaseModel):
    code: str
    legal_name: str
    country: str = "IN"
    currency: str = "INR"
    tax_ids: dict[str, Any] = Field(default_factory=dict)
    registrations: dict[str, Any] = Field(default_factory=dict)
    effective_from: Optional[str] = None


class EntityUpdate(BaseModel):
    legal_name: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    tax_ids: Optional[dict[str, Any]] = None
    registrations: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None


def _serialize(e: LegalEntity) -> dict[str, Any]:
    return {
        "entity_id": e.entity_id,
        "tenant_id": e.tenant_id,
        "code": e.code,
        "legal_name": e.legal_name,
        "country": e.country,
        "currency": e.currency,
        "tax_ids": e.tax_ids or {},
        "registrations": e.registrations or {},
        "status": e.status,
        "effective_from": e.effective_from,
        "effective_to": e.effective_to,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


@router.get("")
def list_entities(
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    status_filter: Optional[str] = None,
) -> dict[str, Any]:
    stmt = select(LegalEntity).where(LegalEntity.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(LegalEntity.status == status_filter.strip().upper())
    rows = session.exec(stmt.order_by(LegalEntity.code)).all()
    return {"items": [_serialize(r) for r in rows], "count": len(rows)}


@router.post("")
def create_entity(
    body: EntityCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="code required")
    existing = session.exec(
        select(LegalEntity).where(LegalEntity.tenant_id == tenant_id, LegalEntity.code == code)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Entity code already exists")
    row = LegalEntity(
        tenant_id=tenant_id,
        code=code,
        legal_name=body.legal_name.strip(),
        country=(body.country or "IN").strip().upper(),
        currency=(body.currency or "INR").strip().upper(),
        tax_ids=body.tax_ids or {},
        registrations=body.registrations or {},
        effective_from=body.effective_from,
        status="ACTIVE",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)


@router.get("/{entity_id}")
def get_entity(
    entity_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    row = session.get(LegalEntity, entity_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    return _serialize(row)


@router.patch("/{entity_id}")
def update_entity(
    entity_id: str,
    body: EntityUpdate,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    row = session.get(LegalEntity, entity_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    data = body.model_dump(exclude_unset=True)
    for key, val in data.items():
        if key == "status" and val is not None:
            setattr(row, key, str(val).strip().upper())
        elif key in {"country", "currency"} and val is not None:
            setattr(row, key, str(val).strip().upper())
        else:
            setattr(row, key, val)
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize(row)
