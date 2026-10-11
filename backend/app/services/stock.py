"""Supplies stock: issue against SKUs and mail-driven bulk reorder when below min."""

from __future__ import annotations

import re
from typing import Optional

from sqlmodel import Session, select

from app.agent.directory import route_for
from app.agent.playbooks import case_prefix
from app.core.enums import CommunicationType, OutcomeStatus
from app.core.logging import get_logger
from app.engine.outcome_engine import OutcomeEngine
from app.models.org import StockSku, Vendor, utcnow
from app.models.outcome import Outcome
from app.services.communication import CommunicationService

logger = get_logger(__name__)

_QTY = re.compile(r"\b(\d+)\s*(?:x|pcs?|pieces?|units?|boxes?|packs?)?\b", re.I)


def find_sku(
    session: Session,
    tenant_id: str,
    *,
    text: str,
    location_id: Optional[str] = None,
) -> Optional[StockSku]:
    """Best-effort match of a supplies ask to a SKU by code or name."""
    blob = (text or "").lower()
    q = select(StockSku).where(StockSku.tenant_id == tenant_id, StockSku.status == "ACTIVE")
    rows = list(session.exec(q).all())
    if location_id:
        placed = [s for s in rows if s.location_id == location_id]
        rows = placed or [s for s in rows if not s.location_id] or rows
    if not rows:
        return None
    for sku in rows:
        code = (sku.sku_code or "").lower()
        name = (sku.name or "").lower()
        if code and code in blob:
            return sku
        if name and name in blob:
            return sku
        tokens = [t for t in re.split(r"[^a-z0-9]+", name) if len(t) >= 3]
        if tokens and all(t in blob for t in tokens[:2]):
            return sku
    return None


def parse_qty(text: str, default: float = 1.0) -> float:
    m = _QTY.search(text or "")
    if not m:
        return default
    try:
        return max(1.0, float(m.group(1)))
    except ValueError:
        return default


def issue_sku(session: Session, sku: StockSku, qty: float) -> StockSku:
    sku.qty_on_hand = max(0.0, float(sku.qty_on_hand or 0) - float(qty))
    sku.updated_at = utcnow()
    session.add(sku)
    session.flush()
    return sku


def low_stock_for_vendor(
    session: Session,
    tenant_id: str,
    *,
    location_id: Optional[str],
    vendor_id: Optional[str],
) -> list[StockSku]:
    q = select(StockSku).where(StockSku.tenant_id == tenant_id, StockSku.status == "ACTIVE")
    out: list[StockSku] = []
    for sku in session.exec(q).all():
        if location_id and sku.location_id and sku.location_id != location_id:
            continue
        if vendor_id and sku.vendor_id and sku.vendor_id != vendor_id:
            continue
        if float(sku.reorder_min or 0) <= 0:
            continue
        if float(sku.qty_on_hand or 0) <= float(sku.reorder_min):
            out.append(sku)
    return out


def _reorder_lines(skus: list[StockSku]) -> list[dict]:
    lines = []
    for sku in skus:
        need = float(sku.reorder_qty or 0) or max(float(sku.reorder_min or 0) * 2, 1.0)
        lines.append(
            {
                "sku_code": sku.sku_code,
                "name": sku.name,
                "qty_on_hand": sku.qty_on_hand,
                "reorder_min": sku.reorder_min,
                "order_qty": need,
                "unit": sku.unit,
                "sku_id": sku.sku_id,
            }
        )
    return lines


def open_bulk_reorder(
    session: Session,
    tenant_id: str,
    *,
    skus: list[StockSku],
    trigger_outcome: Optional[Outcome],
    comms: CommunicationService,
) -> Optional[Outcome]:
    """Open one supplies reorder case and email the vendor or stores team."""
    if not skus:
        return None
    open_rows = session.exec(
        select(Outcome).where(
            Outcome.tenant_id == tenant_id,
            Outcome.status.notin_(  # type: ignore[attr-defined]
                [OutcomeStatus.CLOSED.value, OutcomeStatus.CANCELLED.value, OutcomeStatus.RESOLVED.value]
            ),
        )
    ).all()
    for row in open_rows:
        facts = row.facts or {}
        if facts.get("agent_category") == "supplies" and facts.get("bulk_reorder"):
            existing_ids = {x.get("sku_id") for x in (facts.get("reorder_lines") or [])}
            if existing_ids & {s.sku_id for s in skus}:
                return row

    location_id = next((s.location_id for s in skus if s.location_id), None)
    vendor_id = next((s.vendor_id for s in skus if s.vendor_id), None)
    lines = _reorder_lines(skus)
    names = ", ".join(f"{l['name']}×{l['order_qty']:g}" for l in lines[:6])
    route = route_for(session, tenant_id, "supplies", location_id)
    vendor = session.get(Vendor, vendor_id) if vendor_id else None
    recipients = list(route.recipients)
    if vendor and vendor.contact_email:
        vmail = vendor.contact_email.lower()
        recipients = [vmail] + [r for r in recipients if r.lower() != vmail]

    engine = OutcomeEngine(session, tenant_id)
    ref = engine.next_case_reference(case_prefix("supplies"))

    outcome = Outcome(
        tenant_id=tenant_id,
        case_reference=ref,
        template_code="SERVICE_REQUEST",
        category="SUPPLIES",
        title=f"Stock reorder: {names}"[:200],
        summary=f"Auto bulk reorder — {names}"[:500],
        requester_email=(trigger_outcome.requester_email if trigger_outcome else None) or "stock@system.local",
        status=OutcomeStatus.ACTIVE.value,
        priority="MEDIUM",
        facts={
            "agent_case": True,
            "agent_category": "supplies",
            "agent_stage": "DISPATCHED",
            "bulk_reorder": True,
            "reorder_lines": lines,
            "location_id": location_id,
            "department_code": route.department_code,
            "department_name": route.department_name,
            "vendor_id": vendor_id,
            "vendor_name": vendor.name if vendor else None,
            "details": {"item": names, "requester_note": "Auto bulk reorder — stock below reorder_min"},
            "missing": [],
        },
        conversation_id=trigger_outcome.conversation_id if trigger_outcome else None,
    )
    session.add(outcome)
    session.flush()

    body_lines = [
        "Stock is below minimum. Please supply / confirm the following in one delivery:",
        "",
    ]
    for line in lines:
        body_lines.append(
            f"- {line['name']} ({line['sku_code']}): order {line['order_qty']:g} {line['unit']} "
            f"(on hand {line['qty_on_hand']:g}, min {line['reorder_min']:g})"
        )
    body_lines += [
        "",
        f"Case: {outcome.case_reference}",
        'Reply DONE when shipped, or CONFIRM RECEIVED with quantities so we can refill stock.',
    ]
    if recipients:
        comms.send(
            communication_type=CommunicationType.ACTION_REQUIRED.value,
            subject=f"[ACTION] Stock reorder {outcome.case_reference}",
            body="\n".join(body_lines),
            recipients=recipients,
            outcome_id=outcome.outcome_id,
            conversation_id=outcome.conversation_id,
            idempotency_key=f"bulk-reorder:{outcome.outcome_id}",
        )
    logger.info("bulk_reorder_opened", case=outcome.case_reference, skus=len(lines))
    return outcome


def refill_from_confirm(session: Session, outcome: Outcome, text: str) -> list[str]:
    """When vendor/team confirms receipt, bump qty_on_hand by order_qty for each line."""
    facts = outcome.facts or {}
    if not facts.get("bulk_reorder"):
        return []
    updated = []
    for line in facts.get("reorder_lines") or []:
        sku = session.get(StockSku, line.get("sku_id"))
        if not sku:
            continue
        add = float(line.get("order_qty") or 0)
        m = re.search(rf"{re.escape(sku.name)}\s*[:=]?\s*(\d+)", text or "", re.I)
        if m:
            add = float(m.group(1))
        sku.qty_on_hand = float(sku.qty_on_hand or 0) + add
        sku.updated_at = utcnow()
        session.add(sku)
        updated.append(f"{sku.name} +{add:g} → {sku.qty_on_hand:g}")
    return updated


def issue_and_maybe_reorder(
    session: Session,
    tenant_id: str,
    *,
    text: str,
    location_id: Optional[str],
    trigger_outcome: Optional[Outcome],
    comms: CommunicationService,
) -> dict:
    sku = find_sku(session, tenant_id, text=text, location_id=location_id)
    if not sku:
        return {"issued": False}
    qty = parse_qty(text)
    issue_sku(session, sku, qty)
    result: dict = {"issued": True, "sku": sku.sku_code, "qty": qty, "qty_on_hand": sku.qty_on_hand}
    if float(sku.qty_on_hand or 0) > float(sku.reorder_min or 0):
        return result
    bundle = low_stock_for_vendor(
        session, tenant_id, location_id=sku.location_id or location_id, vendor_id=sku.vendor_id
    )
    if all(s.sku_id != sku.sku_id for s in bundle):
        bundle.insert(0, sku)
    reorder = open_bulk_reorder(
        session, tenant_id, skus=bundle, trigger_outcome=trigger_outcome, comms=comms
    )
    result["reorder_case"] = reorder.case_reference if reorder else None
    return result
