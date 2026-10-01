"""Priority (impact x urgency) and the SLA that follows from it, for every kind of request.

The model suggests a priority; these rules can raise it for safety or business-stopping signals and
lower it only when the requester says there is no rush. SLA hours = the tighter of the department's
SLA and the priority cap, so an urgent leak is never left on a 24-hour clock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PRIORITIES = ("LOW", "MEDIUM", "HIGH", "URGENT")
_RANK = {p: i for i, p in enumerate(PRIORITIES)}

# Resolution target caps (hours) and first-response targets (hours) per priority.
RESOLUTION_CAP = {"URGENT": 4, "HIGH": 8, "MEDIUM": 48, "LOW": 120}
RESPONSE_TARGET = {"URGENT": 0.25, "HIGH": 1, "MEDIUM": 4, "LOW": 8}

_URGENT = re.compile(
    r"\b(?:fire|smoke|burning\s+smell|gas\s+leak|short[\s-]?circuit|spark(?:ing|s)|electric(?:al)?\s+shock|"
    r"flood(?:ed|ing)?|water\s+(?:is\s+)?(?:everywhere|gushing|flooding)|pipe\s+burst|burst\s+pipe|"
    r"(?:lift|elevator)\s+(?:is\s+)?(?:stuck|stopped)|trapped|stuck\s+in\s+(?:the\s+)?(?:lift|elevator)|"
    r"injur(?:y|ed)|accident|medical\s+emergency|ambulance|faint(?:ed)?|unconscious|"
    r"theft|stolen|break[\s-]?in|intruder|security\s+breach|"
    r"(?:no|total|complete)\s+power|power\s+(?:outage|cut|failure)|blackout|"
    r"(?:whole|entire)\s+(?:office|floor|building)\s+(?:is\s+)?(?:down|without|has\s+no))\b",
    re.I,
)
_HIGH = re.compile(
    r"\b(?:urgent(?:ly)?|asap|immediately|right\s+away|emergency|critical|"
    r"leak(?:ing|age)?|no\s+water|toilet\s+(?:is\s+)?(?:blocked|clogged|overflowing)|"
    r"internet\s+(?:is\s+)?down|wi-?fi\s+(?:is\s+)?down|network\s+(?:is\s+)?down|"
    r"(?:can'?t|cannot|unable\s+to)\s+(?:work|log\s*in|login)|"
    r"(?:whole|entire)\s+(?:team|floor|department)|everyone|"
    r"ceo|md|chairman|board\s+meeting|client\s+(?:visit|is\s+coming)|vip|"
    r"today|within\s+(?:an?\s+)?hour|by\s+(?:noon|eod|end\s+of\s+day))\b",
    re.I,
)
_LOW = re.compile(
    r"\b(?:no\s+rush|not\s+urgent|whenever\s+(?:possible|convenient|you\s+can)|at\s+your\s+convenience|"
    r"low\s+priority|next\s+week|when\s+you\s+get\s+(?:a\s+)?(?:chance|time))\b",
    re.I,
)


@dataclass(frozen=True)
class PriorityVerdict:
    priority: str
    reason: str = ""

    @property
    def urgent(self) -> bool:
        return self.priority == "URGENT"


def normalize_priority(value: object) -> str:
    raw = str(value or "").strip().upper()
    aliases = {"P1": "URGENT", "CRITICAL": "URGENT", "P2": "HIGH", "P3": "MEDIUM", "NORMAL": "MEDIUM", "P4": "LOW"}
    raw = aliases.get(raw, raw)
    return raw if raw in _RANK else "MEDIUM"


def infer_priority(text: str, suggested: object = None) -> PriorityVerdict:
    base = normalize_priority(suggested)
    body = text or ""
    m = _URGENT.search(body)
    if m:
        return PriorityVerdict("URGENT", f"safety / business-stopping signal: \"{m.group(0).lower()}\"")
    m = _HIGH.search(body)
    if m and _RANK[base] < _RANK["HIGH"]:
        return PriorityVerdict("HIGH", f"time-critical signal: \"{m.group(0).lower()}\"")
    if _LOW.search(body) and base == "MEDIUM":
        return PriorityVerdict("LOW", "requester said there is no rush")
    return PriorityVerdict(base)


def sla_hours_for(priority: str, department_sla: float | int | None) -> float:
    cap = RESOLUTION_CAP.get(normalize_priority(priority), 48)
    dept = float(department_sla or 24)
    if priority == "LOW":
        return max(dept, cap)
    return min(dept, cap)
