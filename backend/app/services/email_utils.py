import hashlib
import re
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

QUOTE_PATTERNS = [
    # Yahoo/Gmail often leave "wrote:" mid-line with the quoted body after it
    re.compile(r"^\s*On\s+.+\bwrote:", re.M | re.I),
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
    re.compile(r"^Yahoo Mail:.*$", re.M | re.I),
    re.compile(r"^Disclaimer\s*:", re.M | re.I),
    re.compile(r"^This e-?mail.*confidential", re.M | re.I),
]


def _first_cut(text: str, patterns: list[re.Pattern]) -> int | None:
    cuts = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            cuts.append(match.start())
    disc = re.search(r"\n\s*Disclaimer\s*:", text, re.I)
    if disc:
        cuts.append(disc.start())
    return min(cuts) if cuts else None


def split_new_and_quoted(body: str) -> tuple[str, str]:
    """Split requester's new text from quoted history (Yahoo/Gmail/Outlook)."""
    text = body or ""
    cut = _first_cut(text, QUOTE_PATTERNS)
    if cut is None:
        return text.strip(), ""
    return text[:cut].strip(), text[cut:].strip()


def salvage_inline_answers(quoted: str) -> list[str]:
    """Keep text the requester typed after our questions in the quoted thread."""
    answers: list[str] = []
    for raw_line in (quoted or "").splitlines():
        line = raw_line.strip().lstrip(">").strip()
        if "?" not in line:
            continue
        rest = line.rsplit("?", 1)[-1].strip(" \t-–—")
        if len(rest) < 2:
            continue
        # Example times in the question live before '?'; leftover boilerplate is short.
        if re.fullmatch(r"(e\.g\.|eg)[.\s].*", rest, re.I):
            continue
        answers.append(rest)
    return answers


def strip_signatures(text: str) -> str:
    cut = _first_cut(text or "", SIGNATURE_PATTERNS)
    if cut is None:
        return (text or "").strip()
    return (text or "")[:cut].strip()


def strip_for_ai(body: str) -> str:
    """New requester text + answers written onto quoted questions. Drop our outbound copy."""
    return prepare_interpreter_view(body)["combined_for_parsers"]


QUOTED_EXCERPT_MAX = 2800


def prepare_interpreter_view(body: str) -> dict:
    """Split a mailbox reply the way a chat model should read it.

    People type however they want: new text at the top, answers after our '?',
    edits inside the quoted thread. Heuristics get the cleaned `combined_for_parsers`
    slice; Gemini also sees a labeled quoted excerpt so it can recover answers
    salvage missed (answers not on the same line as the question).
    """
    new_text, quoted = split_new_and_quoted(body or "")
    new_text = strip_signatures(new_text)
    salvaged = salvage_inline_answers(quoted)
    excerpt = (quoted or "").strip()
    if len(excerpt) > QUOTED_EXCERPT_MAX:
        excerpt = excerpt[-QUOTED_EXCERPT_MAX:]
    parts: list[str] = []
    if new_text:
        parts.append(new_text)
    if salvaged:
        parts.append("Answers written on the questions:")
        parts.extend(salvaged)
    return {
        "this_message": new_text,
        "answers_typed_on_quoted_questions": salvaged,
        "quoted_thread_excerpt": excerpt,
        "combined_for_parsers": "\n".join(parts).strip(),
    }


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
