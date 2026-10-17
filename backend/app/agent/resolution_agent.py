"""Operations Resolution Agent — investigate cases and answer admin ledger questions."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.agent.resolution_tools import (
    FACILITIES_CATS,
    case_history_summary,
    find_open_cases_for_location_resource,
    list_approved_vendors,
    replace_due,
    run_tool,
    search_knowledge,
    team_route_info,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.outcome import Outcome
from app.services.ops_ledger import repairs_summary, spend_summary, who_did_what

logger = get_logger(__name__)

ActionName = Literal[
    "dispatch_work_order",
    "link_existing",
    "request_approval",
    "escalate_ops",
    "ask_requester",
    "remind_team",
]


class ResolutionPlan(BaseModel):
    link_case_ref: Optional[str] = None
    create_new: bool = True
    priority: Optional[str] = None
    urgency_reason: Optional[str] = None
    vendor_hint: Optional[str] = None
    workaround: Optional[str] = None
    employee_update: Optional[str] = None
    ops_notes: Optional[str] = None
    recommended_actions: list[str] = Field(default_factory=list)
    investigation: dict[str, Any] = Field(default_factory=dict)


class AdminAnswer(BaseModel):
    reply: str
    grounded: bool = True
    data: dict[str, Any] = Field(default_factory=dict)


INVESTIGATE_INSTRUCTION = """You are the Operations Resolution Agent for a workplace email desk.
You receive tool results (JSON). Propose a ResolutionPlan for this facilities request.
Rules:
- Only use facts present in TOOL_RESULTS. Never invent vendors, case numbers, or history.
- If an open case clearly matches the same location/resource, set link_case_ref and create_new=false; action link_existing.
- Otherwise create_new=true and recommend dispatch_work_order.
- If the mail shows business impact (client meeting tomorrow, etc.), set priority HIGH or URGENT and urgency_reason.
- employee_update: one short paragraph for the employee (no fake ETAs).
- ops_notes: bullet facts for the work-order team (history/vendor if present).
Return ONLY JSON matching the schema.
"""


def _provider():
    from app.ai.gemini import GeminiProvider

    return GeminiProvider()


def _can_reason(provider: Any) -> bool:
    from app.ai.gemini import HeuristicProvider

    if get_settings().ai_emergency_stop:
        return False
    if provider is None or isinstance(provider, HeuristicProvider):
        return False
    if not (get_settings().gemini_api_key or "").strip():
        return False
    return hasattr(provider, "generate_json")


def gather_investigation(
    session: Session,
    tenant_id: str,
    *,
    outcome: Outcome,
    text: str,
) -> dict[str, Any]:
    facts = outcome.facts or {}
    category = (facts.get("agent_category") or outcome.category or "").lower()
    location_id = facts.get("location_id")
    open_cases = find_open_cases_for_location_resource(
        session, tenant_id, location_id=location_id, text=text, category=category
    )
    # Exclude self
    open_cases = [c for c in open_cases if c.get("case_reference") != outcome.case_reference]
    history = case_history_summary(session, tenant_id, location_id=location_id, category=category)
    vendors = list_approved_vendors(session, tenant_id, category=category or "hvac")
    knowledge = search_knowledge(session, tenant_id, text[:200])
    route = team_route_info(session, tenant_id, category or "maintenance", location_id)
    return {
        "open_cases": open_cases,
        "history": history,
        "vendors": vendors,
        "knowledge": knowledge,
        "route": route,
        "category": category,
        "location_id": location_id,
        "title": outcome.title,
        "priority": outcome.priority,
        "details": facts.get("details") or {},
        "raw_request": facts.get("raw_request") or text[:1500],
    }


def _heuristic_plan(bundle: dict[str, Any], text: str) -> ResolutionPlan:
    open_cases = bundle.get("open_cases") or []
    link = open_cases[0]["case_reference"] if open_cases and open_cases[0].get("score", 0) >= 2 else None
    urgent = bool(re.search(r"\b(?:urgent|asap|client\s+meeting|tomorrow|critical)\b", text or "", re.I))
    vendors = bundle.get("vendors") or []
    vendor_hint = vendors[0]["name"] if vendors else None
    notes = []
    if bundle.get("history"):
        notes.append(f"Prior related work: {bundle['history'][0].get('summary')}")
    if vendor_hint:
        notes.append(f"Approved vendor on file: {vendor_hint}")
    route = bundle.get("route") or {}
    if route.get("department_name"):
        notes.append(f"Route to {route['department_name']}")
    if link:
        return ResolutionPlan(
            link_case_ref=link,
            create_new=False,
            priority="HIGH" if urgent else None,
            urgency_reason="Business impact language in request" if urgent else None,
            vendor_hint=vendor_hint,
            employee_update=f"This looks related to open case {link}. I've linked your report so the team can continue there.",
            ops_notes="; ".join(notes) or None,
            recommended_actions=["link_existing"],
            investigation=bundle,
        )
    return ResolutionPlan(
        create_new=True,
        priority="URGENT" if urgent and re.search(r"\btomorrow|client\b", text or "", re.I) else ("HIGH" if urgent else None),
        urgency_reason="Client / deadline impact mentioned" if urgent else None,
        vendor_hint=vendor_hint,
        employee_update="I've logged this with the facilities team and asked them to prioritise it. I'll update you here.",
        ops_notes="; ".join(notes) or None,
        recommended_actions=["dispatch_work_order"],
        investigation=bundle,
    )


def investigate(
    session: Session,
    tenant_id: str,
    *,
    outcome: Outcome,
    text: str,
) -> ResolutionPlan:
    bundle = gather_investigation(session, tenant_id, outcome=outcome, text=text)
    provider = _provider()
    if _can_reason(provider):
        try:
            data, _ = provider.generate_json(
                system_instruction=INVESTIGATE_INSTRUCTION,
                payload={"TOOL_RESULTS": bundle, "REQUEST_TEXT": (text or "")[:2500]},
                temperature=0.0,
            )
            plan = ResolutionPlan.model_validate(data or {})
            plan.investigation = bundle
            if not plan.recommended_actions:
                plan.recommended_actions = ["link_existing"] if plan.link_case_ref else ["dispatch_work_order"]
            return plan
        except Exception as exc:  # noqa: BLE001
            logger.warning("resolution_agent_investigate_failed", error=str(exc)[:200])
    return _heuristic_plan(bundle, text)


def investigate_stalled(
    session: Session,
    tenant_id: str,
    *,
    outcome: Outcome,
) -> ResolutionPlan:
    facts = outcome.facts or {}
    status = run_tool(session, tenant_id, "work_order_status", {"outcome_id": outcome.outcome_id})
    vendors = list_approved_vendors(session, tenant_id, category=(facts.get("agent_category") or "maintenance"))
    history = case_history_summary(
        session, tenant_id, location_id=facts.get("location_id"), category=facts.get("agent_category")
    )
    alts = [v["name"] for v in vendors[:3]]
    notes = (
        f"No timely team progress on {outcome.case_reference}. "
        f"Stage={status.get('stage')}. "
        + (f"Approved alternatives: {', '.join(alts)}. " if alts else "")
        + "Reassignment needs facilities/admin approval."
    )
    return ResolutionPlan(
        create_new=False,
        ops_notes=notes,
        vendor_hint=alts[0] if alts else None,
        employee_update=None,
        recommended_actions=["escalate_ops", "remind_team"],
        investigation={"status": status, "vendors": vendors, "history": history[:5]},
    )


_SPEND = re.compile(r"\b(?:spend|spent|expenditure|cost|how\s+much)\b", re.I)
_REPAIR = re.compile(r"\b(?:repair|repaired|fixed|maintenance\s+done|what\s+was\s+repaired)\b", re.I)
_REPLACE = re.compile(r"\b(?:replace|replacement|low\s+stock|needs?\s+replacing|reorder)\b", re.I)
_WHO = re.compile(r"\b(?:who\s+(?:did|closed|handled|worked)|what\s+happened\s+on|history\s+of)\b", re.I)
_CASE_REF = re.compile(r"\b([A-Z]{2,5}-\d{4}-\d{3,})\b", re.I)
_DEPT = re.compile(r"\b([A-Z]{2,}(?:_[A-Z0-9]+)+)\b")
_DAYS = re.compile(r"\b(?:last|past)\s+(\d+)\s+days?\b", re.I)
_MONTH = re.compile(r"\b(?:this|current)\s+month\b", re.I)


def is_admin_analytics_question(text: str) -> bool:
    t = text or ""
    return bool(_SPEND.search(t) or _REPAIR.search(t) or _REPLACE.search(t) or _WHO.search(t))


def answer_admin_question(
    session: Session,
    tenant_id: str,
    text: str,
    *,
    location_ids: Optional[list[str]] = None,
    scope_label: Optional[str] = None,
) -> AdminAnswer:
    """Grounded admin Q&A from ledger only. location_ids limits a branch admin to their site."""
    days = 30
    if m := _DAYS.search(text or ""):
        days = max(1, min(365, int(m.group(1))))
    elif _MONTH.search(text or ""):
        days = 31
    dept = None
    if m := _DEPT.search(text or ""):
        dept = m.group(1)
    case_ref = None
    if m := _CASE_REF.search(text or ""):
        case_ref = m.group(1).upper()
    scope = f" for {scope_label}" if scope_label else ""

    if _REPLACE.search(text or ""):
        data = replace_due(session, tenant_id, location_ids=location_ids)
        low = data.get("low_stock") or []
        assets = data.get("assets_attention") or []
        lines = [f"Here's what the ledger shows needs attention{scope}:", ""]
        if low:
            lines.append("Low stock:")
            for s in low[:15]:
                lines.append(f"- {s['name']} ({s['sku_code']}): on hand {s['qty_on_hand']}, min {s['reorder_min']}")
        else:
            lines.append("Low stock: none recorded under reorder mins.")
        lines.append("")
        if assets:
            lines.append("Asset / replace signals:")
            for a in assets[:10]:
                lines.append(f"- {a.get('summary')} [{a.get('case') or a.get('tag') or '—'}]")
        else:
            lines.append("No recent asset replace/damage ledger rows.")
        return AdminAnswer(reply="\n".join(lines), grounded=True, data=data)

    if _SPEND.search(text or ""):
        data = spend_summary(session, tenant_id, department_code=dept, location_ids=location_ids, days=days)
        lines = [
            f"Spend from the operational ledger (last {days} days"
            + scope
            + (f", dept {dept}" if dept else "")
            + "):",
            f"Total recorded: INR {data['total']:,.2f} across {data['rows']} amount rows "
            f"(scanned {data['scanned']} related events).",
            "",
        ]
        if data["top"]:
            lines.append("Top lines:")
            for row in data["top"][:12]:
                lines.append(
                    f"- {row['when'][:10]} {row.get('case') or '—'} "
                    f"INR {float(row['amount'] or 0):,.0f} — {row['summary'][:120]}"
                )
        else:
            lines.append("No amount rows in range yet (spend is recorded when amount is known on close/reorder).")
        return AdminAnswer(reply="\n".join(lines), grounded=True, data=data)

    if _REPAIR.search(text or ""):
        data = repairs_summary(session, tenant_id, department_code=dept, location_ids=location_ids, days=days)
        lines = [f"Repairs / facilities ledger (last {days} days{scope}): {data['count']} events.", ""]
        for item in data["items"][:20]:
            lines.append(
                f"- {item['when'][:10]} [{item.get('case') or '—'}] {item['type']} "
                f"{item.get('category') or ''}: {item['summary'][:140]}"
            )
        if not data["items"]:
            lines.append("No repair-category ledger rows in that window.")
        return AdminAnswer(reply="\n".join(lines), grounded=True, data=data)

    if _WHO.search(text or "") or case_ref:
        data = who_did_what(
            session, tenant_id, case_reference=case_ref, department_code=dept, location_ids=location_ids, days=days
        )
        lines = [f"Who did what (ledger{scope}):", ""]
        for item in data["items"][:25]:
            lines.append(
                f"- {item['when'][:16]} {item.get('actor') or 'system'} ({item['role']}) "
                f"{item['type']} {item.get('case') or ''}: {item['summary'][:120]}"
            )
        if not data["items"]:
            lines.append("No ledger rows matched.")
        return AdminAnswer(reply="\n".join(lines), grounded=True, data=data)

    # Generic: try spend + repairs brief
    spend = spend_summary(session, tenant_id, department_code=dept, location_ids=location_ids, days=days)
    repairs = repairs_summary(session, tenant_id, department_code=dept, location_ids=location_ids, days=days)
    reply = (
        f"I can answer from the operational ledger. Last {days} days"
        + scope
        + (f", {dept}" if dept else "")
        + f":\n- Recorded spend: INR {spend['total']:,.2f}\n"
        f"- Repair/facilities events: {repairs['count']}\n\n"
        "Ask specifically: spend, repairs, what needs replacing, or who did what on a case."
    )
    return AdminAnswer(reply=reply, grounded=True, data={"spend": spend, "repairs": repairs})


def should_investigate(category: str) -> bool:
    return (category or "").lower() in FACILITIES_CATS
