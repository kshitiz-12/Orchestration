"""ERP connector contract — production adapters implement this; CI uses CertifiedStubERP."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlmodel import Session

from app.models.finance import ErpHandoff
from app.models.org import Invoice, utcnow
from app.services.outbox import OutboxService


@dataclass
class ErpResult:
    ok: bool
    status: str
    erp_document_ref: Optional[str] = None
    error: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)


class ErpConnector(ABC):
    @abstractmethod
    def post_invoice(self, invoice: Invoice, *, idempotency_key: str) -> ErpResult:
        ...

    @abstractmethod
    def payment_status(self, erp_document_ref: str) -> ErpResult:
        ...


class CertifiedStubERP(ErpConnector):
    """Deterministic stub for acceptance tests — not Mock-for-demo; certified behaviour matrix."""

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def post_invoice(self, invoice: Invoice, *, idempotency_key: str) -> ErpResult:
        if invoice.match_status != "MATCHED":
            return ErpResult(ok=False, status="REJECTED", error="Invoice must be MATCHED before ERP post")
        ref = f"ERP-{invoice.invoice_number}"
        handoff = ErpHandoff(
            tenant_id=self.tenant_id,
            invoice_id=invoice.invoice_id,
            direction="OUTBOUND",
            erp_system="CERTIFIED_STUB",
            erp_document_ref=ref,
            status="ACCEPTED",
            payload={"amount": invoice.amount, "currency": invoice.currency},
            idempotency_key=idempotency_key,
            sent_at=utcnow(),
            acknowledged_at=utcnow(),
        )
        self.session.add(handoff)
        invoice.erp_handoff_status = "ACCEPTED"
        self.session.add(invoice)
        self.session.commit()
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="ERP.INVOICE_POSTED",
            payload={"invoice_id": invoice.invoice_id, "erp_ref": ref},
            idempotency_key=f"erp-post-{idempotency_key}",
            aggregate_type="Invoice",
            aggregate_id=invoice.invoice_id,
        )
        return ErpResult(ok=True, status="ACCEPTED", erp_document_ref=ref)

    def payment_status(self, erp_document_ref: str) -> ErpResult:
        # Stub never invents PAID without explicit test harness mark
        return ErpResult(ok=True, status="ACCEPTED", erp_document_ref=erp_document_ref, raw={"paid": False})


class HrmsConnector(ABC):
    @abstractmethod
    def sync_employees(self) -> dict[str, Any]:
        ...


class CertifiedStubHRMS(HrmsConnector):
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def sync_employees(self) -> dict[str, Any]:
        """Contract: delta sync returns counts; no invented people."""
        return {
            "ok": True,
            "created": 0,
            "updated": 0,
            "deactivated": 0,
            "source": "CERTIFIED_STUB_HRMS",
            "note": "Wire live HRMS credentials in Phase 9; stub proves connector boundary",
        }
