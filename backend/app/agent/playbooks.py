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
    # Owning department when no department in Company setup lists this category
    department: str = "ADMIN"
    # Optional details worth asking for alongside the blocking ones (never hold the work up)
    nice_to_have: tuple[str, ...] = ()


_WHERE = ("location", "floor", "area", "room", "desk", "office", "cabin", "wing", "seat")
_WHAT = ("issue", "description", "problem", "details", "symptom")
_WHEN = ("date", "visit_date", "required_date", "needed_by", "start_date", "event_date", "travel_date")

PLAYBOOKS: tuple[Playbook, ...] = (
    Playbook("meeting_room", "Meeting room booking", prefix="ROOM", action="legacy",
             aliases=("room", "meeting", "room_booking", "conference_room", "training_room", "training"),
             department="ADMIN"),
    Playbook("invoice", "Vendor invoice", prefix="INV", action="legacy", aliases=("vendor_invoice", "bill"),
             department="FINANCE"),
    # ---- front desk & security
    Playbook(
        "visitor", "Visitor pre-registration", prefix="VIS", action="visitor_pass", department="SECURITY",
        required=((("visitor_names",), "Who is visiting (name and company)?"),
                  (("visit_date",), "Which date and time is the visit?")),
        aliases=("guest", "visitor_management", "interview_candidate", "candidate_visit"),
        nice_to_have=("Will they bring a laptop or a car (vehicle number)?",),
    ),
    Playbook(
        "parking", "Parking", prefix="PRK", action="parking", department="SECURITY",
        required=((("vehicle_numbers",), "What is the vehicle number?"),
                  (("visit_date",), "Which date do you need parking?")),
        aliases=("guest_parking", "car_parking", "employee_parking", "bike_parking", "parking_sticker"),
    ),
    Playbook(
        "material_gate_pass", "Material gate pass", prefix="MGP", department="SECURITY",
        required=((("items", "item", "material", "description"), "Which items are going out (and how many)?"),
                  (("returnable", "pass_type"), "Is it returnable (coming back, e.g. repair) or non-returnable?"),
                  (_WHEN, "On which date will it go out?")),
        aliases=("gate_pass", "material_pass", "rgp", "nrgp", "returnable_gate_pass", "asset_out", "material_out"),
        nice_to_have=("Who is carrying it / vehicle number?",),
    ),
    Playbook(
        "lost_found", "Lost & found", prefix="LNF", department="SECURITY",
        required=((("item", "items", "description"), "What was lost or found (describe it)?"),
                  (_WHERE, "Where (and roughly when) was it lost or found?")),
        aliases=("lost_and_found", "lost_item", "found_item", "lost_property"),
    ),
    Playbook(
        "keys_locker", "Keys & lockers", prefix="KEY", department="SECURITY",
        aliases=("locker", "key", "keys", "duplicate_key", "cabin_key", "drawer_key"),
    ),
    Playbook("security", "Security", sensitive=True, department="SECURITY",
             aliases=("cctv", "security_incident", "guard")),
    Playbook("access_card", "Access card / ID", prefix="ITS", sensitive=True, department="IT",
             aliases=("access", "id_card", "badge", "access_control", "lost_card")),
    # ---- facilities
    Playbook(
        "maintenance", "Maintenance", department="FACILITIES",
        required=((_WHERE, "Where exactly is it (floor / area / desk)?"),),
        aliases=("facility", "facilities", "repair", "civil", "carpentry", "painting", "lift", "elevator", "door", "lights"),
    ),
    Playbook("hvac", "Air conditioning", department="FACILITIES",
             required=((_WHERE, "Which floor / area is affected?"),),
             aliases=("ac", "air_conditioning", "cooling", "heating", "ventilation")),
    Playbook("electrical", "Electrical", department="FACILITIES",
             required=((_WHERE, "Where exactly (floor / area / desk)?"),),
             aliases=("power", "socket", "ups", "lighting")),
    Playbook("plumbing", "Plumbing", department="FACILITIES",
             required=((_WHERE, "Which washroom / pantry / floor?"),),
             aliases=("washroom", "toilet", "water_leak", "tap")),
    Playbook("furniture", "Furniture", department="FACILITIES",
             required=((("item", "items", "description", "issue", "problem"), "Which item (chair, desk, drawer...) and what's needed?"),
                       (_WHERE, "Where is it (floor / desk number)?")),
             aliases=("chair", "desk_repair", "table", "drawer")),
    Playbook("pest_control", "Pest control", department="FACILITIES",
             required=((_WHERE, "Where did you see it (floor / area)?"),),
             aliases=("pests", "pest", "rodents", "rats", "cockroach", "termites", "mosquito")),
    Playbook("waste_disposal", "Waste / scrap disposal", department="FACILITIES",
             required=((("items", "item", "description"), "What needs to be disposed of (and roughly how much)?"),),
             aliases=("e_waste", "ewaste", "scrap", "garbage", "waste")),
    Playbook("health_safety", "Health & safety", prefix="EHS", department="FACILITIES",
             aliases=("safety", "incident", "first_aid", "ehs", "fire_safety", "fire_extinguisher", "medical")),
    # ---- housekeeping & pantry
    Playbook("housekeeping", "Housekeeping", department="HOUSEKEEPING",
             required=((_WHERE, "Which area needs attention (floor / room / washroom)?"),),
             aliases=("cleaning", "deep_cleaning", "spill", "sanitisation", "sanitization")),
    Playbook("pantry", "Pantry", department="HOUSEKEEPING",
             aliases=("water_dispenser", "coffee_machine", "tea", "coffee", "drinking_water", "pantry_supplies")),
    # ---- cafeteria & events
    Playbook(
        "catering", "Catering", prefix="CAT", auto_spend_limit=5000.0, department="CAFETERIA",
        required=((_WHEN, "For which date and time?"),
                  (("headcount", "attendees", "quantity", "people", "pax"), "For how many people?")),
        aliases=("food", "snacks", "lunch_order", "high_tea", "refreshments"),
        nice_to_have=("Veg / non-veg split and any allergies?", "Cost centre for the spend?"),
    ),
    Playbook("cafeteria", "Cafeteria", department="CAFETERIA",
             aliases=("canteen", "food_coupon", "meal_card", "food_quality", "menu")),
    Playbook(
        "event", "Event / celebration", prefix="EVT", auto_spend_limit=5000.0, department="ADMIN",
        required=((_WHEN, "What is the date and time?"),
                  (("headcount", "attendees", "people", "pax"), "Roughly how many people?")),
        aliases=("celebration", "party", "town_hall", "townhall", "offsite", "festival", "birthday", "farewell",
                 "team_outing", "employee_engagement"),
        nice_to_have=("Venue preference, budget and cost centre?",),
    ),
    # ---- workplace
    Playbook(
        "seating", "Seating / desk move", prefix="SEAT", department="ADMIN",
        required=((("employee_name", "employees", "name", "team"), "Who needs the seat / move (name or team)?"),
                  (_WHEN, "From which date?")),
        aliases=("seat", "desk_allocation", "workstation", "seat_change", "desk_move", "relocation", "shifting",
                 "hot_desk", "cabin_allocation"),
        nice_to_have=("Preferred floor / near which team?",),
    ),
    Playbook(
        "supplies", "Office supplies", prefix="SUP", auto_spend_limit=5000.0, department="ADMIN",
        required=((("items", "item", "quantity", "description"), "What items do you need, and how many?"),),
        aliases=("stationery", "office_supplies", "peripherals", "consumables", "toner", "cartridge"),
    ),
    Playbook(
        "printing", "Printing / business cards", prefix="PRT", auto_spend_limit=3000.0, department="ADMIN",
        required=((("items", "item", "quantity", "description"), "What needs printing, and how many?"),),
        aliases=("business_cards", "visiting_cards", "photocopy", "print", "xerox", "binding", "id_print"),
    ),
    Playbook(
        "courier", "Courier / mailroom", prefix="CUR", department="ADMIN",
        required=((("recipient", "address", "to", "destination", "tracking_number", "awb", "sender"),
                   "Is it outgoing (recipient name, address, phone) or a parcel you're expecting (sender / tracking no.)?"),),
        aliases=("parcel", "dispatch", "mailroom", "post", "package", "inward_courier", "outward_courier"),
    ),
    Playbook("purchase", "Purchase request", prefix="SUP", sensitive=True, department="PROCUREMENT",
             aliases=("procurement", "buy", "quotation")),
    Playbook("vendor", "Vendor management", prefix="VND", sensitive=True, department="PROCUREMENT",
             aliases=("vendor_onboarding", "new_vendor", "vendor_issue", "amc", "contract_renewal")),
    # ---- travel & transport
    Playbook(
        "travel", "Travel / cab", prefix="TRV", department="TRAVEL",
        required=((("travel_date", "visit_date", "pickup_time", "date"), "When do you need to travel (date and time)?"),
                  (("pickup", "from", "route", "destination", "to", "drop"), "From where to where?")),
        aliases=("cab", "taxi", "airport_transfer", "hotel", "flight", "train", "visa", "airport_pickup"),
    ),
    Playbook(
        "employee_transport", "Employee transport", prefix="TRN", department="TRAVEL",
        required=((("pickup", "address", "route", "from", "location"), "Which pickup / drop address or route?"),
                  (("shift", "timing", "time", "pickup_time"), "Which shift / timing?")),
        aliases=("shuttle", "pickup_drop", "cab_service", "transport", "night_drop", "office_bus", "route_change"),
        nice_to_have=("From which date?",),
    ),
    Playbook(
        "guest_house", "Guest house / stay", prefix="GH", department="ADMIN",
        required=((("guest_name", "guest_names", "visitor_names", "employee_name", "name"), "Who is staying?"),
                  (("check_in", "date", "visit_date", "start_date"), "Check-in date (and check-out / number of nights)?")),
        aliases=("accommodation", "stay", "guesthouse", "company_flat", "lodging"),
    ),
    # ---- people
    Playbook(
        "onboarding", "New joiner onboarding", prefix="ONB", action="fan_out", department="HR",
        fan_out=("it_support", "maintenance", "access_card"),
        required=((("employee_name", "joiner_name", "name", "new_joiner", "joinee_name", "full_name", "candidate_name",
                    "employee", "on_behalf_of"), "What is the new joiner's name?"),
                  (("joining_date", "start_date", "date", "date_of_joining", "doj"), "What is their joining date?")),
        aliases=("new_joiner", "joiner", "new_hire"),
        nice_to_have=("Team / manager, location and laptop type?",),
    ),
    Playbook("offboarding", "Employee exit", prefix="EXT", sensitive=True, action="fan_out", department="HR",
             fan_out=("it_support", "access_card"), aliases=("exit", "last_working_day", "relieving")),
    Playbook("hr_query", "HR query", prefix="HRQ", sensitive=True, department="HR",
             aliases=("hr", "leave", "payslip", "attendance")),
    # ---- IT
    Playbook("it_support", "IT support", prefix="ITS", department="IT",
             required=((_WHAT, "What's the problem (and any error message)?"),),
             aliases=("it", "tech_support", "printer", "email_issue", "password", "vpn", "projector", "monitor")),
    Playbook("laptop", "Laptop / device", prefix="ITS", department="IT", aliases=("device", "desktop", "keyboard", "mouse")),
    Playbook("network", "Network / Wi-Fi", prefix="ITS", department="IT", aliases=("wifi", "internet", "lan")),
    Playbook("software", "Software / licence", prefix="ITS", department="IT",
             required=((("software", "item", "name", "description"), "Which software / licence do you need?"),),
             aliases=("licence", "license", "software_install", "subscription", "application_access")),
    Playbook("phone_sim", "Phone / SIM", prefix="ITS", department="IT", aliases=("sim", "mobile", "phone", "data_card")),
    Playbook("asset", "Asset movement / return", prefix="AST", department="IT",
             aliases=("asset_return", "asset_transfer", "asset_tagging", "asset_allocation")),
    # ---- finance
    Playbook("payment", "Payment", sensitive=True, department="FINANCE"),
    Playbook("reimbursement", "Reimbursement", sensitive=True, department="FINANCE", aliases=("expense", "claim")),
    Playbook("general", "General admin request", department="ADMIN", aliases=("other", "misc", "admin")),
)

_BY_CATEGORY = {p.category: p for p in PLAYBOOKS}
_ALIASES = {alias: p.category for p in PLAYBOOKS for alias in p.aliases}

LEGACY_CATEGORIES = {p.category for p in PLAYBOOKS if p.action == "legacy"}

_SENSITIVE_TEXT = re.compile(
    r"\b(?:bank\s+(?:details|account)|salary|payroll|confidential|legal\s+notice|disciplin\w*|"
    r"harass\w*|terminat\w*|resign\w*|server\s+room|data\s*cent(?:er|re)|master\s+key|cctv\s+footage)\b",
    re.I,
)
_AFTER_HOURS = re.compile(
    r"\b(?:after[\s-]?(?:office\s+)?hours|out\s+of\s+office\s+hours|(?:on\s+)?(?:the\s+)?(?:weekend|sunday|saturday|holiday|night)\s+"
    r"(?:access|entry|work(?:ing)?|permission|opening)|(?:access|entry|permission|open\s+the\s+office)\b[^.\n]{0,40}"
    r"\b(?:after[\s-]?hours|weekend|sunday|saturday|holiday|overnight|late\s+night|after\s+(?:8|9|10|11)\s*pm))\b",
    re.I,
)
# A cab to catch a flight is not a flight booking - only bookings of tickets / stays need approval.
_TRAVEL_BOOKING = re.compile(
    r"\b(?:flight|air|train|rail|bus)\s+tickets?\b|\b(?:book|booking|reserve|arrange)\b[^.\n]{0,30}\b(?:flights?|trains?|hotels?|stay)\b|"
    r"\bhotel\s+(?:room|stay|booking|accommodation)\b|\bvisa\b",
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


_LOCATION_IN_TEXT = re.compile(
    r"\b(?:\d+(?:st|nd|rd|th)?\s*(?:floor|flr|fl)\b|(?:floor|flr|level|wing|block|tower|room|desk|cabin|bay|seat)\s*(?:no\.?\s*)?[\w-]+|"
    r"ground\s+floor|basement|terrace|rooftop|lobby|reception|pantry|cafeteria|canteen|washroom|restroom|toilet|"
    r"conference\s+room|meeting\s+room|boardroom|server\s+room|parking|gate|entrance|corridor|lift\s+lobby|"
    r"near\s+(?:the\s+)?\w+)",
    re.I,
)


def label_value(text: str, key: str) -> Optional[str]:
    label = re.escape(key.replace("_", " ")).replace(r"\ ", r"[\s_-]*")
    m = re.search(rf"^[\s>*\u2022-]*{label}\s*[:=\-]\s*(.{{1,120}}?)\s*$", text or "", re.I | re.M)
    return m.group(1).strip() if m else None


def fill_required(category: str, details: dict[str, Any], text: str = "") -> dict[str, Any]:
    """Before asking, use what is already there: a synonym key the model chose, or a 'Name: Priya' line in the
    email. The value is stored under the playbook's main key so every later step finds it."""
    out = dict(details or {})
    for keys, _ in playbook_for(category).required:
        main = keys[0]
        if out.get(main) not in (None, "", [], {}):
            continue
        value = next((out[k] for k in keys[1:] if out.get(k) not in (None, "", [], {})), None)
        if value is None:
            value = next((v for k in keys if (v := label_value(text, k))), None)
        if value is not None:
            out[main] = value
    return out


def missing_questions(category: str, details: dict[str, Any]) -> list[str]:
    out = []
    text = " ".join(str(v) for v in details.values() if isinstance(v, (str, int, float)))
    for keys, question in playbook_for(category).required:
        if any(details.get(k) not in (None, "", [], {}) for k in keys):
            continue
        if keys == _WHERE and _LOCATION_IN_TEXT.search(text):
            continue
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
    if cat == "material_gate_pass" and is_non_returnable(details):
        return RiskVerdict(True, "non-returnable material leaving the office needs admin sign-off")
    match = _SENSITIVE_TEXT.search(text or "")
    if match:
        return RiskVerdict(True, f"mentions {match.group(0).lower()}")
    if _AFTER_HOURS.search(text or ""):
        return RiskVerdict(True, "after-hours / holiday access needs admin sign-off")
    if cat == "travel" and _TRAVEL_BOOKING.search(text or ""):
        return RiskVerdict(True, "flight / train / hotel bookings need approval before booking")
    amount = max(largest_amount(text), float(details.get("amount") or 0) if _is_number(details.get("amount")) else 0.0)
    limit = spend_limit or book.auto_spend_limit
    if amount and (not limit or amount > limit):
        return RiskVerdict(True, f"spend of INR {amount:,.0f} is above the auto-approve limit")
    if cat == "catering" and not amount:
        return RiskVerdict(True, "catering is chargeable - cost sign-off needed before ordering")
    if confidence < 0.45:
        return RiskVerdict(True, "the request is unclear")
    return RiskVerdict(False)


def is_non_returnable(details: dict[str, Any]) -> bool:
    raw = str(details.get("returnable", details.get("pass_type", "")) or "").strip().lower()
    if raw in {"false", "no", "n"}:
        return True
    return bool(re.search(r"\b(?:non[\s-]?returnable|nrgp|not\s+(?:coming\s+)?back|permanent|scrap|sold|disposal)\b", raw))


def label_for(category: Optional[str]) -> str:
    return playbook_for(category).label


# What a team must tell us before a job counts as verified done (blueprint: no evidence, no verified closure).
_EVIDENCE: dict[str, str] = {
    **{c: "what was fixed or done (a photo works too)" for c in (
        "maintenance", "hvac", "electrical", "plumbing", "furniture", "pest_control", "waste_disposal",
        "health_safety", "housekeeping")},
    **{c: "what was done and the asset tag / ticket number if any" for c in (
        "it_support", "laptop", "network", "software", "phone_sim", "asset")},
    "access_card": "the card number issued or access granted",
    "material_gate_pass": "the gate-out entry / security sign-off",
    "courier": "the courier name and AWB / tracking number",
    "supplies": "what was delivered and to whom",
    "purchase": "the PO number or delivery note",
    "printing": "what was delivered and to whom",
    "travel": "the booking reference / cab and driver details",
    "employee_transport": "the route / cab allocated",
    "guest_house": "the booking confirmation",
    "seating": "the seat number allotted",
    "keys_locker": "the key / locker number handed over",
    "catering": "what was served and the headcount",
    "event": "what was arranged",
}

# Blueprint section 9: who may decide. D = AI only summarises; C = humans approve; B = rule-validated; A = routine.
DECISION_CLASSES = {
    "A": "Routine - the desk handles it",
    "B": "Rule-checked - the desk acts after checks",
    "C": "Human approval needed",
    "D": "Human decision only",
}
_CLASS_D = {"vendor", "payment", "hr_query", "security", "offboarding"}
_CLASS_B_ACTIONS = {"visitor_pass", "parking"}
_CLASS_B = {"material_gate_pass", "seating", "keys_locker", "meeting_room", "invoice"}


def evidence_hint(category: Optional[str]) -> str:
    return _EVIDENCE.get(normalize_category(category), "")


def decision_class(category: Optional[str], needs_admin: bool) -> str:
    book = playbook_for(category)
    if book.category in _CLASS_D:
        return "D"
    if needs_admin:
        return "C"
    if book.action in _CLASS_B_ACTIONS or book.category in _CLASS_B:
        return "B"
    return "A"


_TASK_WORDS: dict[str, re.Pattern] = {
    "it_support": re.compile(
        r"laptop|desktop|computer|e-?mail|\bsystem|log-?ins?\b|account|software|\bvpn\b|password|monitor|headset|"
        r"\bsim\b|mobile|phone|wi-?fi|\bapps?\b|tools? access|\bdata\b|backup", re.I),
    "access_card": re.compile(r"access card|id card|\bid\b(?= and access)|badge|\bcards?\b|biometric|door access|"
                              r"floor access|turnstile", re.I),
    "maintenance": re.compile(r"\bdesk|workstation|\bseat|chair|cabin|furniture|locker|drawer|pedestal|cubicle", re.I),
    "onboarding": re.compile(r"paperwork|document|induction|orientation|payroll|offer letter|contract|formalit|"
                             r"background|\bbgv\b|policy|policies|welcome kit|buddy", re.I),
    "offboarding": re.compile(r"paperwork|document|exit interview|full (?:and|&) final|\bf&f\b|relieving|"
                              r"experience letter|clearance|formalit|settlement|notice", re.I),
}

_DEFAULT_TEAM_TASKS: dict[str, dict[str, str]] = {
    "onboarding": {
        "onboarding": "Complete joining formalities, documents and induction for {who}",
        "it_support": "Laptop, company email ID and system logins ready for {who} by {when}",
        "maintenance": "Desk / workstation ready for {who} by {when}",
        "access_card": "Issue ID and access card for {who}",
    },
    "offboarding": {
        "offboarding": "Exit formalities, clearance and full & final settlement for {who}",
        "it_support": "Collect laptop and IT assets from {who}; disable email and system access after {when}",
        "access_card": "Collect ID / access card from {who} and deactivate it after {when}",
    },
}


def split_tasks(category: Optional[str], tasks: list[str], team_categories: list[str],
                details: Optional[dict] = None) -> dict[str, list[str]]:
    """Give each team on a multi-team request its own to-do list: what was asked, matched by keywords; anything
    unmatched stays with the owning team (first entry); a team left with nothing gets the playbook's default task."""
    out: dict[str, list[str]] = {c: [] for c in team_categories}
    if not team_categories:
        return out
    for task in tasks:
        text = str(task).strip().rstrip(".")
        if not text:
            continue
        scores = {c: len(_TASK_WORDS[c].findall(text)) for c in team_categories if c in _TASK_WORDS}
        best = max(scores.items(), key=lambda kv: kv[1], default=(None, 0))
        out[best[0] if best[1] else team_categories[0]].append(text)
    d = details or {}
    who = d.get("employee_name") or d.get("joiner_name") or d.get("name") or "the employee"
    when = (d.get("joining_date") or d.get("last_working_day") or d.get("start_date") or d.get("date")
            or "the agreed date")
    defaults = _DEFAULT_TEAM_TASKS.get(normalize_category(category), {})
    for c, items in out.items():
        if not items and c in defaults:
            items.append(defaults[c].format(who=who, when=when))
    return out


_LIST_ITEM = re.compile(r"^\s*(?:\d+[.)]|[-*\u2022])\s+(.+)$")
_KEY_VALUE = re.compile(r"^[\w /&'-]{1,30}:\s")


def tasks_from_text(text: str) -> list[str]:
    """Fallback when the model gives no task list: the numbered/bulleted asks in the email (not 'Key: value' facts)."""
    out = []
    for line in (text or "").splitlines():
        m = _LIST_ITEM.match(line)
        if m and not _KEY_VALUE.match(m.group(1)):
            out.append(m.group(1).strip())
    return out[:12]


def catalogue_for_prompt() -> list[dict[str, Any]]:
    """Compact request-type catalogue the model sees, so it picks real categories and asks the right things."""
    out = []
    for p in PLAYBOOKS:
        out.append({
            "category": p.category,
            "label": p.label,
            "also_called": list(p.aliases[:6]),
            "needs": [q for _, q in p.required],
            "detail_keys": [keys[0] for keys, _ in p.required],
            "admin_sign_off": p.sensitive,
            "team": p.department,
        })
    return out


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
