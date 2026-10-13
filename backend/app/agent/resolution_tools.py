"""Allowlisted read tools for the Operations Resolution Agent (no raw SQL)."""

from __future__ import annotations

import re
from typing import Any, Optional

from sqlmodel import Session, col, select

from app.agent.directory import route_for
from app.models.company import KnowledgeEntry
from app.models.org import StockSku, Vendor
from app.models.outcome import Outcome
from app.services.ops_ledger import (
    query_events,
    repairs_summary,
    spend_summary,
    who_did_what,
)

FACILITIES_CATS = frozenset(
    {"maintenance", "hvac", "electrical", "plumbing", "furniture", "pest_control", "waste_disposal", "health_safety"}
)

_CLOSED = frozenset({"CLOSED", "CANCELLED", "ADMINISTRATIVELY_CLOSED", "RESOLVED"})


def find_open_cases_for_location_resource(
    session: Session,
    tenant_id: str,
    *,
    location_id: Optional[str],
    text: str,
    category: Optional[str] = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    q = select(Outcome).where(Outcome.tenant_id == tenant_id)
    rows = list(session.exec(q.order_by(col(Outcome.created_at).desc()).limit(80)).all())
    tokens = [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) >= 3][:12]
    out = []
    for o in rows:
        facts = o.facts or {}
        stage = str(facts.get("agent_stage") or o.status or "")
        if stage in _CLOSED or o.status in _CLOSED:
            continue
        cat = (facts.get("agent_category") or o.category or "").lower()
        if category and cat and cat != category.lower() and cat not in FACILITIES_CATS:
            continue
        if location_id and facts.get("location_id") and facts.get("location_id") != location_id:
            continue
        blob = f"{o.title}\n{o.summary}\n{facts.get('raw_request') or ''}\n{facts.get('details') or ''}".lower()
        score = sum(1 for t in tokens if t in blob)
        if score < 1 and not (category and cat == category.lower()):
            continue
        out.append(
            {
                "case_reference": o.case_reference,
                "title": o.title,
                "stage": stage,
                "category": cat,
                "priority": o.priority,
                "score": score,
                "department_code": facts.get("department_code"),
            }
        )
        if len(out) >= limit:
            break
    return sorted(out, key=lambda x: -x["score"])


def case_history_summary(
    session: Session,
    tenant_id: str,
    *,
    location_id: Optional[str],
    category: Optional[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = query_events(
        session,
        tenant_id,
        event_types=["TEAM_DONE", "CLOSED", "VENDOR_ASSIGNED", "WORK_ORDER_SENT"],
        location_id=location_id,
        category=category,
        days=90,
        limit=limit,
    )
    return [
        {
            "when": r.occurred_at.isoformat(),
            "case": r.case_reference,
            "type": r.event_type,
            "summary": r.summary,
            "actor": r.actor_email,
            "amount": r.amount,
        }
        for r in rows
    ]


def search_knowledge(session: Session, tenant_id: str, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    rows = session.exec(
        select(KnowledgeEntry).where(
            KnowledgeEntry.tenant_id == tenant_id,
            KnowledgeEntry.is_active == True,  # noqa: E712
        )
    ).all()
    scored = []
    for r in rows:
        blob = f"{r.title}\n{r.content}\n{r.section}".lower()
        score = sum(1 for t in re.split(r"[^a-z0-9]+", q) if len(t) >= 3 and t in blob)
        if score:
            scored.append({"key": r.key, "title": r.title, "section": r.section, "content": (r.content or "")[:600], "score": score})
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def list_approved_vendors(
    session: Session,
    tenant_id: str,
    *,
    category: Optional[str] = None,
    location: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    from app.services.vendor_lifecycle import vendors_for_location

    rows = vendors_for_location(
        session, tenant_id, location_id=location_id, category=None
    )
    out = []
    for v in rows:
        cat = (v.category or "").lower()
        if category and category.lower() not in cat and cat not in {
            (category or "").lower(),
            "hvac",
            "maintenance",
            "facilities",
        }:
            services = " ".join(v.approved_services or []).lower()
            if category and category.lower() not in services:
                continue
        if location and v.location and location.lower() not in (v.location or "").lower():
            continue
        out.append(
            {
                "vendor_id": v.vendor_id,
                "name": v.name,
                "category": v.category,
                "email": v.contact_email,
                "location": v.location,
                "score": v.score,
                "coverage_cities": (v.coverage_cities or [])[:8],
            }
        )
        if len(out) >= limit:
            break
    return out


def team_route_info(session: Session, tenant_id: str, category: str, location_id: Optional[str]) -> dict[str, Any]:
    route = route_for(session, tenant_id, category, location_id)
    return {
        "department_code": route.department_code,
        "department_name": route.department_name,
        "recipients": list(route.recipients),
        "sla_hours": route.sla_hours,
        "redirected_to_admin": route.redirected_to_admin,
    }


def work_order_status(session: Session, tenant_id: str, outcome_id: str) -> dict[str, Any]:
    o = session.get(Outcome, outcome_id)
    if not o or o.tenant_id != tenant_id:
        return {"found": False}
    facts = o.facts or {}
    return {
        "found": True,
        "case_reference": o.case_reference,
        "stage": facts.get("agent_stage"),
        "status": o.status,
        "priority": o.priority,
        "department_code": facts.get("department_code"),
        "dispatched_at": facts.get("dispatched_at"),
        "sla_reminded_at": facts.get("sla_reminded_at"),
        "sla_escalated_at": facts.get("sla_escalated_at"),
        "progress_note": facts.get("progress_note"),
        "resolution_note": facts.get("resolution_note"),
    }


def replace_due(session: Session, tenant_id: str) -> dict[str, Any]:
    low_stock = []
    for sku in session.exec(
        select(StockSku).where(StockSku.tenant_id == tenant_id, StockSku.status == "ACTIVE")
    ).all():
        if float(sku.reorder_min or 0) > 0 and float(sku.qty_on_hand or 0) <= float(sku.reorder_min):
            low_stock.append(
                {
                    "sku_code": sku.sku_code,
                    "name": sku.name,
                    "qty_on_hand": sku.qty_on_hand,
                    "reorder_min": sku.reorder_min,
                    "location_id": sku.location_id,
                }
            )
    # Assets needing attention from recent ledger
    asset_rows = query_events(
        session,
        tenant_id,
        event_types=["ASSET_ISSUE", "ASSET_RETURN", "TEAM_DONE"],
        days=60,
        limit=50,
    )
    assets = [
        {"when": r.occurred_at.isoformat(), "tag": r.asset_tag, "summary": r.summary, "case": r.case_reference}
        for r in asset_rows
        if r.asset_tag or "replace" in (r.summary or "").lower() or "damaged" in (r.summary or "").lower()
    ]
    return {"low_stock": low_stock[:30], "assets_attention": assets[:30]}


TOOL_HANDLERS = {
    "find_open_cases_for_location_resource": find_open_cases_for_location_resource,
    "case_history_summary": case_history_summary,
    "search_knowledge": search_knowledge,
    "list_approved_vendors": list_approved_vendors,
    "team_route_info": team_route_info,
    "work_order_status": work_order_status,
    "ledger_spend": lambda session, tenant_id, **kw: spend_summary(session, tenant_id, **kw),
    "ledger_repairs": lambda session, tenant_id, **kw: repairs_summary(session, tenant_id, **kw),
    "ledger_who_did_what": lambda session, tenant_id, **kw: who_did_what(session, tenant_id, **kw),
    "ledger_replace_due": lambda session, tenant_id, **kw: replace_due(session, tenant_id),
}


def run_tool(session: Session, tenant_id: str, name: str, arguments: Optional[dict] = None) -> Any:
    fn = TOOL_HANDLERS.get(name)
    if not fn:
        return {"error": f"unknown_tool:{name}"}
    args = dict(arguments or {})
    args.pop("tenant_id", None)
    try:
        return fn(session, tenant_id, **args)
    except TypeError as exc:
        return {"error": f"bad_args:{exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}
