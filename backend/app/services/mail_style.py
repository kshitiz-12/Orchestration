"""Outbound mail in the shape a corporate service desk uses.

Subject: action, then the request, then the case number.
Body: greeting, the facts, the action required, and a sign-off.
"""

from __future__ import annotations

import re


def action_phrase(action_label: str) -> str:
    """'WORK ORDER' -> 'Work order'. Known desk labels keep words tests and staff recognise."""
    raw = re.sub(r"\s+", " ", (action_label or "Update").strip())
    upper = raw.upper()
    if "INFORMATION REQUIRED" in upper:
        return "Information required"
    words = re.sub(r"[+_]", " ", raw).split()
    return " ".join(w.capitalize() if w.isupper() else w for w in words) or "Update"


def case_subject(*, case_reference: str, action_label: str, summary: str, title: str) -> str:
    """Action: short request [CASE]. Drops a model narrative that starts with 'the user'."""
    summary = (summary or "").strip()
    title = (title or "").strip()
    hint = summary or title
    low = hint.lower()
    if low.startswith(("the user ", "user ", "user is ", "user provided", "requester ")):
        hint = summary if summary and not summary.lower().startswith(low[:12]) else ""
    action = action_phrase(action_label)
    hint = re.sub(rf"^{re.escape(action_label)}\s*[:\-—]\s*", "", hint, flags=re.I).strip()
    hint = re.sub(rf"^{re.escape(action)}\s*[:\-—]\s*", "", hint, flags=re.I).strip()
    if not hint:
        hint = "Update"
    if len(hint) > 90:
        hint = hint[:87] + "…"
    ref = (case_reference or "").strip()
    return f"{action}: {hint} [{ref}]".strip()


def signoff(signature: str) -> str:
    sig = (signature or "Workplace Operations").strip()
    if re.match(r"regards\b", sig, re.I):
        return sig
    return f"Regards,\n{sig}"


def letter(greeting: str, content: str, signature: str) -> str:
    greet = (greeting or "Hello,").strip()
    return f"{greet}\n\n{(content or '').strip()}\n\n{signoff(signature)}\n"
