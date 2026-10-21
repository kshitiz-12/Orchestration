"""Decide a request from the records for that thing at that branch.

Warranty, AMC, repair count, repeat complaints, stock, issued equipment and vendor
standing are read from stored rows. A missing record stays unknown. Counts are not invented.
Company overrides live on BusinessRule RECORD_LIMITS, or on the asset as replace_after.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.ops_ledger import OpsLedgerEvent
from app.models.org import Asset, BusinessRule, Contract, StockSku, Vendor
from app.services.amc_gate import amc_coverage_hint

_ASSET_CATEGORIES = {
    "hvac", "electrical", "plumbing", "furniture", "maintenance", "laptop", "access_card", "phone_sim", "asset",
}
_REPEAT_CATEGORIES = {"housekeeping", "pantry", "pest_control", "cleaning"}
_TYPE_FOR = {
    "hvac": "HVAC",
    "electrical": "ELECTRICAL",
    "plumbing": "PLUMBING",
    "furniture": "FURNITURE",
    "maintenance": "MAINTENANCE",
    "laptop": "LAPTOP",
    "access_card": "ACCESS_CARD",
    "phone_sim": "PHONE",
    "asset": "ASSET",
}
_KIND_WORDS = {
    "hvac": ("ac", "a/c", "hvac", "air condition"),
    "electrical": ("fan", "light", "socket", "ups"),
    "plumbing": ("tap", "leak", "washroom", "toilet"),
    "furniture": ("chair", "desk", "table", "drawer"),
    "laptop": ("laptop", "notebook"),
    "access_card": ("access card", "id card", "badge"),
}
_DEFAULT_REPLACE_AFTER = {
    "hvac": 6,
    "electrical": 8,
    "plumbing": 6,
    "furniture": 4,
    "maintenance": 6,
    "laptop": 3,
    "access_card": 3,
    "phone_sim": 2,
    "asset": 6,
}
_DEFAULT_REPEAT_AFTER = {"housekeeping": 4, "pantry": 4, "pest_control": 3, "cleaning": 4}
_DEFAULT_VENDOR_MISSES = 3


def _limits(session: Session, tenant_id: str) -> dict[str, Any]:
    row = session.exec(
        select(BusinessRule).where(
            BusinessRule.tenant_id == tenant_id,
            BusinessRule.code == "RECORD_LIMITS",
            BusinessRule.is_active == True,  # noqa: E712
        )
    ).first()
    return dict(row.config or {}) if row else {}


def _replace_after(limits: dict[str, Any], category: str, asset: Optional[Asset]) -> int:
    if asset is not None:
        raw = (asset.attributes or {}).get("replace_after")
        if isinstance(raw, (int, float)) and int(raw) > 0:
            return int(raw)
    custom = (limits.get("replace_after") or {}).get(category)
    if isinstance(custom, (int, float)) and int(custom) > 0:
        return int(custom)
    return int(_DEFAULT_REPLACE_AFTER.get(category, 6))


def _repeat_after(limits: dict[str, Any], category: str) -> int:
    custom = (limits.get("repeat_after") or {}).get(category)
    if isinstance(custom, (int, float)) and int(custom) > 0:
        return int(custom)
    return int(_DEFAULT_REPEAT_AFTER.get(category, 4))


def _parse_date(value: Any) -> Optional[date]:
    text = str(value or "").strip()[:10]
    if not re.match(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _place_token(text: str) -> str:
    raw = text or ""
    match = re.search(r"\b(?:room|rm|cabin)\s*([a-z0-9-]+)", raw, re.I)
    if match:
        return match.group(1).lower()
    match = re.search(r"\b(\d+(?:st|nd|rd|th)\s+floor)\b", raw, re.I)
    if match:
        return match.group(1).lower()
    return ""


def _request_text(outcome: Any) -> str:
    facts = getattr(outcome, "facts", None) or {}
    details = facts.get("details") or {}
    parts = [
        getattr(outcome, "title", "") or "",
        facts.get("raw_request") or "",
        details.get("location") or "",
        details.get("room") or "",
        details.get("issue") or "",
        details.get("item") or "",
        details.get("description") or "",
    ]
    return " ".join(str(p) for p in parts if p)


def _assets_at(session: Session, tenant_id: str, location_id: Optional[str]) -> list[Asset]:
    if not location_id:
        return []
    rows = session.exec(select(Asset).where(Asset.tenant_id == tenant_id)).all()
    return [a for a in rows if a.location_id == location_id]


def _match_asset(assets: list[Asset], category: str, text: str, details: dict) -> Optional[Asset]:
    tag = str(details.get("asset_tag") or details.get("tag") or "").strip()
    if tag:
        found = next((a for a in assets if (a.tag or "").lower() == tag.lower()), None)
        if found:
            return found
    room = _place_token(text)
    words = _KIND_WORDS.get(category, ())
    want_type = _TYPE_FOR.get(category, "")
    best: Optional[Asset] = None
    best_score = 0
    for asset in assets:
        blob = " ".join(
            [
                asset.name or "",
                asset.tag or "",
                asset.type or "",
                str((asset.attributes or {}).get("room") or ""),
            ]
        ).lower()
        score = 0
        if want_type and (asset.type or "").upper() == want_type:
            score += 2
        if room and room in blob:
            score += 3
        if any(word in blob or word in text.lower() for word in words):
            score += 1
        if score > best_score:
            best, best_score = asset, score
    if best is None or not (best_score >= 3 or (best_score >= 2 and room)):
        return None
    peers = [a for a in assets if want_type and (a.type or "").upper() == want_type]
    if len(peers) > 1 and not (room and room in " ".join([best.name or "", str((best.attributes or {}).get("room") or "")]).lower()):
        return None
    return best


def _completions(session: Session, tenant_id: str, location_id: Optional[str], category: str) -> list[OpsLedgerEvent]:
    rows = session.exec(
        select(OpsLedgerEvent).where(
            OpsLedgerEvent.tenant_id == tenant_id,
            OpsLedgerEvent.event_type == "TEAM_DONE",
        )
    ).all()
    out = []
    for row in rows:
        if location_id and row.location_id and row.location_id != location_id:
            continue
        if category and row.category and row.category != category:
            continue
        out.append(row)
    return out


def _repair_count(rows: list[OpsLedgerEvent], asset: Optional[Asset], place: str, outcome_id: Optional[str]) -> Optional[int]:
    if asset is None and not place:
        return None
    count = 0
    for row in rows:
        if outcome_id and row.outcome_id == outcome_id:
            continue
        tag = (asset.tag or "") if asset else ""
        blob = f"{row.summary or ''} {row.asset_tag or ''}".lower()
        if tag and ((row.asset_tag or "").lower() == tag.lower() or tag.lower() in blob):
            count += 1
        elif place and place in blob:
            count += 1
        elif asset and asset.asset_id and asset.asset_id in str((row.payload or {}).get("asset_id") or ""):
            count += 1
    return count


def _warranty(asset: Optional[Asset]) -> tuple[str, Optional[str]]:
    if asset is None:
        return "unknown", None
    end = _parse_date((asset.attributes or {}).get("warranty_end"))
    if end is None:
        return "unknown", None
    if end >= date.today():
        return "active", end.isoformat()
    return "expired", end.isoformat()


def _vendor_problem(session: Session, amc: dict) -> Optional[str]:
    obligations = amc.get("obligations") or []
    if not obligations:
        return None
    first = obligations[0]
    vendor = session.get(Vendor, first.get("vendor_id")) if first.get("vendor_id") else None
    contract = session.get(Contract, first.get("contract_id")) if first.get("contract_id") else None
    if vendor and (vendor.status or "").upper() != "ACTIVE":
        return f"{vendor.name} is {vendor.status}. Do not send this job to that vendor."
    end = _parse_date(getattr(contract, "end_date", None))
    if end and end < date.today():
        name = vendor.name if vendor else "The AMC contract"
        return f"{name} ended on {end.isoformat()}. Do not send this job under that contract."
    return None


def _issued_count(session: Session, tenant_id: str, email: str, category: str) -> int:
    want = _TYPE_FOR.get(category, "")
    if not email or not want:
        return 0
    rows = session.exec(
        select(Asset).where(Asset.tenant_id == tenant_id, Asset.assignee_email == email.lower())
    ).all()
    return sum(1 for a in rows if (a.type or "").upper() == want and (a.status or "") in {"ACTIVE", "ISSUED", "PENDING_ISSUE"})


def _stock_note(session: Session, tenant_id: str, location_id: Optional[str], text: str) -> Optional[dict[str, Any]]:
    rows = session.exec(select(StockSku).where(StockSku.tenant_id == tenant_id, StockSku.status == "ACTIVE")).all()
    want = text.lower()
    chosen = None
    for sku in rows:
        if location_id and sku.location_id and sku.location_id != location_id:
            continue
        if (sku.name or "").lower() in want or (sku.sku_code or "").lower() in want:
            chosen = sku
            break
    if chosen is None:
        return None
    expired = _parse_date(chosen.expires_on)
    if expired and expired < date.today():
        return {
            "action": "EXPIRED",
            "reason": f"{chosen.name} at this branch expired on {expired.isoformat()}",
            "headline": f"Do not issue {chosen.name}. It expired on {expired.isoformat()}.",
            "summary": f"{chosen.name} at this branch is past its expiry ({expired.isoformat()}). It will not be issued.",
            "checks": [f"Stock: {chosen.name}", f"On hand: {chosen.qty_on_hand:g}", f"Expired: {expired.isoformat()}"],
        }
    if float(chosen.reorder_min or 0) > 0 and float(chosen.qty_on_hand or 0) <= float(chosen.reorder_min):
        return {
            "action": "REORDER",
            "reason": f"{chosen.name} is at {chosen.qty_on_hand:g}, minimum is {chosen.reorder_min:g}",
            "headline": f"Reorder {chosen.name}. On hand {chosen.qty_on_hand:g}, minimum {chosen.reorder_min:g}.",
            "summary": (
                f"{chosen.name} at this branch is at {chosen.qty_on_hand:g} {chosen.unit} "
                f"(minimum {chosen.reorder_min:g}). A reorder is required."
            ),
            "checks": [f"Stock: {chosen.name}", f"On hand: {chosen.qty_on_hand:g}", f"Minimum: {chosen.reorder_min:g}"],
        }
    return None


def decide_for_case(session: Session, tenant_id: str, outcome: Any) -> dict[str, Any]:
    """One decision for this case, from records at its branch."""
    facts = getattr(outcome, "facts", None) or {}
    category = (facts.get("agent_category") or "general").lower()
    details = dict(facts.get("details") or {})
    text = _request_text(outcome)
    location_id = facts.get("location_id")
    limits = _limits(session, tenant_id)
    checks: list[str] = []

    if category in {"supplies", "pantry"} or "stock" in text.lower():
        stock = _stock_note(session, tenant_id, location_id, text)
        if stock:
            stock["checks"] = checks + stock["checks"]
            return stock

    if category in _REPEAT_CATEGORIES:
        place = _place_token(text)
        limit = _repeat_after(limits, category)
        rows = _completions(session, tenant_id, location_id, category)
        count = _repair_count(rows, None, place, getattr(outcome, "outcome_id", None))
        checks.append(f"Place: {place or 'not named'}")
        checks.append(f"Earlier completions at this place: {count if count is not None else 'unknown'}")
        checks.append(f"Escalate after: {limit}")
        if place and count is not None and count >= limit:
            return {
                "action": "ESCALATE",
                "reason": f"This place has already been completed {count} times (limit {limit})",
                "headline": f"Escalated. {place} has been attended {count} times. Do not treat this as an ordinary repeat.",
                "summary": (
                    f"The same place ({place}) at this branch has already been completed {count} times. "
                    f"The limit is {limit}, so this is escalated instead of another ordinary job."
                ),
                "repair_count": count,
                "limit": limit,
                "checks": checks,
            }

    if category not in _ASSET_CATEGORIES:
        return {"action": "PROCEED", "reason": "", "summary": "", "headline": "", "checks": checks}

    assets = _assets_at(session, tenant_id, location_id)
    asset = _match_asset(assets, category, text, details)
    place = _place_token(text)
    rows = _completions(session, tenant_id, location_id, category)
    count = _repair_count(rows, asset, place, getattr(outcome, "outcome_id", None))
    warranty, warranty_until = _warranty(asset)
    amc = amc_coverage_hint(
        session,
        tenant_id,
        category=category,
        asset_id=asset.asset_id if asset else details.get("asset_id"),
        location_id=location_id,
    )
    limit = _replace_after(limits, category, asset)
    name = asset.name if asset else "This item"
    checks.append(f"Item: {name}" if asset else "Item: no matching asset on record at this branch")
    checks.append(f"Warranty: {warranty}" + (f" until {warranty_until}" if warranty_until and warranty == "active" else ""))
    if warranty == "expired" and warranty_until:
        checks[-1] = f"Warranty: expired on {warranty_until}"
    checks.append(
        "AMC: " + (
            amc["obligations"][0]["vendor_name"] if amc.get("has_coverage") else "none on record"
        )
    )
    checks.append(f"Repairs on record: {count if count is not None else 'unknown'}")
    checks.append(f"Replace after: {limit}")

    vendor_block = _vendor_problem(session, amc) if amc.get("applicable") else None
    if vendor_block:
        checks.append(vendor_block)

    issued = _issued_count(session, tenant_id, getattr(outcome, "requester_email", "") or "", category)
    if category in {"laptop", "phone_sim", "access_card"} and issued >= 1 and category != "access_card":
        checks.append(f"Already issued to this person: {issued}")
        return {
            "action": "NEEDS_APPROVAL",
            "reason": f"This person already holds {issued} {category.replace('_', ' ')} at this company",
            "headline": f"Approval required. {issued} {category.replace('_', ' ')} already issued to the requester.",
            "summary": (
                f"The record shows {issued} {category.replace('_', ' ')} already issued to you. "
                "A further issue needs approval."
            ),
            "asset_id": asset.asset_id if asset else None,
            "asset_tag": asset.tag if asset else None,
            "repair_count": count,
            "limit": limit,
            "checks": checks,
        }

    if asset is None and count is None:
        return {
            "action": "REPAIR_UNKNOWN",
            "reason": "No asset matched this request at this branch",
            "headline": "Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.",
            "summary": "No asset record matched this request at your branch, so warranty and repair history were not applied.",
            "checks": checks,
        }

    base = {
        "asset_id": asset.asset_id if asset else None,
        "asset_tag": asset.tag if asset else None,
        "repair_count": count,
        "limit": limit,
        "warranty": warranty,
        "checks": checks,
    }
    if vendor_block:
        return {
            **base,
            "action": "VENDOR_HOLD",
            "reason": vendor_block,
            "headline": vendor_block,
            "summary": vendor_block,
        }
    if count is not None and count >= limit:
        return {
            **base,
            "action": "REPLACE",
            "reason": f"{name} has been repaired {count} times (limit {limit})",
            "headline": f"Replace {name}. It has been repaired {count} times. The limit is {limit}. Do not repair it again.",
            "summary": (
                f"{name} at this branch has been repaired {count} times. The limit is {limit}, "
                "so this request is a replacement, not another repair."
            ),
        }
    if warranty == "active":
        return {
            **base,
            "action": "WARRANTY_REPAIR",
            "reason": f"{name} is under warranty until {warranty_until}",
            "headline": f"Warranty claim for {name}. Covered until {warranty_until}. Do not buy a replacement.",
            "summary": f"{name} is under warranty until {warranty_until}. The work will be handled as a warranty claim.",
        }
    if amc.get("has_coverage"):
        vendor_name = amc["obligations"][0]["vendor_name"]
        return {
            **base,
            "action": "AMC_REPAIR",
            "reason": f"AMC covers this with {vendor_name}",
            "headline": f"Repair under AMC. Use {vendor_name}. Repairs on record: {count if count is not None else 'unknown'}.",
            "summary": (
                f"{name} is covered by an AMC with {vendor_name}. "
                f"Repairs on record: {count if count is not None else 'unknown'} (replace after {limit})."
            ),
        }
    return {
        **base,
        "action": "REPAIR",
        "reason": f"Repair. Count {count if count is not None else 'unknown'} of {limit}.",
        "headline": f"Repair {name}. Repairs on record: {count if count is not None else 'unknown'} of {limit}.",
        "summary": (
            f"{name} will be repaired. Repairs on record: {count if count is not None else 'unknown'}. "
            f"Replacement is considered after {limit}."
        ),
    }
