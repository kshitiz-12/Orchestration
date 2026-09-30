"""Site service catalogue and chargeability: what an event actually costs, and who has to approve it.

Nothing is hard-coded as free or paid here. Each requested service is looked up in the tenant's
catalogue (delivery model, rate, included limit, premium triggers). Only the chargeable portion
ends up in the cost plan and needs approval; included services are coordinated at no charge.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.company import CostCentre, SiteService

DEFAULT_SITE = "Corporate Office"
PAID_MODELS = {"SUBSIDISED", "CHARGEABLE", "OUTSOURCED"}
MODEL_LABELS = {
    "INCLUDED": "included site facility",
    "CONTRACT": "covered by existing contract",
    "SUBSIDISED": "subsidised / concessional",
    "CHARGEABLE": "chargeable internal service",
    "OUTSOURCED": "outsourced / empanelled provider",
}

DEFAULT_SITE_SERVICES: list[dict[str, Any]] = [
    {"code": "meeting_room", "name": "Meeting room", "delivery_model": "INCLUDED", "owner_department": "ADMIN"},
    {"code": "external_venue", "name": "External / off-site venue", "delivery_model": "OUTSOURCED",
     "owner_department": "ADMIN", "unit": "per_event"},
    {"code": "tea_coffee", "name": "Tea / coffee (vending and pantry)", "delivery_model": "INCLUDED",
     "owner_department": "CAFETERIA", "unit": "per_person",
     "premium_triggers": ["premium", "dedicated", "staffed", "barista", "served at the table", "branded"],
     "premium_rate": 120},
    {"code": "water", "name": "Drinking water and standard bottles", "delivery_model": "INCLUDED",
     "owner_department": "ADMIN", "unit": "per_person",
     "premium_triggers": ["branded water", "premium water", "mineral water"], "premium_rate": 40},
    {"code": "working_lunch", "name": "Working lunch (sponsored cafeteria meal)", "delivery_model": "SUBSIDISED",
     "owner_department": "CAFETERIA", "unit": "per_person", "rate": 350, "evidence_rule": "cafeteria_count"},
    {"code": "high_tea", "name": "High tea / snacks (special menu)", "delivery_model": "CHARGEABLE",
     "owner_department": "CAFETERIA", "unit": "per_person", "rate": 350, "evidence_rule": "cafeteria_count"},
    {"code": "catering_general", "name": "Catering (menu to be confirmed)", "delivery_model": "CHARGEABLE",
     "owner_department": "CAFETERIA", "unit": "per_person", "evidence_rule": "cafeteria_count"},
    {"code": "standard_av", "name": "Installed AV / VC and internal IT support", "delivery_model": "INCLUDED",
     "owner_department": "IT",
     "premium_triggers": ["external technician", "rented equipment", "hired equipment", "live stream",
                          "livestream", "event production", "extra microphones"]},
    {"code": "stationery", "name": "Standard stationery and printing", "delivery_model": "INCLUDED",
     "owner_department": "ADMIN",
     "premium_triggers": ["custom print", "customised print", "customized print", "print pack", "booklet",
                          "branded kit", "excess printing"]},
    {"code": "visitor_access", "name": "Visitor access and reception", "delivery_model": "INCLUDED",
     "owner_department": "SECURITY"},
    {"code": "visitor_parking", "name": "Internal visitor parking", "delivery_model": "INCLUDED",
     "owner_department": "SECURITY", "unit": "per_slot",
     "premium_triggers": ["external parking", "paid parking", "valet"], "premium_rate": 200},
    {"code": "local_transfer", "name": "Airport / station transfer", "delivery_model": "OUTSOURCED",
     "owner_department": "TRAVEL", "unit": "per_trip", "rate": 1500, "provider": "Empanelled transport vendor"},
    {"code": "flight", "name": "Flight (empanelled travel agent)", "delivery_model": "OUTSOURCED",
     "owner_department": "TRAVEL", "unit": "per_person", "rate": 12000},
    {"code": "hotel", "name": "Hotel (empanelled)", "delivery_model": "OUTSOURCED",
     "owner_department": "TRAVEL", "unit": "per_night", "rate": 4500},
]

DEFAULT_COST_CENTRES: list[dict[str, Any]] = [
    {"code": "SL-1101", "name": "Sales", "department": "Sales", "approver_name": "Rohan Mehta"},
    {"code": "EN-2101", "name": "Engineering", "department": "Engineering"},
    {"code": "FN-3101", "name": "Finance", "department": "Finance", "approver_name": "Vikram Rao"},
    {"code": "MK-4101", "name": "Marketing", "department": "Marketing"},
    {"code": "OP-5101", "name": "Operations", "department": "Operations", "approver_name": "Karan Malhotra"},
    {"code": "PE-6101", "name": "People", "department": "People"},
    {"code": "TE-7101", "name": "Technology", "department": "Technology"},
    {"code": "LG-8101", "name": "Legal", "department": "Legal"},
]

_NONE = {"", "none", "no", "n/a", "na", "nil", "nothing", "not needed", "not required", "no thanks", "0"}
_MEAL_RE = re.compile(r"\b(lunch|dinner|breakfast|meals?|buffet|thali)\b", re.I)
_SNACK_RE = re.compile(r"\b(high[\s-]?tea|snacks?|sandwich\w*|cookies|samosa\w*|refreshments?|pastr\w+|finger\s+food)\b", re.I)
_BEVERAGE_RE = re.compile(r"\b(tea|coffee|chai|beverages?|vending|juice)\b", re.I)
_WATER_RE = re.compile(r"\bwater\b", re.I)
_STATIONERY_RE = re.compile(r"\b(stationery|stationary|markers?|notepads?|flip\s*charts?|print\w*|pens)\b", re.I)


def ensure_site_services(session: Session, tenant_id: str) -> None:
    """Idempotent sample catalogue and cost centres; never overwrites rows the company edited."""
    have = {
        (s.site, s.code)
        for s in session.exec(select(SiteService).where(SiteService.tenant_id == tenant_id)).all()
    }
    for spec in DEFAULT_SITE_SERVICES:
        if (DEFAULT_SITE, spec["code"]) in have:
            continue
        session.add(SiteService(tenant_id=tenant_id, site=DEFAULT_SITE, notes="Sample data - edit in Company setup.", **spec))
    have_cc = {c.code for c in session.exec(select(CostCentre).where(CostCentre.tenant_id == tenant_id)).all()}
    for spec in DEFAULT_COST_CENTRES:
        if spec["code"] not in have_cc:
            session.add(CostCentre(tenant_id=tenant_id, **spec))
    session.flush()


def catalogue(session: Session, tenant_id: str, site: str = DEFAULT_SITE) -> dict[str, SiteService]:
    rows = session.exec(
        select(SiteService).where(SiteService.tenant_id == tenant_id, SiteService.is_active == True)  # noqa: E712
    ).all()
    out: dict[str, SiteService] = {}
    for row in rows:
        # A site-specific row wins over the default site's row for the same service
        if row.site == site or row.code not in out:
            out[row.code] = row
    return out


def resolve_cost_centre(session: Session, tenant_id: str, facts: dict[str, Any], requester_email: Optional[str]) -> dict[str, Any]:
    from app.agent.company_seed import is_placeholder
    from app.models.org import Person

    code = str(facts.get("cost_centre") or "").strip().upper()
    row = None
    if code:
        row = session.exec(
            select(CostCentre).where(CostCentre.tenant_id == tenant_id, CostCentre.code == code)
        ).first()
    department = None
    if row is None and requester_email:
        person = session.exec(select(Person).where(Person.email == requester_email.strip().lower())).first()
        department = person.department if person else None
        if department:
            row = session.exec(
                select(CostCentre).where(
                    CostCentre.tenant_id == tenant_id,
                    CostCentre.department == department,
                    CostCentre.is_active == True,  # noqa: E712
                )
            ).first()
    approver_email = (row.approver_email or "").strip().lower() if row else ""
    if approver_email and is_placeholder(approver_email):
        approver_email = ""
    return {
        "code": code or (row.code if row else None),
        "name": row.name if row else None,
        "source": "requester" if code else ("department" if row else None),
        "department": department or (row.department if row else None),
        "approver_name": facts.get("cost_approver_name") or (row.approver_name if row else None),
        "approver_email": approver_email or None,
    }


def cost_centre_approver_emails(session: Session, tenant_id: str) -> set[str]:
    """Department heads named on cost centres: their replies are approval decisions, not new requests."""
    from app.agent.company_seed import is_placeholder

    rows = session.exec(
        select(CostCentre).where(CostCentre.tenant_id == tenant_id, CostCentre.is_active == True)  # noqa: E712
    ).all()
    return {
        e for e in ((r.approver_email or "").strip().lower() for r in rows) if e and not is_placeholder(e)
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _catering_text(facts: dict[str, Any]) -> str:
    parts = [_text(facts.get("catering"))]
    parts += [_text(n) for n in facts.get("catering_notes") or []]
    return " ".join(p for p in parts if p)


def _open_request_text(facts: dict[str, Any]) -> str:
    return " ".join(
        _text(r.get("text") if isinstance(r, dict) else r) for r in facts.get("open_requests") or []
    )


def _premium(service: SiteService, text: str) -> bool:
    low = text.lower()
    return any(t and t.lower() in low for t in service.premium_triggers or [])


def _line(
    service: Optional[SiteService],
    code: str,
    qty: float,
    *,
    premium: bool = False,
    rate_override: Optional[float] = None,
    rate_source: Optional[str] = None,
    note: str = "",
) -> dict[str, Any]:
    if service is None:
        # Not in the catalogue: never assume free; it needs a quotation and a decision
        return {
            "code": code, "name": code.replace("_", " ").capitalize(), "model": "UNLISTED", "owner": "ADMIN",
            "qty": qty, "chargeable_qty": qty, "rate": None, "amount": None, "chargeable": True,
            "quote_required": True, "note": note or "not in the site service catalogue",
        }
    model = (service.delivery_model or "INCLUDED").upper()
    paid = model in PAID_MODELS or premium
    free_qty = float(service.included_limit or 0) if not premium else 0.0
    chargeable_qty = max(0.0, qty - free_qty) if paid else 0.0
    rate = rate_override if rate_override is not None else (
        float(service.premium_rate or 0) if premium else float(service.rate or 0)
    )
    amount = round(rate * chargeable_qty, 2) if (paid and rate) else (0.0 if not paid else None)
    return {
        "code": service.code,
        "name": service.name,
        "model": "PREMIUM" if premium else model,
        "model_label": "premium / special request" if premium else MODEL_LABELS.get(model, model.lower()),
        "owner": service.owner_department,
        "provider": service.provider,
        "unit": service.unit,
        "qty": qty,
        "chargeable_qty": chargeable_qty,
        "rate": rate if paid else 0.0,
        "rate_source": rate_source or ("site_catalogue" if paid and rate else None),
        "amount": amount,
        "chargeable": bool(paid and chargeable_qty > 0),
        "quote_required": bool(paid and chargeable_qty > 0 and not rate),
        "evidence_rule": service.evidence_rule,
        "note": note,
    }


def build_cost_plan(
    session: Session,
    tenant_id: str,
    facts: dict[str, Any],
    *,
    requester_email: Optional[str] = None,
) -> dict[str, Any]:
    """Classify every requested service by the site catalogue into included vs chargeable lines."""
    from app.services.catering import catering_quote
    from app.services.event_facts import day_count, event_kind, travel_needed
    from app.services.meeting_room import (
        external_visitor_count,
        guest_vehicle_count,
        hybrid_needed,
        presentation_needed,
        seats_needed,
    )

    cat = catalogue(session, tenant_id)
    headcount = seats_needed(facts) or 1
    days = day_count(facts)
    extra_text = _open_request_text(facts)
    lines: list[dict[str, Any]] = []

    booked = facts.get("booked_room") or facts.get("proposed_room") or {}
    if booked.get("external_venue"):
        lines.append(_line(cat.get("external_venue"), "external_venue", 1, note=str(booked.get("name") or "")))
    else:
        lines.append(_line(cat.get("meeting_room"), "meeting_room", days, note=str(booked.get("name") or "")))

    food = _catering_text(facts)
    if food.lower() not in _NONE:
        meal, snack, drink = _MEAL_RE.search(food), _SNACK_RE.search(food), _BEVERAGE_RE.search(food)
        cater_codes: list[str] = []
        if meal:
            cater_codes.append("working_lunch")
        if snack:
            cater_codes.append("high_tea")
        if drink:
            cater_codes.append("tea_coffee")
        if _WATER_RE.search(food) and not cater_codes:
            cater_codes.append("water")
        if not cater_codes:
            cater_codes.append("catering_general")
        for code in cater_codes:
            svc = cat.get(code)
            premium = bool(svc and (svc.delivery_model or "").upper() == "INCLUDED" and _premium(svc, food))
            qty = float(headcount * days)
            if svc is not None and ((svc.delivery_model or "").upper() in PAID_MODELS or premium):
                quote = catering_quote(session, tenant_id, headcount)
                catalogue_rate = float((svc.premium_rate if premium else svc.rate) or 0)
                if premium:
                    rate, source = catalogue_rate or None, "site_catalogue"
                elif quote.get("rate_source") in {"contract", "vendor_pricing"}:
                    # Existing caterer contract covers the menu: its rate is the applicable one
                    rate, source = quote.get("rate"), quote.get("rate_source")
                elif catalogue_rate:
                    rate, source = catalogue_rate, "site_catalogue"
                else:
                    rate, source = quote.get("rate"), quote.get("rate_source")
                line = _line(svc, code, qty, premium=premium, rate_override=rate, rate_source=source)
                line["vendor"] = quote.get("vendor")
                line["contract"] = quote.get("contract") if source == "contract" else None
                lines.append(line)
            else:
                lines.append(_line(svc, code, qty, premium=premium))
        if not any(line["code"] == "water" for line in lines):
            lines.append(_line(cat.get("water"), "water", float(headcount * days)))

    if hybrid_needed(facts) or presentation_needed(facts) or event_kind(facts) == "training":
        svc = cat.get("standard_av")
        lines.append(_line(svc, "standard_av", 1, premium=bool(svc and _premium(svc, extra_text + " " + _text(facts.get("hybrid_av"))))))

    stationery_text = f"{extra_text} {_text(facts.get('stationery'))}"
    if event_kind(facts) == "training" or _STATIONERY_RE.search(stationery_text):
        svc = cat.get("stationery")
        lines.append(_line(svc, "stationery", 1, premium=bool(svc and _premium(svc, stationery_text))))

    if external_visitor_count(facts) > 0:
        lines.append(_line(cat.get("visitor_access"), "visitor_access", external_visitor_count(facts)))
    if guest_vehicle_count(facts) > 0:
        svc = cat.get("visitor_parking")
        park_text = f"{extra_text} {_text(facts.get('special_access'))}"
        lines.append(_line(svc, "visitor_parking", guest_vehicle_count(facts), premium=bool(svc and _premium(svc, park_text))))

    if travel_needed(facts):
        people = int(facts.get("travellers") or 0)
        nights = days if facts.get("travel_hotel") else 0
        if facts.get("travel_flight"):
            lines.append(_line(cat.get("flight"), "flight", people, note=f"from {facts.get('travel_from')}" if facts.get("travel_from") else ""))
        if nights:
            lines.append(_line(cat.get("hotel"), "hotel", people * nights, note=f"{nights} night(s)"))
        if facts.get("travel_transfer") or not (facts.get("travel_flight") or nights):
            trips = people * (2 if nights else 1)
            lines.append(_line(cat.get("local_transfer"), "local_transfer", trips))

    chargeable = [line for line in lines if line["chargeable"]]
    total = round(sum(float(line["amount"] or 0) for line in chargeable), 2)
    return {
        "site": DEFAULT_SITE,
        "currency": "INR",
        "headcount": headcount,
        "days": days,
        "lines": lines,
        "included": [line["name"] for line in lines if not line["chargeable"]],
        "chargeable": [line["name"] for line in chargeable],
        "chargeable_total": total,
        "quote_pending": any(line.get("quote_required") for line in chargeable),
        "cost_centre": resolve_cost_centre(session, tenant_id, facts, requester_email),
    }


def has_charges(plan: Optional[dict[str, Any]]) -> bool:
    return bool(plan and plan.get("chargeable"))


def chargeable_lines(plan: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    return [line for line in (plan or {}).get("lines") or [] if line.get("chargeable")]


def only_catering_charges(plan: Optional[dict[str, Any]]) -> bool:
    lines = chargeable_lines(plan)
    return bool(lines) and all(line.get("owner") == "CAFETERIA" for line in lines)


def _money(amount: Any, currency: str = "INR") -> str:
    if not isinstance(amount, (int, float)):
        return "to be quoted"
    symbol = "Rs" if currency == "INR" else currency
    return f"{symbol} {amount:,.0f}"


def _qty_label(line: dict[str, Any]) -> str:
    qty = line.get("chargeable_qty") or line.get("qty") or 0
    unit = {
        "per_person": "people", "per_trip": "trips", "per_night": "room-nights", "per_slot": "slots",
    }.get(str(line.get("unit") or ""), "")
    qty_text = f"{qty:g}" if isinstance(qty, (int, float)) else str(qty)
    return f"{qty_text} {unit}".strip()


def cost_plan_text(plan: Optional[dict[str, Any]], *, for_approver: bool = True) -> str:
    """Approval body: chargeable components with amounts, then what is included at no charge."""
    if not plan:
        return ""
    currency = plan.get("currency") or "INR"
    lines: list[str] = []
    cc = plan.get("cost_centre") or {}
    if for_approver:
        cc_line = cc.get("code") or "not given yet (asked from the requester)"
        if cc.get("name") and cc.get("code"):
            cc_line += f" ({cc['name']})"
        lines.append(f"Cost centre: {cc_line}")
    charged = chargeable_lines(plan)
    if charged:
        lines.append("Chargeable:")
        for line in charged:
            rate = line.get("rate")
            calc = f"{_qty_label(line)} x {_money(rate, currency)}" if rate else _qty_label(line)
            source = " (contract rate)" if line.get("rate_source") == "contract" else ""
            lines.append(f"- {line['name']}: {calc} = {_money(line.get('amount'), currency)}{source}")
        total = plan.get("chargeable_total") or 0
        suffix = " + items to be quoted" if plan.get("quote_pending") else ""
        lines.append(f"Estimated chargeable total: {_money(total, currency)} before tax{suffix}")
    included = plan.get("included") or []
    if included:
        lines.append("Included at no incremental charge: " + ", ".join(n[:1].lower() + n[1:] for n in included) + ".")
    return "\n".join(lines)


def included_note(plan: Optional[dict[str, Any]]) -> str:
    """One sentence for the requester: what needs no approval and what the approval will cover."""
    if not plan:
        return ""
    included = [n for n in plan.get("included") or []]
    charged = plan.get("chargeable") or []
    parts = []
    if included:
        parts.append("No separate approval is needed for " + ", ".join(n[:1].lower() + n[1:] for n in included) + ".")
    if charged:
        parts.append("Cost approval will cover only " + ", ".join(n[:1].lower() + n[1:] for n in charged) + ".")
    return " ".join(parts)
