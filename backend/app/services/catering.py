"""Catering quote from the tenant's vendor / contract data (no hard-coded rates)."""

from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.org import Contract, Vendor


def _rate(value: Any) -> Optional[float]:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    return rate if rate > 0 else None


def catering_quote(session: Session, tenant_id: str, headcount: int) -> dict[str, Any]:
    settings = get_settings()
    preferred = (settings.catering_vendor_name or "").strip().lower()
    vendors = [
        v
        for v in session.exec(select(Vendor).where(Vendor.tenant_id == tenant_id)).all()
        if "cater" in (v.category or "").lower() and (v.status or "ACTIVE").upper() == "ACTIVE"
    ]
    contracts = [
        c
        for c in session.exec(select(Contract).where(Contract.tenant_id == tenant_id)).all()
        if (c.status or "").upper() == "ACTIVE"
    ]
    by_vendor = {c.vendor_id: c for c in contracts}

    vendor = next((v for v in vendors if preferred and preferred in (v.name or "").lower()), None)
    vendor = vendor or next((v for v in vendors if v.vendor_id in by_vendor), None)
    vendor = vendor or (vendors[0] if vendors else None)
    contract = by_vendor.get(vendor.vendor_id) if vendor else None

    rate, source = None, None
    if contract:
        rate, source = _rate((contract.rate_card or {}).get("unit_rate")), "contract"
    if rate is None and vendor:
        rate, source = _rate((vendor.pricing or {}).get("per_person")), "vendor_pricing"
    if rate is None:
        rate, source = _rate(settings.catering_default_rate), "default_rate"
    if rate is None:
        source = "missing"

    currency = (
        (contract.rate_card or {}).get("currency") if contract else None
    ) or ((vendor.pricing or {}).get("currency") if vendor else None) or "INR"
    return {
        "vendor": vendor.name if vendor else None,
        "vendor_id": vendor.vendor_id if vendor else None,
        "contract": contract.name if contract else None,
        "rate": rate,
        "rate_source": source,
        "headcount": headcount,
        "amount_ex_tax": round(rate * headcount, 2) if rate is not None else None,
        "currency": currency,
    }
