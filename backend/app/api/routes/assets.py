"""Asset lifecycle APIs (M03)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import DashboardOpsDep, SessionDep, TenantDep
from app.services.asset_lifecycle import AssetLifecycleService

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetCreate(BaseModel):
    type: str
    name: str
    location_id: Optional[str] = None
    vendor_id: Optional[str] = None
    tag: Optional[str] = None
    assignee_email: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class AssetStatusBody(BaseModel):
    status: str
    reason: Optional[str] = None


class AssetReassignBody(BaseModel):
    location_id: Optional[str] = None
    assignee_email: Optional[str] = None


def _ser(a) -> dict[str, Any]:
    return {
        "asset_id": a.asset_id,
        "type": a.type,
        "name": a.name,
        "status": a.status,
        "location_id": a.location_id,
        "vendor_id": a.vendor_id,
        "tag": a.tag,
        "assignee_email": a.assignee_email,
        "attributes": a.attributes or {},
    }


@router.get("")
def list_assets(
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    status: Optional[str] = None,
    type: Optional[str] = None,
) -> dict[str, Any]:
    rows = AssetLifecycleService(session, tenant_id).list(status=status, type=type)
    return {"items": [_ser(r) for r in rows], "count": len(rows)}


@router.post("")
def create_asset(
    body: AssetCreate,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    asset = AssetLifecycleService(session, tenant_id).register(
        type=body.type,
        name=body.name,
        location_id=body.location_id,
        vendor_id=body.vendor_id,
        tag=body.tag,
        assignee_email=body.assignee_email,
        attributes=body.attributes,
    )
    return _ser(asset)


@router.post("/{asset_id}/status")
def set_status(
    asset_id: str,
    body: AssetStatusBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    return _ser(AssetLifecycleService(session, tenant_id).set_status(asset_id, body.status, reason=body.reason))


@router.post("/{asset_id}/reassign")
def reassign(
    asset_id: str,
    body: AssetReassignBody,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
) -> dict[str, Any]:
    if body.location_id is None and body.assignee_email is None:
        raise HTTPException(status_code=400, detail="location_id or assignee_email required")
    return _ser(
        AssetLifecycleService(session, tenant_id).reassign(
            asset_id, location_id=body.location_id, assignee_email=body.assignee_email
        )
    )
