"""Vendor lifecycle API — admin console + email invite (no separate vendor app)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import DashboardOpsDep, SessionDep, TenantDep
from app.connectors.factory import get_email_provider
from app.models.org import VendorCoverage
from app.services import vendor_lifecycle as vl
from app.services.communication import CommunicationService

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _comms(session, tenant_id: str) -> CommunicationService:
    email = get_email_provider(session, tenant_id)
    sender = email if email.is_connected() else None
    return CommunicationService(session, tenant_id, email_sender=sender)


class InviteIn(BaseModel):
    name: str
    contact_email: str
    category: str = "general"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    service_areas: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    send_email: bool = True


class ProfileIn(BaseModel):
    patch: dict[str, Any] = Field(default_factory=dict)


class CoverageIn(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ActivateIn(BaseModel):
    score: Optional[float] = None
    create_contract: bool = True
    notify: bool = True


class SuspendIn(BaseModel):
    reason: str
    blacklist: bool = False
    notify: bool = True


@router.get("")
def list_vendors(
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    status: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = False,
    q: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
):
    return vl.list_vendors(
        session,
        tenant_id,
        status=status,
        category=category,
        active_only=active_only,
        q=q,
        city=city,
        state=state,
    )


@router.get("/{vendor_id}")
def get_vendor(vendor_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep):
    try:
        vendor = vl._get(session, tenant_id, vendor_id)
        coverage = list(
            session.exec(
                select(VendorCoverage).where(
                    VendorCoverage.tenant_id == tenant_id, VendorCoverage.vendor_id == vendor_id
                )
            ).all()
        )
        return {"vendor": vendor, "coverage": coverage, "registration_url": vl.registration_url(vendor.invite_token or "") if vendor.invite_token else None}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/invite")
def invite(body: InviteIn, session: SessionDep, tenant_id: TenantDep, user: DashboardOpsDep):
    try:
        comms = _comms(session, tenant_id) if body.send_email else None
        vendor = vl.invite_vendor(
            session,
            tenant_id,
            name=body.name,
            contact_email=body.contact_email,
            category=body.category,
            contact_name=body.contact_name,
            contact_phone=body.contact_phone,
            service_areas=body.service_areas,
            invited_by=user.email,
            notes=body.notes,
            comms=comms,
        )
        session.commit()
        return {
            "vendor": vendor,
            "registration_url": vl.registration_url(vendor.invite_token or ""),
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{vendor_id}/resend-invite")
def resend_invite(vendor_id: str, session: SessionDep, tenant_id: TenantDep, user: DashboardOpsDep):
    try:
        vendor = vl.resend_invite(session, tenant_id, vendor_id, comms=_comms(session, tenant_id))
        session.commit()
        return {"vendor": vendor, "registration_url": vl.registration_url(vendor.invite_token or "")}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{vendor_id}")
def update_profile(
    vendor_id: str,
    body: ProfileIn,
    session: SessionDep,
    tenant_id: TenantDep,
    user: DashboardOpsDep,
):
    try:
        vendor = vl.update_profile(session, tenant_id, vendor_id, patch=body.patch, actor_email=user.email)
        session.commit()
        return vendor
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc).lower() else 400, str(exc)) from exc


@router.put("/{vendor_id}/coverage")
def set_coverage(
    vendor_id: str,
    body: CoverageIn,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
):
    try:
        rows = vl.set_coverage(session, tenant_id, vendor_id, body.rows)
        session.commit()
        return {"vendor_id": vendor_id, "coverage": rows}
    except ValueError as exc:
        raise HTTPException(404 if "not found" in str(exc).lower() else 400, str(exc)) from exc


@router.post("/{vendor_id}/score")
def score_vendor(vendor_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep):
    try:
        breakdown = vl.compute_score(session, tenant_id, vendor_id)
        session.commit()
        vendor = vl._get(session, tenant_id, vendor_id)
        return {"vendor_id": vendor_id, "score": vendor.score, "tier": vendor.vendor_tier, "breakdown": breakdown}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{vendor_id}/activate")
def activate(
    vendor_id: str,
    body: ActivateIn,
    session: SessionDep,
    tenant_id: TenantDep,
    user: DashboardOpsDep,
):
    try:
        vendor = vl.activate_vendor(
            session,
            tenant_id,
            vendor_id,
            actor_email=user.email,
            score=body.score,
            create_contract=body.create_contract,
            comms=_comms(session, tenant_id) if body.notify else None,
        )
        session.commit()
        return vendor
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{vendor_id}/suspend")
def suspend(
    vendor_id: str,
    body: SuspendIn,
    session: SessionDep,
    tenant_id: TenantDep,
    user: DashboardOpsDep,
):
    try:
        vendor = vl.suspend_vendor(
            session,
            tenant_id,
            vendor_id,
            reason=body.reason,
            actor_email=user.email,
            blacklist=body.blacklist,
            comms=_comms(session, tenant_id) if body.notify else None,
        )
        session.commit()
        return vendor
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/{vendor_id}/scorecard")
def scorecard(
    vendor_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _: DashboardOpsDep,
    days: int = 90,
):
    try:
        return vl.performance_scorecard(session, tenant_id, vendor_id, days=max(1, min(365, days)))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
