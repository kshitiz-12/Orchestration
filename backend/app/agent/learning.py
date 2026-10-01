"""Verified organisational memory (blueprint 18): what the AI planned, what people corrected, how it really ended.

Only verified closures become precedent for the AI; everything else is kept for audit and correction trends.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.models.company import LearningRecord
from app.models.org import utcnow
from app.models.outcome import Outcome

logger = get_logger(__name__)

VERIFIED_CLOSURES = {"verified_by_requester", "verified_evidence"}
CLOSURE_LABELS = {
    "verified_by_requester": "Verified - requester confirmed",
    "verified_evidence": "Verified - completion evidence on file",
    "closed_without_evidence": "Closed - no completion evidence",
    "administrative": "Administrative closure",
    "requester_non_response": "Closed - requester did not reply",
    "cancelled": "Cancelled",
    "rejected": "Not approved / unable to proceed",
}

_STOP = {
    "please", "need", "needs", "with", "from", "that", "this", "have", "there", "about", "would", "could", "kindly",
    "team", "admin", "thanks", "thank", "regards", "hello", "today", "tomorrow", "office", "floor", "request",
}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _STOP}


def _ts(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def add_correction(session: Session, outcome: Outcome, kind: str, by: str, **data: Any) -> None:
    from app.agent.desk import _set_facts

    corrections = list((outcome.facts or {}).get("corrections") or [])
    corrections.append({"kind": kind, "by": by, "at": utcnow().isoformat(), **data})
    _set_facts(session, outcome, corrections=corrections[-30:])


def record_closure(session: Session, outcome: Outcome) -> Optional[LearningRecord]:
    facts = outcome.facts or {}
    if not facts.get("agent_case"):
        return None
    closure = facts.get("closure_type") or "unknown"
    verified = closure in VERIFIED_CLOSURES
    dispatched = _ts(facts.get("dispatched_at"))
    resolved = _ts(facts.get("resolved_at"))
    record = session.exec(select(LearningRecord).where(LearningRecord.outcome_id == outcome.outcome_id)).first()
    if record is None:
        record = LearningRecord(tenant_id=outcome.tenant_id, outcome_id=outcome.outcome_id, category="general")
    record.case_reference = outcome.case_reference
    record.category = facts.get("agent_category") or "general"
    record.request_text = (facts.get("raw_request") or outcome.title or "")[:2000]
    record.ai_plan = facts.get("ai_plan") or {}
    record.corrections = facts.get("corrections") or []
    record.final_plan = {
        "category": facts.get("agent_category"),
        "department": facts.get("department_code"),
        "priority": outcome.priority,
        "details": facts.get("details") or {},
        "decision_class": facts.get("decision_class"),
        "needed_approval": bool(facts.get("approval_id")),
    }
    record.execution = {
        "team": facts.get("department_name"),
        "hours_to_resolve": round((resolved - dispatched).total_seconds() / 3600, 1) if resolved and dispatched else None,
        "sla_breached": bool(facts.get("sla_breached")),
        "evidence_status": facts.get("evidence_status"),
        "resolution_note": facts.get("resolution_note"),
        "asked": (facts.get("ai_plan") or {}).get("missing") or [],
    }
    record.closure_type = closure
    record.verified = verified
    record.reopen_count = int(facts.get("reopen_count") or 0)
    record.learning_eligible = verified
    record.updated_at = utcnow()
    session.add(record)
    session.flush()
    return record


def similar_verified(session: Session, tenant_id: str, text: str, *, limit: int = 3) -> list[dict]:
    """Closest verified past cases by shared words - cheap, explainable, no embeddings needed."""
    words = _words(text)
    if not words:
        return []
    rows = session.exec(
        select(LearningRecord)
        .where(LearningRecord.tenant_id == tenant_id, LearningRecord.learning_eligible == True)  # noqa: E712
        .order_by(LearningRecord.created_at.desc())  # type: ignore[attr-defined]
        .limit(300)
    ).all()
    scored = []
    for r in rows:
        overlap = len(words & _words(r.request_text or ""))
        if overlap >= 2:
            scored.append((overlap, r))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = []
    for _, r in scored[:limit]:
        out.append({
            "request": (r.request_text or "")[:240],
            "category": r.category,
            "team": (r.execution or {}).get("team"),
            "asked_requester": (r.execution or {}).get("asked") or [],
            "needed_approval": (r.final_plan or {}).get("needed_approval"),
            "how_it_was_done": (r.execution or {}).get("resolution_note"),
            "corrected_by_humans": [c.get("kind") for c in (r.corrections or [])],
        })
    return out


def _window(session: Session, tenant_id: str, days: int) -> list[Outcome]:
    return list(session.exec(
        select(Outcome).where(
            Outcome.tenant_id == tenant_id,
            Outcome.template_code == "SERVICE_REQUEST",
            Outcome.created_at >= utcnow() - timedelta(days=days),
        )
    ).all())


def _kinds(facts: dict) -> list[str]:
    return [str(c.get("kind")) for c in facts.get("corrections") or []]


def accuracy_summary(session: Session, tenant_id: str, *, days: int = 90) -> dict:
    """How often the AI's first reading survived human review, per request type (blueprint 19: AI governance)."""
    from app.agent.playbooks import label_for

    by_type: dict[str, dict] = {}
    trend: dict[str, int] = {}
    totals = {"cases": 0, "type_ok": 0, "team_ok": 0, "priority_ok": 0, "reopened": 0, "closed": 0, "verified": 0}
    for o in _window(session, tenant_id, days):
        f = o.facts or {}
        if f.get("knowledge_gap"):
            continue
        kinds = _kinds(f)
        for k in kinds:
            trend[k] = trend.get(k, 0) + 1
        label = label_for(f.get("agent_category"))
        row = by_type.setdefault(label, {"type": label, "cases": 0, "type_ok": 0, "team_ok": 0, "priority_ok": 0,
                                         "reopened": 0, "closed": 0, "verified": 0})
        checks = {
            "type_ok": "recategorised" not in kinds,
            "team_ok": not ({"recategorised", "rerouted"} & set(kinds)),
            "priority_ok": "priority_changed" not in kinds,
            "reopened": bool(f.get("reopen_count")),
            "closed": bool(f.get("closure_type")),
            "verified": f.get("closure_type") in VERIFIED_CLOSURES,
        }
        for bucket in (row, totals):
            bucket["cases"] += 1
            for k, v in checks.items():
                bucket[k] += 1 if v else 0

    def pct(n: int, d: int) -> Optional[int]:
        return round(100 * n / d) if d else None

    def shape(r: dict) -> dict:
        return {
            **({"type": r["type"]} if "type" in r else {}),
            "cases": r["cases"],
            "type_accuracy_pct": pct(r["type_ok"], r["cases"]),
            "team_accuracy_pct": pct(r["team_ok"], r["cases"]),
            "priority_accuracy_pct": pct(r["priority_ok"], r["cases"]),
            "reopen_rate_pct": pct(r["reopened"], r["cases"]),
            "verified_closure_pct": pct(r["verified"], r["closed"]),
        }

    return {
        "window_days": days,
        "overall": shape(totals),
        "by_type": sorted((shape(r) for r in by_type.values()), key=lambda r: -r["cases"]),
        "correction_trend": sorted(({"kind": k, "count": v} for k, v in trend.items()), key=lambda r: -r["count"]),
    }


def rule_suggestions(session: Session, tenant_id: str, *, days: int = 90, threshold: int = 2) -> list[dict]:
    """Repeated human corrections become proposed rule changes for an admin to accept (blueprint 18.2)."""
    from app.agent.directory import departments
    from app.agent.playbooks import label_for
    from app.models.company import KnowledgeEntry

    names = {d.code: d.name for d in departments(session, tenant_id)}
    counters: dict[tuple, list[str]] = {}
    for o in _window(session, tenant_id, days):
        f = o.facts or {}
        cat = f.get("agent_category") or "general"
        for c in f.get("corrections") or []:
            kind = c.get("kind")
            if kind == "rerouted":
                key = ("route", c.get("category") or cat, c.get("after"))
            elif kind == "recategorised":
                key = ("type", c.get("before"), c.get("after"))
            elif kind == "priority_changed":
                key = ("priority", cat, c.get("after"))
            elif kind == "detail_changed":
                key = ("detail", cat, c.get("field"))
            else:
                continue
            counters.setdefault(key, []).append(o.case_reference)
        if f.get("reopen_count"):
            counters.setdefault(("reopen", cat, f.get("department_code")), []).append(o.case_reference)

    out: list[dict] = []
    for (kind, a, b), refs in counters.items():
        if len(refs) < threshold or not a or not b:
            continue
        refs = sorted(set(refs))
        if kind == "route":
            out.append({
                "id": f"route:{a}:{b}", "kind": "route", "count": len(refs), "cases": refs,
                "suggestion": f"Send {label_for(a)} requests to {names.get(b, b)} by default",
                "why": f"Admins moved {label_for(a)} cases to {names.get(b, b)} {len(refs)} times",
                "action": {"type": "route_category", "category": a, "department": b},
            })
        elif kind == "type":
            out.append({
                "id": f"type:{a}:{b}", "kind": "type", "count": len(refs), "cases": refs,
                "suggestion": f"Mails read as {label_for(a)} are often really {label_for(b)}",
                "why": "Admins changed the request type the same way repeatedly - review the AI instructions / aliases",
                "action": None,
            })
        elif kind == "priority":
            out.append({
                "id": f"priority:{a}:{b}", "kind": "priority", "count": len(refs), "cases": refs,
                "suggestion": f"Treat {label_for(a)} requests as {b.title()} priority",
                "why": f"Priority was changed to {b.title()} on {len(refs)} {label_for(a)} cases",
                "action": None,
            })
        elif kind == "detail":
            out.append({
                "id": f"detail:{a}:{b}", "kind": "detail", "count": len(refs), "cases": refs,
                "suggestion": f"Ask for '{b.replace('_', ' ')}' on {label_for(a)} requests",
                "why": f"Admins had to fix {b.replace('_', ' ')} by hand {len(refs)} times",
                "action": None,
            })
        elif kind == "reopen":
            out.append({
                "id": f"reopen:{a}:{b}", "kind": "quality", "count": len(refs), "cases": refs,
                "suggestion": f"Review how {names.get(b, b)} closes {label_for(a)} jobs",
                "why": f"{len(refs)} {label_for(a)} cases were reopened by requesters",
                "action": None,
            })
    drafts = session.exec(
        select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id, KnowledgeEntry.section == "draft",
                                     KnowledgeEntry.is_active == False)  # noqa: E712
    ).all()
    if drafts:
        out.append({
            "id": "knowledge_drafts", "kind": "knowledge", "count": len(drafts), "cases": [],
            "suggestion": f"Approve {len(drafts)} answer(s) so the AI can reply directly next time",
            "why": "These questions had no verified answer; an admin answered them",
            "action": None,
        })
    return sorted(out, key=lambda s: -s["count"])


def apply_route_rule(session: Session, tenant_id: str, category: str, department_code: str, actor: str) -> dict:
    """Accepting a routing suggestion edits Company setup - the same thing an admin would do by hand."""
    from app.audit.service import AuditService
    from app.models.company import Department

    rows = session.exec(select(Department).where(Department.tenant_id == tenant_id)).all()
    target = next((d for d in rows if d.code == department_code), None)
    if target is None:
        raise ValueError(f"no department {department_code}")
    moved_from = []
    for dept in rows:
        cats = [str(c) for c in dept.categories or []]
        if dept.code == department_code:
            if category not in cats:
                dept.categories = cats + [category]
        elif category in cats:
            dept.categories = [c for c in cats if c != category]
            moved_from.append(dept.code)
        session.add(dept)
    AuditService(session).record(
        tenant_id=tenant_id, actor=actor, action="AI_RULE_APPLIED", entity_type="Department",
        entity_id=target.department_id, after={"category": category, "department": department_code, "moved_from": moved_from},
    )
    session.flush()
    return {"category": category, "department": department_code, "moved_from": moved_from}


def automation_kpis(session: Session, tenant_id: str, *, days: int = 30) -> dict:
    """Blueprint 18.3: eligible repetitive steps done without a human touch / all eligible steps.

    Approvals, physical work and other accountable decisions are excluded from both sides. Each case contributes
    acknowledge, classify, route and close, plus clarify / remind when they happened; human corrections, manual
    re-assignment and manual closure count as touched steps.
    """
    since = utcnow() - timedelta(days=days)
    rows = session.exec(
        select(Outcome).where(
            Outcome.tenant_id == tenant_id,
            Outcome.template_code == "SERVICE_REQUEST",
            Outcome.created_at >= since,
        )
    ).all()
    eligible = touched = verified = closed = 0
    for o in rows:
        f = o.facts or {}
        steps = 4 + (1 if f.get("info_requested_at") else 0) + (1 if f.get("sla_reminded_at") else 0)
        human = len(f.get("corrections") or [])
        if f.get("closure_type") == "administrative":
            human += 1
        eligible += steps
        touched += min(human, steps)
        if f.get("closure_type"):
            closed += 1
            verified += 1 if f.get("closure_type") in VERIFIED_CLOSURES else 0
    rate = round(100 * (eligible - touched) / eligible) if eligible else None
    return {
        "automation_rate_pct": rate,
        "automation_window_days": days,
        "verified_closure_pct": round(100 * verified / closed) if closed else None,
    }
