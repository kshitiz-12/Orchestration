"""Procure-to-pay orchestration (M19–M21) — PR/PO/SES/match/ERP handoff."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session

from app.connectors.erp import ErpConnector
from app.connectors.erp_http import get_erp_connector
from app.engines.matching import MatchingEngine
from app.models.finance import CostRequirement, ServiceEntry
from app.models.org import Invoice, PurchaseOrder, Receipt, utcnow


class P2PService:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        *,
        entity_id: Optional[str] = None,
        erp: Optional[ErpConnector] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id
        self.erp = erp or get_erp_connector(session, tenant_id)
        self.matching = MatchingEngine(session, tenant_id)

    def create_po(
        self,
        *,
        vendor_id: str,
        po_number: str,
        description: str,
        quantity: float,
        unit_rate: float,
        currency: str = "INR",
        contract_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            tenant_id=self.tenant_id,
            vendor_id=vendor_id,
            po_number=po_number.strip(),
            description=description.strip(),
            quantity=quantity,
            unit_rate=unit_rate,
            currency=currency,
            status="OPEN",
            contract_id=contract_id,
        )
        self.session.add(po)
        if outcome_id:
            cost = CostRequirement(
                tenant_id=self.tenant_id,
                entity_id=self.entity_id,
                outcome_id=outcome_id,
                vendor_id=vendor_id,
                category="OPEX",
                currency=currency,
                estimated_amount=quantity * unit_rate,
                committed_amount=quantity * unit_rate,
                status="COMMITTED",
            )
            self.session.add(cost)
        self.session.commit()
        self.session.refresh(po)
        return po

    def receive_goods(self, *, po_id: str, quantity_received: float, received_date: str, notes: Optional[str] = None) -> Receipt:
        po = self.session.get(PurchaseOrder, po_id)
        if not po or po.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="PO not found")
        receipt = Receipt(
            tenant_id=self.tenant_id,
            po_id=po_id,
            quantity_received=quantity_received,
            received_date=received_date,
            status="CONFIRMED",
            notes=notes,
        )
        self.session.add(receipt)
        self.session.commit()
        self.session.refresh(receipt)
        return receipt

    def create_ses(
        self,
        *,
        po_id: str,
        quantity: float,
        unit_rate: float,
        vendor_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
    ) -> ServiceEntry:
        po = self.session.get(PurchaseOrder, po_id)
        if not po or po.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="PO not found")
        ses = ServiceEntry(
            tenant_id=self.tenant_id,
            entity_id=self.entity_id,
            po_id=po_id,
            contract_id=po.contract_id,
            vendor_id=vendor_id or po.vendor_id,
            outcome_id=outcome_id,
            quantity=quantity,
            unit_rate=unit_rate,
            amount=quantity * unit_rate,
            currency=po.currency,
            status="SUBMITTED",
        )
        match = self.matching.match_ses(ses, po)
        if match.status != "MATCHED":
            ses.status = "DRAFT"
            ses.notes = "; ".join(match.reasons)
        self.session.add(ses)
        self.session.commit()
        self.session.refresh(ses)
        return ses

    def match_and_post_invoice(self, invoice_id: str) -> dict[str, Any]:
        invoice = self.session.get(Invoice, invoice_id)
        if not invoice or invoice.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Invoice not found")
        result = self.matching.match_invoice(invoice)
        invoice.match_status = result.status
        invoice.updated_at = utcnow()
        self.session.add(invoice)
        self.session.commit()
        if result.status != "MATCHED":
            return {"match": result.status, "reasons": result.reasons, "posted": False}
        posted = self.erp.post_invoice(invoice, idempotency_key=f"inv-post-{invoice.invoice_id}")
        return {
            "match": result.status,
            "reasons": result.reasons,
            "posted": posted.ok,
            "erp_status": posted.status,
            "erp_ref": posted.erp_document_ref,
            "error": posted.error,
        }
