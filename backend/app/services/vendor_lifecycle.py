"""Vendor lifecycle (admin console + email): invite → register → score → activate.

ACTIVE vendors are the only ones the desk, resolution agent, and stock reorder use.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Optional

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.org import Contract, Vendor, VendorCoverage, utcnow
from app.services.ops_ledger import query_events, record

logger = get_logger(__name__)

STATUSES = frozenset({"INVITED", "UNDER_REVIEW", "ACTIVE", "SUSPENDED", "BLACKLISTED"})

DOC_KEYS = (
    "gst_certificate",
    "pan_card",
    "cin_certificate",
    "msme_certificate",
    "incorporation",
    "labour_license",
    "pf_registration",
    "esic_registration",
    "cancelled_cheque",
    "insurance_policy",
    "iso_certificate",
)

COMPLIANCE_KEYS = (
    "years_in_business",
    "employee_count",
    "annual_turnover",
    "pan_india_capability",
    "bfsi_clients",
    "background_verification",
    "police_verification",
    "escalation_matrix",
    "bcp",
    "data_privacy_policy",
)

INVITE_DAYS = 14


def frontend_base_url() -> str:
    settings = get_settings()
    raw = (settings.frontend_public_url or "").strip().rstrip("/")
    if raw:
        return raw
    origins = settings.cors_origin_list
    if origins and origins[0] != "*":
        return origins[0].rstrip("/")
    return (settings.public_base_url or "").rstrip("/")


def registration_url(token: str) -> str:
    base = frontend_base_url()
    if not base:
        return f"/vendor-register/{token}"
    return f"{base}/vendor-register/{token}"


def _mint_token() -> str:
    return secrets.token_urlsafe(32)


def invite_vendor(
    session: Session,
    tenant_id: str,
    *,
    name: str,
    contact_email: str,
    category: str = "general",
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    service_areas: Optional[list[str]] = None,
    invited_by: Optional[str] = None,
    notes: Optional[str] = None,
    comms: Any = None,
) -> Vendor:
    email = (contact_email or "").strip().lower()
    if not name.strip() or "@" not in email:
        raise ValueError("name and valid contact_email are required")
    existing = session.exec(
        select(Vendor).where(Vendor.tenant_id == tenant_id, Vendor.contact_email == email)
    ).first()
    if existing and existing.status == "ACTIVE":
        raise ValueError(f"Vendor already active: {existing.vendor_id}")
    vendor = existing or Vendor(
        tenant_id=tenant_id,
        name=name.strip()[:200],
        category=(category or "general").strip().lower()[:80],
        contact_email=email,
        status="INVITED",
    )
    vendor.name = name.strip()[:200]
    vendor.category = (category or vendor.category or "general").strip().lower()[:80]
    vendor.contact_email = email
    vendor.contact_name = (contact_name or vendor.contact_name or "")[:120] or None
    vendor.contact_phone = (contact_phone or vendor.contact_phone or "")[:40] or None
    vendor.status = "INVITED"
    vendor.invited_by = (invited_by or "").strip().lower() or vendor.invited_by
    vendor.invited_at = utcnow()
    vendor.invite_token = _mint_token()
    vendor.invite_expires_at = utcnow() + timedelta(days=INVITE_DAYS)
    vendor.registration_submitted_at = None
    vendor.notes = (notes or vendor.notes or "")[:1000] or None
    if service_areas:
        vendor.coverage_cities = list(dict.fromkeys([*(vendor.coverage_cities or []), *service_areas]))[:80]
    session.add(vendor)
    session.flush()
    record(
        session,
        tenant_id,
        event_type="VENDOR_INVITED",
        summary=f"Invited vendor {vendor.name} <{vendor.contact_email}>",
        actor_email=invited_by,
        actor_role="admin",
        category=vendor.category,
        payload={"vendor_id": vendor.vendor_id, "status": vendor.status},
    )
    if comms is not None:
        send_invite_email(comms, vendor)
    return vendor


def send_invite_email(comms: Any, vendor: Vendor) -> None:
    link = registration_url(vendor.invite_token or "")
    body = (
        f"Hello {vendor.contact_name or vendor.name},\n\n"
        f"You have been invited to register as a vendor for our workplace operations desk "
        f"({vendor.category}).\n\n"
        f"Please complete your registration within {INVITE_DAYS} days:\n{link}\n\n"
        "You will submit company details, documents, coverage, compliance and commercial information.\n"
        "After review we will activate your account for work orders.\n\n"
        f"{get_settings().mail_signature}\n"
    )
    try:
        comms.send(
            communication_type="INFORMATION_ONLY",
            recipients=[vendor.contact_email],
            subject=f"Vendor registration invite — {vendor.name}",
            body=body,
            idempotency_key=f"vendor-invite:{vendor.vendor_id}:{vendor.invite_token}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("vendor_invite_email_failed", vendor_id=vendor.vendor_id, error=str(exc)[:200])


def resend_invite(session: Session, tenant_id: str, vendor_id: str, *, comms: Any = None) -> Vendor:
    vendor = _get(session, tenant_id, vendor_id)
    if vendor.status not in {"INVITED", "UNDER_REVIEW"}:
        raise ValueError("Can only resend invite for INVITED or UNDER_REVIEW vendors")
    vendor.invite_token = _mint_token()
    vendor.invite_expires_at = utcnow() + timedelta(days=INVITE_DAYS)
    vendor.status = "INVITED"
    vendor.updated_at = utcnow()
    session.add(vendor)
    session.flush()
    if comms is not None:
        send_invite_email(comms, vendor)
    return vendor


def get_by_invite_token(session: Session, token: str) -> Vendor:
    tok = (token or "").strip()
    if not tok:
        raise ValueError("Invalid registration link")
    vendor = session.exec(select(Vendor).where(Vendor.invite_token == tok)).first()
    if vendor is None:
        raise ValueError("Invalid registration link")
    if vendor.invite_expires_at and vendor.invite_expires_at < utcnow():
        raise ValueError("Registration link has expired — ask ops to resend the invite")
    if vendor.status in {"SUSPENDED", "BLACKLISTED"}:
        raise ValueError("This vendor cannot register")
    return vendor


def register_by_token(session: Session, token: str, payload: dict[str, Any]) -> Vendor:
    """Public vendor self-registration via invite token."""
    vendor = get_by_invite_token(session, token)
    patch = dict(payload or {})
    # Never allow status/token override from public form
    for forbidden in (
        "status",
        "invite_token",
        "invite_expires_at",
        "tenant_id",
        "vendor_id",
        "score",
        "vendor_tier",
        "activated_at",
    ):
        patch.pop(forbidden, None)
    _apply_profile(vendor, patch)
    vendor.status = "UNDER_REVIEW"
    vendor.registration_submitted_at = utcnow()
    vendor.updated_at = utcnow()
    session.add(vendor)
    session.flush()
    # Optional coverage rows in payload
    if isinstance(payload.get("coverage_rows"), list):
        set_coverage(session, vendor.tenant_id, vendor.vendor_id, payload["coverage_rows"])
    compute_score(session, vendor.tenant_id, vendor.vendor_id)
    session.refresh(vendor)
    record(
        session,
        vendor.tenant_id,
        event_type="VENDOR_REGISTERED",
        summary=f"Vendor registration submitted: {vendor.name}",
        actor_email=vendor.contact_email,
        actor_role="vendor",
        category=vendor.category,
        payload={"vendor_id": vendor.vendor_id},
    )
    return vendor


def _apply_profile(vendor: Vendor, patch: dict[str, Any]) -> None:
    allowed = {
        "name",
        "legal_name",
        "category",
        "gstin",
        "pan",
        "cin",
        "msme_number",
        "contact_name",
        "contact_phone",
        "website",
        "registered_address",
        "location",
        "approved_services",
        "coverage_states",
        "coverage_cities",
        "coverage_location_ids",
        "documents",
        "compliance",
        "references",
        "manpower",
        "equipment",
        "financial",
        "sla_terms",
        "pricing",
        "notes",
    }
    for key, value in (patch or {}).items():
        if key in allowed:
            setattr(vendor, key, value)


def update_profile(
    session: Session,
    tenant_id: str,
    vendor_id: str,
    *,
    patch: dict[str, Any],
    actor_email: Optional[str] = None,
) -> Vendor:
    vendor = _get(session, tenant_id, vendor_id)
    _apply_profile(vendor, patch or {})
    if vendor.status == "INVITED":
        vendor.status = "UNDER_REVIEW"
    vendor.updated_at = utcnow()
    session.add(vendor)
    session.flush()
    record(
        session,
        tenant_id,
        event_type="VENDOR_PROFILE_UPDATED",
        summary=f"Vendor profile updated: {vendor.name}",
        actor_email=actor_email,
        actor_role="admin",
        category=vendor.category,
        payload={"vendor_id": vendor.vendor_id, "status": vendor.status},
    )
    return vendor


def set_coverage(
    session: Session,
    tenant_id: str,
    vendor_id: str,
    rows: list[dict[str, Any]],
) -> list[VendorCoverage]:
    vendor = _get(session, tenant_id, vendor_id)
    for old in session.exec(
        select(VendorCoverage).where(
            VendorCoverage.tenant_id == tenant_id, VendorCoverage.vendor_id == vendor_id
        )
    ).all():
        session.delete(old)
    session.flush()
    out: list[VendorCoverage] = []
    states, cities, locs = [], [], []
    for row in rows or []:
        cov = VendorCoverage(
            tenant_id=tenant_id,
            vendor_id=vendor_id,
            state=(row.get("state") or None),
            city=(row.get("city") or None),
            location_id=row.get("location_id"),
            team_count=int(row.get("team_count") or 0),
            notes=(row.get("notes") or None),
        )
        session.add(cov)
        out.append(cov)
        if cov.state:
            states.append(cov.state)
        if cov.city:
            cities.append(cov.city)
        if cov.location_id:
            locs.append(cov.location_id)
    vendor.coverage_states = list(dict.fromkeys(states))
    vendor.coverage_cities = list(dict.fromkeys(cities))
    vendor.coverage_location_ids = list(dict.fromkeys(locs))
    vendor.updated_at = utcnow()
    session.add(vendor)
    session.flush()
    return out


def compute_score(session: Session, tenant_id: str, vendor_id: str) -> dict[str, Any]:
    """Deterministic 0–100 scores from submitted profile fields only."""
    vendor = _get(session, tenant_id, vendor_id)
    docs = vendor.documents or {}
    doc_hits = sum(1 for k in DOC_KEYS if docs.get(k) in (True, "yes", "YES", "provided", "uploaded", 1))
    technical = min(100.0, (doc_hits / max(len(DOC_KEYS), 1)) * 70 + (15 if vendor.approved_services else 0) + (15 if vendor.gstin and vendor.pan else 0))

    states = len(vendor.coverage_states or [])
    cities = len(vendor.coverage_cities or [])
    locs = len(vendor.coverage_location_ids or [])
    coverage = min(100.0, states * 12 + cities * 4 + locs * 8 + (20 if states or cities or locs else 0))

    comp = vendor.compliance or {}
    comp_hits = sum(1 for k in COMPLIANCE_KEYS if comp.get(k) not in (None, "", False, 0))
    compliance = min(100.0, (comp_hits / max(len(COMPLIANCE_KEYS), 1)) * 100)

    fin = vendor.financial or {}
    fin_hits = sum(1 for k in ("annual_turnover", "credit_rating", "payment_terms", "gst_compliant") if fin.get(k) not in (None, ""))
    financial = min(100.0, fin_hits * 25)

    mp = vendor.manpower or {}
    staff = float(mp.get("permanent_employees") or mp.get("total") or 0)
    manpower_score = min(100.0, 20 + (staff / 5) if staff else (10 if mp else 0))

    overall = round(
        technical * 0.25 + coverage * 0.25 + compliance * 0.25 + financial * 0.15 + manpower_score * 0.10,
        1,
    )
    breakdown = {
        "technical": round(technical, 1),
        "coverage": round(coverage, 1),
        "compliance": round(compliance, 1),
        "financial": round(financial, 1),
        "manpower": round(manpower_score, 1),
        "overall": overall,
    }
    vendor.score = overall
    vendor.score_breakdown = breakdown
    if overall >= 80:
        vendor.vendor_tier = "PREFERRED"
    elif overall >= 55:
        vendor.vendor_tier = "APPROVED"
    else:
        vendor.vendor_tier = "CONDITIONAL"
    vendor.updated_at = utcnow()
    session.add(vendor)
    session.flush()
    return breakdown


def activate_vendor(
    session: Session,
    tenant_id: str,
    vendor_id: str,
    *,
    actor_email: Optional[str] = None,
    score: Optional[float] = None,
    create_contract: bool = True,
    comms: Any = None,
) -> Vendor:
    vendor = _get(session, tenant_id, vendor_id)
    if vendor.status == "BLACKLISTED":
        raise ValueError("Cannot activate a blacklisted vendor")
    if vendor.score is None or not vendor.score_breakdown:
        compute_score(session, tenant_id, vendor_id)
        session.refresh(vendor)
    if score is not None:
        vendor.score = float(score)
    vendor.status = "ACTIVE"
    vendor.activated_at = utcnow()
    vendor.suspended_reason = None
    vendor.invite_token = None
    vendor.updated_at = utcnow()
    if create_contract and not vendor.contract_id:
        contract = Contract(
            tenant_id=tenant_id,
            vendor_id=vendor.vendor_id,
            name=f"{vendor.name} — {vendor.category} AMC",
            rate_card=dict(vendor.pricing or {}),
            status="ACTIVE",
            start_date=utcnow().date().isoformat(),
        )
        session.add(contract)
        session.flush()
        vendor.contract_id = contract.contract_id
    session.add(vendor)
    session.flush()
    record(
        session,
        tenant_id,
        event_type="VENDOR_ACTIVATED",
        summary=f"Activated vendor {vendor.name} (score {vendor.score})",
        actor_email=actor_email,
        actor_role="admin",
        category=vendor.category,
        payload={"vendor_id": vendor.vendor_id, "tier": vendor.vendor_tier, "score": vendor.score},
    )
    if comms is not None:
        try:
            comms.send(
                communication_type="INFORMATION_ONLY",
                recipients=[vendor.contact_email],
                subject=f"Vendor activated — {vendor.name}",
                body=(
                    f"Hello {vendor.contact_name or vendor.name},\n\n"
                    f"Your vendor registration has been activated (tier: {vendor.vendor_tier}, "
                    f"score: {vendor.score}). You may receive work orders by email for "
                    f"{vendor.category} services.\n\n{get_settings().mail_signature}\n"
                ),
                idempotency_key=f"vendor-activated:{vendor.vendor_id}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vendor_activate_email_failed", error=str(exc)[:160])
    return vendor


def suspend_vendor(
    session: Session,
    tenant_id: str,
    vendor_id: str,
    *,
    reason: str,
    actor_email: Optional[str] = None,
    blacklist: bool = False,
    comms: Any = None,
) -> Vendor:
    vendor = _get(session, tenant_id, vendor_id)
    vendor.status = "BLACKLISTED" if blacklist else "SUSPENDED"
    vendor.suspended_reason = (reason or "")[:500] or None
    vendor.updated_at = utcnow()
    session.add(vendor)
    session.flush()
    record(
        session,
        tenant_id,
        event_type="VENDOR_BLACKLISTED" if blacklist else "VENDOR_SUSPENDED",
        summary=f"{vendor.status.title()} vendor {vendor.name}: {reason[:200]}",
        actor_email=actor_email,
        actor_role="admin",
        category=vendor.category,
        payload={"vendor_id": vendor.vendor_id, "reason": reason[:500]},
    )
    if comms is not None:
        try:
            comms.send(
                communication_type="INFORMATION_ONLY",
                recipients=[vendor.contact_email],
                subject=f"Vendor status: {vendor.status} — {vendor.name}",
                body=(
                    f"Hello {vendor.contact_name or vendor.name},\n\n"
                    f"Your vendor status is now {vendor.status}.\nReason: {reason}\n\n"
                    f"{get_settings().mail_signature}\n"
                ),
                idempotency_key=f"vendor-suspend:{vendor.vendor_id}:{vendor.status}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("vendor_suspend_email_failed", error=str(exc)[:160])
    return vendor


def list_vendors(
    session: Session,
    tenant_id: str,
    *,
    status: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = False,
    q: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
) -> list[Vendor]:
    query = select(Vendor).where(Vendor.tenant_id == tenant_id)
    if active_only:
        query = query.where(Vendor.status == "ACTIVE")
    elif status:
        query = query.where(Vendor.status == status.upper())
    if category:
        query = query.where(Vendor.category == category.lower())
    rows = list(session.exec(query.order_by(col(Vendor.name))).all())
    if city:
        c = city.lower()
        rows = [v for v in rows if c in " ".join(v.coverage_cities or []).lower() or c in (v.location or "").lower()]
    if state:
        s = state.lower()
        rows = [v for v in rows if s in " ".join(v.coverage_states or []).lower()]
    if q:
        needle = q.lower()
        rows = [
            v
            for v in rows
            if needle in (v.name or "").lower()
            or needle in (v.contact_email or "").lower()
            or needle in (v.gstin or "").lower()
            or needle in (v.pan or "").lower()
            or needle in (v.category or "").lower()
        ]
    return rows


def vendors_for_location(
    session: Session,
    tenant_id: str,
    *,
    location_id: Optional[str],
    category: Optional[str] = None,
) -> list[Vendor]:
    """ACTIVE vendors covering a location, preferred/higher score first."""
    rows = list_vendors(session, tenant_id, active_only=True, category=category)
    if location_id:
        filtered = []
        for v in rows:
            locs = v.coverage_location_ids or []
            if not locs or location_id in locs:
                filtered.append(v)
        rows = filtered
    rows.sort(
        key=lambda v: (
            0 if (v.vendor_tier or "") == "PREFERRED" else 1 if (v.vendor_tier or "") == "APPROVED" else 2,
            -(float(v.score or 0)),
            v.name or "",
        )
    )
    return rows


def performance_scorecard(session: Session, tenant_id: str, vendor_id: str, *, days: int = 90) -> dict[str, Any]:
    """Ledger-backed performance only — no invented metrics."""
    vendor = _get(session, tenant_id, vendor_id)
    events = query_events(
        session,
        tenant_id,
        event_types=["TEAM_DONE", "WORK_ORDER_SENT", "SPEND_RECORDED", "CLOSED", "VENDOR_ASSIGNED"],
        category=vendor.category,
        days=days,
        limit=300,
    )
    related = [
        e
        for e in events
        if vendor.name.lower() in (e.summary or "").lower()
        or vendor.vendor_id in str((e.payload or {}).get("vendor_id") or "")
        or (vendor.category and (e.category or "") == vendor.category)
    ]
    spend = sum(float(e.amount or 0) for e in related if e.amount is not None)
    done = sum(1 for e in related if e.event_type in {"TEAM_DONE", "CLOSED"})
    wos = sum(1 for e in related if e.event_type == "WORK_ORDER_SENT")
    return {
        "vendor_id": vendor.vendor_id,
        "name": vendor.name,
        "status": vendor.status,
        "tier": vendor.vendor_tier,
        "score": vendor.score,
        "score_breakdown": vendor.score_breakdown or {},
        "days": days,
        "work_orders_seen": wos,
        "completions_seen": done,
        "spend_recorded": round(spend, 2),
        "currency": "INR",
        "recent": [
            {
                "when": e.occurred_at.isoformat(),
                "type": e.event_type,
                "case": e.case_reference,
                "summary": e.summary,
                "amount": e.amount,
            }
            for e in related[:25]
        ],
        "note": "Metrics are counted from operational ledger rows linked by category/name; empty means nothing recorded yet.",
    }


def _get(session: Session, tenant_id: str, vendor_id: str) -> Vendor:
    vendor = session.get(Vendor, vendor_id)
    if not vendor or vendor.tenant_id != tenant_id:
        raise ValueError("Vendor not found")
    return vendor


def public_registration_form(vendor: Vendor) -> dict[str, Any]:
    return {
        "vendor_id": vendor.vendor_id,
        "name": vendor.name,
        "category": vendor.category,
        "contact_email": vendor.contact_email,
        "contact_name": vendor.contact_name,
        "status": vendor.status,
        "expires_at": vendor.invite_expires_at.isoformat() if vendor.invite_expires_at else None,
        "document_keys": list(DOC_KEYS),
        "compliance_keys": list(COMPLIANCE_KEYS),
        "existing": {
            "legal_name": vendor.legal_name,
            "gstin": vendor.gstin,
            "pan": vendor.pan,
            "documents": vendor.documents or {},
            "compliance": vendor.compliance or {},
            "coverage_cities": vendor.coverage_cities or [],
            "coverage_states": vendor.coverage_states or [],
        },
    }
