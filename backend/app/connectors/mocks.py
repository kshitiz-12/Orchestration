"""Mock / sandbox connectors — clearly separated from the workflow engine."""

from typing import Any


class MockERPConnector:
    """Prototype ERP handoff — never posts real ledger entries."""

    def handoff_invoice(self, invoice: dict[str, Any]) -> dict[str, Any]:
        if invoice.get("match_status") != "MATCHED":
            return {"status": "REJECTED", "reason": "Invoice not matched"}
        if invoice.get("approved") is not True:
            return {"status": "REJECTED", "reason": "Human approval required — no autonomous payment"}
        return {
            "status": "ACCEPTED_MOCK",
            "erp_doc_id": f"MOCK-ERP-{invoice.get('invoice_number')}",
            "payment_released": False,
        }


class MockAccessControlConnector:
    """Never changes live access permissions in the prototype."""

    def request_access(self, person_id: str, areas: list[str]) -> dict[str, Any]:
        return {
            "status": "PENDING_HUMAN_APPROVAL",
            "person_id": person_id,
            "areas": areas,
            "executed": False,
        }


class MockVendorPortal:
    def send_request(self, vendor_email: str, subject: str, body: str) -> dict[str, Any]:
        return {
            "status": "QUEUED_MOCK",
            "vendor_email": vendor_email,
            "subject": subject,
            "confidential_redacted": True,
        }
