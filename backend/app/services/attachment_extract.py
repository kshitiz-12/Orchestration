"""Persist email attachments and extract invoice fields from PDF text.

Digital PDFs: text layer via pypdf.
Scanned/image PDFs: returns empty text — caller may still send the file to Gemini multimodal later.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MONEY = r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)"
_INV_NO = re.compile(
    # Require no/number/# so bare "INVOICE" headers are not captured as the number
    r"\b(?:invoice|inv\.?)\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/]{2,})",
    re.I,
)
_PO_NO = re.compile(
    r"\b(?:p\.?\s*o\.?\s*(?:no\.?|number|#)?|purchase\s*order)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-\/]{2,})",
    re.I,
)
_AMOUNT = re.compile(
    r"(?:(?:grand\s*)?total|amount\s*payable|invoice\s*amount|net\s*payable|total\s*due)"
    rf"\s*[:\-]?\s*(?:INR|Rs\.?|₹|USD|\$)?\s*{_MONEY}",
    re.I,
)
_AMOUNT_FALLBACK = re.compile(rf"(?:INR|Rs\.?|₹)\s*{_MONEY}", re.I)
_QTY = re.compile(r"(?:quantity|qty)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)", re.I)
_RATE = re.compile(r"(?:unit\s*rate|rate|price)\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9]+(?:\.[0-9]+)?)", re.I)
_VENDOR = re.compile(r"(?:from|vendor|supplier|bill\s*from)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 &.\-]{2,60})", re.I)


def _parse_money(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", "").strip())
    except ValueError:
        return None


def scrape_invoice_fields(text: str) -> dict[str, Any]:
    """Deterministic field scrape from invoice/PDF text — never invents amounts."""
    blob = text or ""
    out: dict[str, Any] = {}
    m = _INV_NO.search(blob)
    if m:
        out["invoice_number"] = m.group(1).strip()
    m = _PO_NO.search(blob)
    if m:
        out["po_number"] = m.group(1).strip()
    m = _AMOUNT.search(blob) or _AMOUNT_FALLBACK.search(blob)
    if m:
        amt = _parse_money(m.group(1))
        if amt is not None:
            out["amount"] = amt
    m = _QTY.search(blob)
    if m:
        try:
            out["quantity"] = float(m.group(1))
        except ValueError:
            pass
    m = _RATE.search(blob)
    if m:
        rate = _parse_money(m.group(1))
        if rate is not None:
            out["unit_rate"] = rate
    m = _VENDOR.search(blob)
    if m:
        name = m.group(1).strip()
        if name.lower() not in {"invoice", "tax", "gst", "total"}:
            out["vendor_name"] = name
    return out


def extract_pdf_text(content: bytes, *, max_chars: int = 40_000) -> str:
    if not content:
        return ""
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                continue
        text = "\n".join(parts).strip()
        if len(text) > max_chars:
            return text[:max_chars]
        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_text_extract_failed", error=str(exc)[:200])
        return ""


def decode_attachment_bytes(att: dict[str, Any]) -> Optional[bytes]:
    raw = att.get("content_bytes")
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    b64 = att.get("content_base64") or att.get("content")
    if isinstance(b64, str) and b64.strip():
        try:
            # CloudMailin sometimes prefixes data URLs
            if "," in b64 and b64.strip().lower().startswith("data:"):
                b64 = b64.split(",", 1)[1]
            return base64.b64decode(b64)
        except Exception:  # noqa: BLE001
            logger.warning("attachment_b64_decode_failed", filename=att.get("filename"))
            return None
    return None


def persist_and_extract_attachment(
    att: dict[str, Any],
    *,
    tenant_id: str,
    event_key: str,
) -> dict[str, Any]:
    """Validate/persist attachment; return DB-safe metadata (no raw bytes)."""
    from app.services.email_utils import validate_attachment

    filename = str(att.get("filename") or att.get("file_name") or "attachment")
    content = decode_attachment_bytes(att)
    size = int(att.get("size") or (len(content) if content else 0))
    flags = validate_attachment(filename, size, content)
    meta: dict[str, Any] = {
        "filename": filename,
        "mime_type": att.get("mime_type") or att.get("content_type"),
        "size": size,
        "attachment_id": att.get("attachment_id"),
        "validation": flags,
    }
    if not flags.get("allowed", True) or not content:
        return meta

    settings = get_settings()
    root = Path(settings.storage_path) / "attachments" / tenant_id / event_key
    root.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._\-]+", "_", filename)[:120] or "file"
    path = root / safe_name
    try:
        path.write_bytes(content)
        meta["storage_path"] = str(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("attachment_persist_failed", error=str(exc)[:200], filename=filename)

    ext = Path(filename).suffix.lower().lstrip(".")
    mime = (meta.get("mime_type") or "").lower()
    if ext == "pdf" or "pdf" in mime:
        text = extract_pdf_text(content)
        meta["extracted_text"] = text
        meta["extracted_chars"] = len(text)
        meta["text_layer"] = bool(text.strip())
        fields = scrape_invoice_fields(text) if text else {}
        if fields:
            meta["scraped_fields"] = fields
        if not text.strip():
            meta["extract_note"] = "No text layer — likely scanned; Gemini multimodal or manual entry needed"
    elif ext in {"txt", "csv"}:
        try:
            text = content.decode("utf-8", errors="ignore")[:40_000]
            meta["extracted_text"] = text
            meta["scraped_fields"] = scrape_invoice_fields(text)
        except Exception:  # noqa: BLE001
            pass
    return meta


def attachment_texts_for_ai(attachments: Optional[list[dict[str, Any]]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for a in attachments or []:
        if not a.get("validation", {}).get("allowed", True):
            continue
        text = (a.get("extracted_text") or "").strip()
        if not text:
            continue
        out.append({"filename": str(a.get("filename") or "attachment"), "text": text[:20_000]})
    return out


def scraped_fields_from_attachments(attachments: Optional[list[dict[str, Any]]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for a in attachments or []:
        fields = a.get("scraped_fields") or {}
        if isinstance(fields, dict):
            for k, v in fields.items():
                if k not in merged and v not in (None, ""):
                    merged[k] = v
    return merged
