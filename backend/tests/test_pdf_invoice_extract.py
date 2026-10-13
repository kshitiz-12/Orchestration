"""PDF / attachment invoice field extraction."""

import base64
from io import BytesIO

from sqlmodel import Session, select

from app.connectors.cloudmailin import normalize_cloudmailin_payload
from app.models.org import Tenant
from app.services.attachment_extract import (
    extract_pdf_text,
    persist_and_extract_attachment,
    scrape_invoice_fields,
)
from app.services.intake import IntakeService


def test_scrape_invoice_fields_from_text():
    text = """
    TAX INVOICE
    Invoice No: INV-2026-0042
    PO Number: PO-7788
    Vendor: Acme HVAC Pvt Ltd
    Quantity: 2
    Unit Rate: 1500.00
    Grand Total: INR 3,000.00
    """
    fields = scrape_invoice_fields(text)
    assert fields["invoice_number"] == "INV-2026-0042"
    assert fields["po_number"] == "PO-7788"
    assert fields["amount"] == 3000.0
    assert fields["quantity"] == 2.0
    assert fields["unit_rate"] == 1500.0
    assert "Acme" in fields["vendor_name"]


def test_extract_pdf_text_roundtrip():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    text = extract_pdf_text(buf.getvalue())
    assert isinstance(text, str)  # blank page → empty text is OK


def test_persist_pdf_and_scrape(session: Session, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()

    sample = (
        "Invoice Number: INV-99\n"
        "Amount Payable: Rs. 12500.50\n"
        "PO No: PO-1\n"
        "From: CoolAir Services\n"
    ).encode("utf-8")
    # txt path exercises content persist + scrape without needing PDF text layer
    meta = persist_and_extract_attachment(
        {
            "filename": "bill.txt",
            "mime_type": "text/plain",
            "size": len(sample),
            "content_bytes": sample,
        },
        tenant_id="t1",
        event_key="evt1",
    )
    assert meta["validation"]["allowed"] is True
    assert meta["scraped_fields"]["invoice_number"] == "INV-99"
    assert meta["scraped_fields"]["amount"] == 12500.50
    assert (tmp_path / "attachments" / "t1" / "evt1" / "bill.txt").exists()
    get_settings.cache_clear()


def test_cloudmailin_keeps_attachment_content():
    content = base64.b64encode(b"Invoice No: INV-7\nTotal: INR 500\n").decode()
    payload = {
        "envelope": {
            "from": "vendor@example.com",
            "to": "inbox@demo.cloudmailin.net",
            "recipients": ["inbox@demo.cloudmailin.net"],
        },
        "headers": {"subject": "Invoice INV-7", "message_id": "<pdf-test@x>"},
        "plain": "Please find invoice attached.",
        "attachments": [
            {
                "file_name": "invoice.txt",
                "content_type": "text/plain",
                "size": 40,
                "content": content,
            }
        ],
    }
    event = normalize_cloudmailin_payload(payload)
    assert event.attachments[0].content_base64
    assert event.attachments[0].filename == "invoice.txt"


def test_intake_stores_scraped_fields_not_bytes(session: Session, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()

    tid = session.exec(select(Tenant)).first().tenant_id
    body = "Please process the attached invoice."
    content = base64.b64encode(
        b"Invoice No: INV-55\nGrand Total: INR 9,999.00\nPO Number: PO-55\n"
    ).decode()
    result = IntakeService(session, tid).ingest(
        message_id="<inv-pdf-1@test>",
        thread_id="<inv-pdf-1@test>",
        sender="vendor@supplier.com",
        recipients=["ops@company.com"],
        subject="Invoice INV-55",
        body_text=body,
        source="CLOUDMAILIN",
        attachments=[
            {
                "filename": "inv.txt",
                "mime_type": "text/plain",
                "size": 80,
                "content_base64": content,
            }
        ],
    )
    assert result["status"] in {"queued", "deduplicated"}
    from app.models.intake import RawEmailEvent

    event = session.get(RawEmailEvent, result["event_id"])
    assert event is not None
    att = (event.attachments or [])[0]
    assert "content_base64" not in att
    assert "content_bytes" not in att
    assert att.get("scraped_fields", {}).get("invoice_number") == "INV-55"
    assert att.get("scraped_fields", {}).get("amount") == 9999.0
    get_settings.cache_clear()
