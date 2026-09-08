import hashlib
import re
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

QUOTE_PATTERNS = [
    re.compile(r"^On .+ wrote:$", re.M),
    re.compile(r"^From:\s.+$", re.M),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}$", re.M | re.I),
    re.compile(r"^>+.*$", re.M),
]

SIGNATURE_PATTERNS = [
    re.compile(r"^--\s*$", re.M),
    re.compile(r"^Sent from my .+$", re.M | re.I),
    re.compile(r"^Best regards,?$", re.M | re.I),
    re.compile(r"^Thanks,?$", re.M | re.I),
    re.compile(r"^Regards,?$", re.M | re.I),
]


def strip_for_ai(body: str) -> str:
    """Strip quoted history and signatures for AI input only — originals remain stored."""
    text = body or ""
    cut_points = []
    for pattern in QUOTE_PATTERNS + SIGNATURE_PATTERNS:
        match = pattern.search(text)
        if match:
            cut_points.append(match.start())
    if cut_points:
        text = text[: min(cut_points)].strip()
    return text.strip()


def compute_idempotency_key(message_id: str, source: str = "GMAIL") -> str:
    raw = f"{source}:{message_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_attachment(filename: str, size: int, content: Optional[bytes] = None) -> dict:
    settings = get_settings()
    ext = Path(filename).suffix.lower().lstrip(".")
    flags: dict = {"filename": filename, "size": size, "allowed": True, "reasons": []}
    if size > settings.attachment_max_bytes:
        flags["allowed"] = False
        flags["reasons"].append("size_exceeded")
    if ext not in settings.attachment_extensions:
        flags["allowed"] = False
        flags["reasons"].append("type_not_allowlisted")
    # Basic content sniff: reject empty / executable-like headers
    if content is not None:
        if content[:2] == b"MZ":
            flags["allowed"] = False
            flags["reasons"].append("executable_signature")
        if b"<script" in content[:4096].lower():
            flags["allowed"] = False
            flags["reasons"].append("script_content")
    return flags


PROMPT_INJECTION_MARKERS = [
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "you are now",
    "override policy",
    "disregard safety",
]


def safety_scan_email(subject: str, body: str) -> dict:
    text = f"{subject}\n{body}".lower()
    flags = {
        "prompt_injection_suspected": any(m in text for m in PROMPT_INJECTION_MARKERS),
        "bank_change_mentioned": "bank" in text and any(w in text for w in ["change", "update", "new account", "iban"]),
        "payment_release_requested": any(w in text for w in ["release payment", "wire funds", "pay immediately"]),
    }
    flags["quarantine"] = flags["prompt_injection_suspected"]
    return flags
