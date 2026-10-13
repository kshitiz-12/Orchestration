"""HTTP ERP adapter — production path when ERP_BASE_URL + credentials are set."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from sqlmodel import Session

from app.connectors.erp import CertifiedStubERP, ErpConnector, ErpResult
from app.core.config import get_settings
from app.models.finance import ErpHandoff
from app.models.org import Invoice, utcnow
from app.services.outbox import OutboxService


class HttpErpConnector(ErpConnector):
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.settings = get_settings()
        self.base = (getattr(self.settings, "erp_base_url", None) or "").rstrip("/")
        self.token = getattr(self.settings, "erp_api_token", None) or ""

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def post_invoice(self, invoice: Invoice, *, idempotency_key: str) -> ErpResult:
        if not self.base:
            return CertifiedStubERP(self.session, self.tenant_id).post_invoice(
                invoice, idempotency_key=idempotency_key
            )
        if invoice.match_status != "MATCHED":
            return ErpResult(ok=False, status="REJECTED", error="Invoice must be MATCHED before ERP post")
        payload = {
            "invoice_number": invoice.invoice_number,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "vendor_id": invoice.vendor_id,
            "po_id": invoice.po_id,
            "idempotency_key": idempotency_key,
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    urljoin(self.base + "/", "invoices"),
                    headers={**self._headers(), "Idempotency-Key": idempotency_key},
                    json=payload,
                )
            if resp.status_code >= 400:
                handoff = ErpHandoff(
                    tenant_id=self.tenant_id,
                    invoice_id=invoice.invoice_id,
                    direction="OUTBOUND",
                    erp_system="HTTP_ERP",
                    status="FAILED",
                    payload=payload,
                    last_error=resp.text[:2000],
                    idempotency_key=idempotency_key,
                    sent_at=utcnow(),
                )
                self.session.add(handoff)
                invoice.erp_handoff_status = "FAILED"
                self.session.add(invoice)
                self.session.commit()
                return ErpResult(ok=False, status="FAILED", error=resp.text[:500], raw={"status_code": resp.status_code})
            data = resp.json() if resp.content else {}
            ref = str(data.get("document_ref") or data.get("id") or f"ERP-{invoice.invoice_number}")
            handoff = ErpHandoff(
                tenant_id=self.tenant_id,
                invoice_id=invoice.invoice_id,
                direction="OUTBOUND",
                erp_system="HTTP_ERP",
                erp_document_ref=ref,
                status="ACCEPTED",
                payload={"request": payload, "response": data},
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
                idempotency_key=f"erp-http-{idempotency_key}",
                aggregate_type="Invoice",
                aggregate_id=invoice.invoice_id,
            )
            return ErpResult(ok=True, status="ACCEPTED", erp_document_ref=ref, raw=data)
        except Exception as exc:  # noqa: BLE001
            return ErpResult(ok=False, status="FAILED", error=str(exc)[:500])

    def payment_status(self, erp_document_ref: str) -> ErpResult:
        if not self.base:
            return CertifiedStubERP(self.session, self.tenant_id).payment_status(erp_document_ref)
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    urljoin(self.base + "/", f"payments/{erp_document_ref}"),
                    headers=self._headers(),
                )
            if resp.status_code >= 400:
                return ErpResult(ok=False, status="FAILED", error=resp.text[:500])
            data = resp.json() if resp.content else {}
            status = str(data.get("status") or "ACCEPTED").upper()
            return ErpResult(ok=True, status=status, erp_document_ref=erp_document_ref, raw=data)
        except Exception as exc:  # noqa: BLE001
            return ErpResult(ok=False, status="FAILED", error=str(exc)[:500])


def get_erp_connector(session: Session, tenant_id: str) -> ErpConnector:
    settings = get_settings()
    if (getattr(settings, "erp_base_url", None) or "").strip():
        return HttpErpConnector(session, tenant_id)
    return CertifiedStubERP(session, tenant_id)
