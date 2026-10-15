"""Commercial cost authority — CostRequirement is financial truth; OpsLedger is operational only (V3 §16.4/§29/§31).

Team reply 'done, INR 12500' may only set reported_amount. It never invents posted/paid.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.finance import CostRequirement, ErpHandoff
from app.models.org import utcnow


_STATUS_ORDER = {
    "DRAFT": 0,
    "ESTIMATED": 1,
    "RESERVED": 2,
    "APPROVED": 3,
    "COMMITTED": 4,
    "REPORTED": 5,
    "INVOICED": 6,
    "POSTED": 7,
    "PARTIAL": 7,
    "PAID": 8,
    "CLOSED": 9,
    "CANCELLED": -1,
}


class CommercialCostService:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def get_or_create_for_outcome(
        self,
        outcome_id: str,
        *,
        category: str = "OPEX",
        currency: str = "INR",
        vendor_id: Optional[str] = None,
    ) -> CostRequirement:
        row = self.session.exec(
            select(CostRequirement).where(
                CostRequirement.tenant_id == self.tenant_id,
                CostRequirement.outcome_id == outcome_id,
            )
        ).first()
        if row:
            return row
        row = CostRequirement(
            tenant_id=self.tenant_id,
            entity_id=self.entity_id,
            outcome_id=outcome_id,
            vendor_id=vendor_id,
            category=category.strip().upper(),
            currency=(currency or "INR").upper(),
            status="DRAFT",
            attributes={"authority": "commercial", "ops_ledger_is_not_finance": True},
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def estimate(self, outcome_id: str, amount: float, **kwargs: Any) -> CostRequirement:
        row = self.get_or_create_for_outcome(outcome_id, **{k: kwargs[k] for k in ("category", "currency", "vendor_id") if k in kwargs})
        row.estimated_amount = float(amount)
        row.status = "ESTIMATED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def reserve(self, outcome_id: str, amount: float, *, budget_id: Optional[str] = None) -> CostRequirement:
        row = self.get_or_create_for_outcome(outcome_id)
        row.reserved_amount = float(amount)
        if budget_id:
            row.budget_id = budget_id
        row.status = "RESERVED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def approve(self, outcome_id: str, amount: float) -> CostRequirement:
        row = self.get_or_create_for_outcome(outcome_id)
        row.approved_amount = float(amount)
        row.status = "APPROVED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def commit(self, outcome_id: str, amount: float) -> CostRequirement:
        row = self.get_or_create_for_outcome(outcome_id)
        row.committed_amount = float(amount)
        row.status = "COMMITTED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def report_operational(
        self,
        outcome_id: str,
        amount: float,
        *,
        actor: Optional[str] = None,
        note: Optional[str] = None,
    ) -> CostRequirement:
        """Team 'done, INR X' — reported only. Never posts or pays."""
        row = self.get_or_create_for_outcome(outcome_id)
        row.reported_amount = float(amount)
        attrs = dict(row.attributes or {})
        attrs["reported_by"] = actor
        attrs["reported_note"] = (note or "")[:500]
        attrs["reported_at"] = utcnow().isoformat()
        attrs["authoritative"] = False  # V3: not finance truth
        row.attributes = attrs
        if _STATUS_ORDER.get(row.status, 0) < _STATUS_ORDER["REPORTED"]:
            row.status = "REPORTED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def invoice(self, outcome_id: str, amount: float) -> CostRequirement:
        row = self.get_or_create_for_outcome(outcome_id)
        row.invoiced_amount = float(amount)
        row.status = "INVOICED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def post_from_erp(self, cost_id: str, amount: float, *, erp_ref: Optional[str] = None) -> CostRequirement:
        row = self.session.get(CostRequirement, cost_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Cost requirement not found")
        row.posted_amount = float(amount)
        row.status = "POSTED"
        row.updated_at = utcnow()
        attrs = dict(row.attributes or {})
        if erp_ref:
            attrs["erp_document_ref"] = erp_ref
        row.attributes = attrs
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def mark_paid_from_erp(self, cost_id: str, amount: float, *, erp_ref: Optional[str] = None) -> CostRequirement:
        """Only ERP acknowledgement may set paid — never team chat."""
        row = self.session.get(CostRequirement, cost_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Cost requirement not found")
        row.paid_amount = float(amount)
        row.status = "PAID"
        row.updated_at = utcnow()
        attrs = dict(row.attributes or {})
        attrs["paid_source"] = "ERP"
        if erp_ref:
            attrs["erp_payment_ref"] = erp_ref
        row.attributes = attrs
        self.session.add(row)
        handoff = ErpHandoff(
            tenant_id=self.tenant_id,
            entity_id=row.entity_id,
            cost_id=row.cost_id,
            direction="INBOUND",
            status="PAID",
            erp_document_ref=erp_ref,
            payload={"amount": amount},
            idempotency_key=f"paid-{row.cost_id}-{erp_ref or amount}",
            acknowledged_at=utcnow(),
        )
        self.session.add(handoff)
        self.session.commit()
        self.session.refresh(row)
        return row

    def snapshot(self, outcome_id: str) -> dict[str, Any]:
        row = self.session.exec(
            select(CostRequirement).where(
                CostRequirement.tenant_id == self.tenant_id,
                CostRequirement.outcome_id == outcome_id,
            )
        ).first()
        if not row:
            return {"outcome_id": outcome_id, "status": "NONE", "authoritative_finance": False}
        return {
            "cost_id": row.cost_id,
            "outcome_id": outcome_id,
            "status": row.status,
            "estimated_amount": row.estimated_amount,
            "reserved_amount": row.reserved_amount,
            "approved_amount": row.approved_amount,
            "committed_amount": row.committed_amount,
            "reported_amount": row.reported_amount,
            "invoiced_amount": row.invoiced_amount,
            "posted_amount": row.posted_amount,
            "paid_amount": row.paid_amount,
            "authoritative_finance": row.status in {"POSTED", "PAID", "INVOICED"},
            "ops_reported_only": row.status == "REPORTED",
            "note": "OpsLedger amounts are operational memory; CostRequirement is commercial ladder",
        }
