"""Playbooks: what each kind of request needs, who does it and how risky it is - as data.

Categories are open-ended. Anything without a playbook is a general admin request routed to the
Admin department, never forced into another flow. Adding a request type means adding a Playbook
entry here, not a new pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class Playbook:
    category: str
    label: str
    prefix: str = "TKT"
    # (accepted detail keys, question to ask when none of them is present)
    required: tuple[tuple[tuple[str, ...], str], ...] = ()
    # Admin decides before the desk acts
    sensitive: bool = False
    # Spend above this needs approval (0 = any amount needs approval); department limit overrides it
    auto_spend_limit: float = 0.0
    # How the desk carries it out: work_order (team does it), visitor_pass, parking, fan_out, legacy
    action: str = "work_order"
    # Extra teams that get their own work order (onboarding: IT and facilities as well as HR)
    fan_out: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()


PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook("meeting_room", "Meeting room booking", prefix="ROOM", action="legacy",
             aliases=("room", "meeting", "room_booking", "conference_room")),
    Playbook("invoice", "Vendor invoice", prefix="INV", action="legacy", aliases=("vendor_invoice", "bill")),
    Playbook(
        "visitor", "Visitor pre-registration", prefix="VIS", action="visitor_pass",
        required=((("visitor_names",), "Who is visiting (name and company)?"),
                  (("visit_date",), "Which date and time is the visit?")),
        aliases=("guest", "visitor_management", "gate_pass"),
    ),
    Playbook(
        "parking", "Guest parking", prefix="PRK", action="parking",
        required=((("vehicle_numbers",), "What is the vehicle number?"),
                  (("visit_date",), "Which date do you need parking?")),
        aliases=("guest_parking", "car_parking"),
    ),
    Playbook(
        "supplies", "Office supplies", prefix="SUP", auto_spend_limit=5000.0,
        required=((("items", "item", "quantity", "description"), "What items do you need, and how many?"),),
        aliases=("stationery", "office_supplies", "peripherals"),
    ),
    Playbook("purchase", "Purchase request", prefix="SUP", sensitive=True, aliases=("procurement",)),
    Playbook(
        "travel", "Travel / cab", prefix="TRV",
        required=((("travel_date", "visit_date", "pickup_time", "date"), "When do you need to travel (date and time)?"),
                  (("pickup", "from", "route", "destination", "to", "drop"), "From where to where?")),
        aliases=("cab", "taxi", "airport_transfer", "hotel", "flight"),
    ),
    Playbook(
        "onboarding", "New joiner onboarding", prefix="ONB", action="fan_out", fan_out=("it_support", "maintenance"),
        required=((("employee_name", "joiner_name", "name"), "What is the new joiner's name?"),
                  (("joining_date", "start_date", "date"), "What is their joining date?")),
        aliases=("new_joiner", "joiner"),
    ),
    Playbook("offboarding", "Employee exit", prefix="ONB", sensitive=True, action="fan_out", fan_out=("it_support",)),
    Playbook("it_support", "IT support", prefix="ITS", aliases=("it", "tech_support")),
    Playbook("laptop", "Laptop / device", prefix="ITS"),
    Playbook("network", "Network / Wi-Fi", prefix="ITS", aliases=("wifi",)),
    Playbook("access_card", "Access card", prefix="ITS", sensitive=True, aliases=("access", "id_card")),
    Playbook("maintenance", "Maintenance", aliases=("facility", "facilities", "repair")),
    Playbook("hvac", "Air conditioning", aliases=("ac", "air_conditioning")),
    Playbook("electrical", "Electrical"),
    Playbook("plumbing", "Plumbing"),
    Playbook("housekeeping", "Housekeeping", aliases=("cleaning",)),
    Playbook("catering", "Catering", prefix="CAT", auto_spend_limit=5000.0, aliases=("food",)),
    Playbook("hr_query", "HR query", prefix="HRQ", sensitive=True),
    Playbook("security", "Security", sensitive=True),
    Playbook("payment", "Payment", sensitive=True),
    Playbook("reimbursement", "Reimbursement", sensitive=True),
    Playbook("courier", "Courier"),
    Playbook("general", "General admin request"),
)

_BY_CATEGORY = {p.category: p for p in PLAYBOOKS}
_ALIASES = {alias: p.category for p in PLAYBOOKS for alias in p.aliases}

LEGACY_CATEGORIES = {p.category for p in PLAYBOOKS if p.action == "legacy"}

_SENSITIVE_TEXT = re.compile(
    r"\b(?:bank\s+(?:details|account)|salary|payroll|confidential|legal\s+notice|disciplin\w*|"
    r"harass\w*|terminat\w*|resign\w*|server\s+room|data\s*cent(?:er|re)|master\s+key|cctv\s+footage)\b",
    re.I,
)
_AMOUNT = re.compile(r"(?:inr|rs\.?|₹)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:inr|rupees|rs)\b", re.I)

SUPPLIES_AUTO_LIMIT = _BY_CATEGORY["supplies"].auto_spend_limit


def normalize_category(value: Optional[str]) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_") or "general"
    return _ALIASES.get(raw, raw)


def playbook_for(category: Optional[str]) -> Playbook:
    cat = normalize_category(category)
    return _BY_CATEGORY.get(cat) or Playbook(cat, cat.replace("_", " ").capitalize())


def has_playbook(category: Optional[str]) -> bool:
    return normalize_category(category) in _BY_CATEGORY


def case_prefix(category: str) -> str:
    return playbook_for(category).prefix


def missing_questions(category: str, details: dict[str, Any]) -> list[str]:
    out = []
    for keys, question in playbook_for(category).required:
        if not any(details.get(k) not in (None, "", [], {}) for k in keys):
            out.append(question)
    return out


def largest_amount(text: str) -> float:
    best = 0.0
    for m in _AMOUNT.finditer(text or ""):
        num = (m.group(1) or m.group(2) or "").replace(",", "")
        try:
            best = max(best, float(num))
        except ValueError:
            continue
    return best


@dataclass
class RiskVerdict:
    needs_admin: bool
    reason: str = ""
    checks: list[str] = field(default_factory=list)


def assess_risk(
    *,
    category: str,
    text: str,
    details: dict[str, Any],
    agent_flag: bool,
    agent_reason: str = "",
    confidence: float = 1.0,
    spend_limit: float = 0.0,
    known: bool = True,
) -> RiskVerdict:
    """Hard rules can only add caution to what the model said, never remove it.

    known=False: no playbook and no department handles this kind of work, so the admin decides.
    """
    book = playbook_for(category)
    cat = book.category
    if agent_flag:
        return RiskVerdict(True, agent_reason or "flagged as sensitive")
    if not known:
        return RiskVerdict(True, f"no team is set up for {cat.replace('_', ' ')} requests yet")
    if book.sensitive:
        return RiskVerdict(True, f"{cat.replace('_', ' ')} requests need admin sign-off")
    match = _SENSITIVE_TEXT.search(text or "")
    if match:
        return RiskVerdict(True, f"mentions {match.group(0).lower()}")
    amount = max(largest_amount(text), float(details.get("amount") or 0) if _is_number(details.get("amount")) else 0.0)
    limit = spend_limit or book.auto_spend_limit
    if amount and (not limit or amount > limit):
        return RiskVerdict(True, f"spend of INR {amount:,.0f} is above the auto-approve limit")
    if confidence < 0.45:
        return RiskVerdict(True, "the request is unclear")
    return RiskVerdict(False)


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
