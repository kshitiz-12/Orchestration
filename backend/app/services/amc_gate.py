"""AMC coverage gate before facilities corrective buy/dispatch (M04/M05)."""

from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session, select

from app.models.org import Contract, Vendor
from app.services.amc_contracts import AmcObligation

_FACILITIES_CATS = {
    "maintenance",
    "hvac",
    "electrical",
    "plumbing",
    "furniture",
    "pest_control",
    "waste_disposal",
    "health_safety",
}


def amc_coverage_hint(
    session: Session,
    tenant_id: str,
    *,
    category: str,
    asset_id: Optional[str] = None,
    location_id: Optional[str] = None,
) -> dict[str, Any]:
    """Return active AMC obligations that should be used before buying outside."""
    cat = (category or "").strip().lower()
    if cat not in _FACILITIES_CATS:
        return {"applicable": False, "obligations": []}

    stmt = select(AmcObligation).where(
        AmcObligation.tenant_id == tenant_id,
        AmcObligation.status == "ACTIVE",
    )
    rows = list(session.exec(stmt).all())
    matched = []
    for ob in rows:
        if asset_id and ob.asset_id and ob.asset_id != asset_id:
            continue
        contract = session.get(Contract, ob.contract_id)
        vendor = session.get(Vendor, contract.vendor_id) if contract else None
        if vendor and (vendor.status or "").upper() != "ACTIVE":
            continue
        matched.append(
            {
                "obligation_id": ob.obligation_id,
                "title": ob.title,
                "contract_id": ob.contract_id,
                "vendor_id": vendor.vendor_id if vendor else None,
                "vendor_name": vendor.name if vendor else None,
                "vendor_email": vendor.contact_email if vendor else None,
                "sla_hours": ob.sla_hours,
                "prefer_amc": True,
            }
        )
    return {
        "applicable": True,
        "has_coverage": bool(matched),
        "obligations": matched,
        "guidance": (
            "Use AMC vendor call — do not raise a new purchase without coverage check"
            if matched
            else "No active AMC obligation found for this category/asset"
        ),
    }
