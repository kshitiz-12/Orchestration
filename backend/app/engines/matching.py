"""PO / GRN-SES / Invoice matching engine (deterministic tolerances)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlmodel import Session

from app.models.finance import ServiceEntry
from app.models.org import Invoice, PurchaseOrder, Receipt


@dataclass
class MatchResult:
    status: str  # MATCHED | QUANTITY_MISMATCH | RATE_MISMATCH | AMOUNT_MISMATCH | MISSING_PO | PENDING_REVIEW
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


class MatchingEngine:
    def __init__(self, session: Session, tenant_id: str, *, qty_tol: float = 0.01, rate_tol: float = 0.01, amt_tol: float = 1.0):
        self.session = session
        self.tenant_id = tenant_id
        self.qty_tol = qty_tol
        self.rate_tol = rate_tol
        self.amt_tol = amt_tol

    def match_invoice(self, invoice: Invoice) -> MatchResult:
        if invoice.tenant_id != self.tenant_id:
            return MatchResult(status="PENDING_REVIEW", reasons=["tenant_mismatch"])
        if not invoice.po_id:
            return MatchResult(status="MISSING_PO", reasons=["invoice has no PO"])

        po = self.session.get(PurchaseOrder, invoice.po_id)
        if not po or po.tenant_id != self.tenant_id:
            return MatchResult(status="MISSING_PO", reasons=["PO not found"])

        reasons: list[str] = []
        receipt_qty = 0.0
        if invoice.receipt_id:
            receipt = self.session.get(Receipt, invoice.receipt_id)
            if receipt:
                receipt_qty = float(receipt.quantity_received or 0)
            else:
                reasons.append("receipt_missing")

        inv_qty = float(invoice.quantity or 0)
        inv_rate = float(invoice.unit_rate or 0)
        inv_amt = float(invoice.amount or 0)
        po_qty = float(po.quantity or 0)
        po_rate = float(po.unit_rate or 0)
        po_amt = po_qty * po_rate

        if inv_qty and abs(inv_qty - po_qty) > self.qty_tol and (not receipt_qty or abs(inv_qty - receipt_qty) > self.qty_tol):
            reasons.append(f"quantity_mismatch inv={inv_qty} po={po_qty} receipt={receipt_qty}")
        if inv_rate and abs(inv_rate - po_rate) > self.rate_tol:
            reasons.append(f"rate_mismatch inv={inv_rate} po={po_rate}")
        expected_amt = inv_qty * inv_rate if inv_qty and inv_rate else po_amt
        if inv_amt and abs(inv_amt - expected_amt) > self.amt_tol and abs(inv_amt - po_amt) > self.amt_tol:
            reasons.append(f"amount_mismatch inv={inv_amt} expected={expected_amt} po={po_amt}")

        if any("quantity" in r for r in reasons):
            status = "QUANTITY_MISMATCH"
        elif any("rate" in r for r in reasons):
            status = "RATE_MISMATCH"
        elif any("amount" in r for r in reasons):
            status = "AMOUNT_MISMATCH"
        elif reasons:
            status = "PENDING_REVIEW"
        else:
            status = "MATCHED"

        return MatchResult(
            status=status,
            reasons=reasons,
            details={
                "po_id": po.po_id,
                "po_number": po.po_number,
                "invoice_id": invoice.invoice_id,
                "invoice_number": invoice.invoice_number,
            },
        )

    def match_ses(self, ses: ServiceEntry, po: Optional[PurchaseOrder] = None) -> MatchResult:
        if not ses.po_id and not po:
            return MatchResult(status="MISSING_PO", reasons=["SES has no PO"])
        po = po or self.session.get(PurchaseOrder, ses.po_id)
        if not po:
            return MatchResult(status="MISSING_PO", reasons=["PO not found"])
        reasons: list[str] = []
        if abs(float(ses.unit_rate or 0) - float(po.unit_rate or 0)) > self.rate_tol:
            reasons.append("rate_mismatch")
        if float(ses.quantity or 0) - float(po.quantity or 0) > self.qty_tol:
            reasons.append("quantity_exceeds_po")
        status = "MATCHED" if not reasons else "PENDING_REVIEW"
        return MatchResult(status=status, reasons=reasons, details={"ses_id": ses.ses_id, "po_id": po.po_id})
