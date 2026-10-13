"""Asset lifecycle (M03) — register, locate, custody, status transitions."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.org import Asset, utcnow
from app.services.outbox import OutboxService


class AssetLifecycleService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def register(
        self,
        *,
        type: str,
        name: str,
        location_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        tag: Optional[str] = None,
        assignee_email: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> Asset:
        if tag:
            existing = self.session.exec(
                select(Asset).where(Asset.tenant_id == self.tenant_id, Asset.tag == tag)
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="Asset tag already exists")
        asset = Asset(
            tenant_id=self.tenant_id,
            type=type.strip().upper(),
            name=name.strip(),
            location_id=location_id,
            vendor_id=vendor_id,
            tag=tag,
            assignee_email=(assignee_email or "").strip().lower() or None,
            status="ACTIVE",
            attributes=attributes or {},
        )
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="ASSET.REGISTERED",
            payload={"asset_id": asset.asset_id, "tag": asset.tag, "type": asset.type},
            idempotency_key=f"asset-reg-{asset.asset_id}",
            aggregate_type="Asset",
            aggregate_id=asset.asset_id,
        )
        return asset

    def set_status(self, asset_id: str, status: str, *, reason: Optional[str] = None) -> Asset:
        asset = self.session.get(Asset, asset_id)
        if not asset or asset.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Asset not found")
        allowed = {"ACTIVE", "IN_REPAIR", "IN_TRANSIT", "DISPOSED", "LOST", "INACTIVE"}
        st = status.strip().upper()
        if st not in allowed:
            raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")
        before = asset.status
        asset.status = st
        attrs = dict(asset.attributes or {})
        if reason:
            attrs["status_reason"] = reason
        attrs["status_history"] = list(attrs.get("status_history") or []) + [
            {"from": before, "to": st, "at": utcnow().isoformat(), "reason": reason}
        ]
        asset.attributes = attrs
        asset.updated_at = utcnow()
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        return asset

    def reassign(
        self,
        asset_id: str,
        *,
        location_id: Optional[str] = None,
        assignee_email: Optional[str] = None,
    ) -> Asset:
        asset = self.session.get(Asset, asset_id)
        if not asset or asset.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Asset not found")
        if location_id is not None:
            asset.location_id = location_id
        if assignee_email is not None:
            asset.assignee_email = assignee_email.strip().lower() or None
        asset.updated_at = utcnow()
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        return asset

    def list(self, *, status: Optional[str] = None, type: Optional[str] = None) -> list[Asset]:
        stmt = select(Asset).where(Asset.tenant_id == self.tenant_id)
        if status:
            stmt = stmt.where(Asset.status == status.strip().upper())
        if type:
            stmt = stmt.where(Asset.type == type.strip().upper())
        return list(self.session.exec(stmt.order_by(Asset.name)).all())
