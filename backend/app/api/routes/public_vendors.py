"""Public vendor registration via invite token (no JWT)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import SessionDep
from app.services import vendor_lifecycle as vl

router = APIRouter(prefix="/public/vendors", tags=["public"])


class RegisterIn(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    cin: Optional[str] = None
    msme_number: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    registered_address: Optional[str] = None
    location: Optional[str] = None
    approved_services: list[str] = Field(default_factory=list)
    coverage_states: list[str] = Field(default_factory=list)
    coverage_cities: list[str] = Field(default_factory=list)
    documents: dict[str, Any] = Field(default_factory=dict)
    compliance: dict[str, Any] = Field(default_factory=dict)
    references: list[dict[str, Any]] = Field(default_factory=list)
    manpower: dict[str, Any] = Field(default_factory=dict)
    equipment: list[Any] = Field(default_factory=list)
    financial: dict[str, Any] = Field(default_factory=dict)
    sla_terms: dict[str, Any] = Field(default_factory=dict)
    pricing: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None
    coverage_rows: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/register/{token}")
def get_registration(token: str, session: SessionDep):
    try:
        vendor = vl.get_by_invite_token(session, token)
        return vl.public_registration_form(vendor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/register/{token}")
def submit_registration(token: str, body: RegisterIn, session: SessionDep):
    try:
        payload = body.model_dump(exclude_none=True)
        vendor = vl.register_by_token(session, token, payload)
        session.commit()
        return {
            "status": "submitted",
            "vendor_id": vendor.vendor_id,
            "name": vendor.name,
            "review_status": vendor.status,
            "score": vendor.score,
            "tier": vendor.vendor_tier,
            "message": "Registration received. Ops will review and activate you for work orders.",
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
