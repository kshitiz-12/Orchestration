"""PolicyRule master API — effective-dated control inputs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CompanyAdminDep, DashboardOpsDep, EntityDep, SessionDep, TenantDep
from app.models.org import PolicyRule, utcnow

router = APIRouter(prefix="/policies", tags=["policies"])


class PolicyCreate(BaseModel):
    code: str
    name: str
    rule_family: str
    condition: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    reason_template: Optional[str] = None
    priority: int = 100
    version: int = 1
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    entity_id: Optional[str] = None


def _ser(p: PolicyRule) -> dict[str, Any]:
    return {
        "policy_id": p.policy_id,
        "tenant_id": p.tenant_id,
        "entity_id": p.entity_id,
        "code": p.code,
        "name": p.name,
        "rule_family": p.rule_family,
        "condition": p.condition or {},
        "decision": p.decision or {},
        "reason_template": p.reason_template,
        "priority": p.priority,
        "version": p.version,
        "effective_from": p.effective_from,
        "effective_to": p.effective_to,
        "is_active": p.is_active,
    }


@router.get("")
def list_policies(
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    rule_family: Optional[str] = None,
) -> dict[str, Any]:
    stmt = select(PolicyRule).where(PolicyRule.tenant_id == tenant_id)
    if rule_family:
        stmt = stmt.where(PolicyRule.rule_family == rule_family.strip().upper())
    rows = session.exec(stmt.order_by(PolicyRule.rule_family, PolicyRule.priority)).all()
    return {"items": [_ser(r) for r in rows], "count": len(rows)}


@router.post("")
def create_policy(
    body: PolicyCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    entity_id: EntityDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    family = body.rule_family.strip().upper()
    allowed = {"ELIGIBILITY", "APPROVAL", "SLA", "RATE", "BUDGET", "EVIDENCE", "COMMUNICATION"}
    if family not in allowed:
        raise HTTPException(status_code=400, detail=f"rule_family must be one of {sorted(allowed)}")
    row = PolicyRule(
        tenant_id=tenant_id,
        entity_id=body.entity_id or entity_id,
        code=body.code.strip().upper(),
        name=body.name.strip(),
        rule_family=family,
        condition=body.condition or {},
        decision=body.decision or {},
        reason_template=body.reason_template,
        priority=body.priority,
        version=body.version,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _ser(row)


@router.patch("/{policy_id}/deactivate")
def deactivate_policy(
    policy_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: CompanyAdminDep,
) -> dict[str, Any]:
    row = session.get(PolicyRule, policy_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Policy not found")
    row.is_active = False
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    return _ser(row)
