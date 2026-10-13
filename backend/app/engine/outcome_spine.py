"""Canonical Outcome spine helpers — shared by desk and meeting/invoice paths.

DOCX §2.1 / §29: one Event → Outcome → Requirement → Task → Evidence model.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlmodel import Session, select

from app.engines.evidence import EvidenceEngine
from app.engines.sla import SlaEngine
from app.models.outcome import Evidence, Outcome, Requirement, Task, utcnow
from app.models.org import OutcomeTemplate


def ensure_requirement(
    session: Session,
    *,
    tenant_id: str,
    outcome: Outcome,
    code: str,
    title: str,
    mandatory: bool = True,
    evidence_required: bool = False,
) -> Requirement:
    existing = session.exec(
        select(Requirement).where(
            Requirement.outcome_id == outcome.outcome_id,
            Requirement.code == code,
        )
    ).first()
    if existing:
        return existing
    row = Requirement(
        tenant_id=tenant_id,
        outcome_id=outcome.outcome_id,
        code=code,
        title=title,
        is_mandatory=mandatory,
        evidence_required=evidence_required,
        status="REQUIRED",
    )
    session.add(row)
    session.flush()
    return row


def ensure_task(
    session: Session,
    *,
    tenant_id: str,
    outcome: Outcome,
    code: str,
    title: str,
    owner_role: Optional[str] = None,
    evidence_required: bool = False,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> Task:
    existing = session.exec(
        select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == code)
    ).first()
    if existing:
        return existing
    sla = SlaEngine(session, tenant_id).target_for(
        category=category or outcome.category,
        priority=priority or outcome.priority or "MEDIUM",
    )
    row = Task(
        tenant_id=tenant_id,
        outcome_id=outcome.outcome_id,
        requirement_id=requirement_id,
        code=code,
        title=title,
        owner_role=owner_role,
        evidence_required=evidence_required,
        sla_hours=int(sla.resolution_hours),
        due_at=sla.due_at,
        status="NOT_STARTED",
    )
    session.add(row)
    session.flush()
    return row


def materialize_template_spine(
    session: Session,
    *,
    tenant_id: str,
    outcome: Outcome,
    template_code: Optional[str] = None,
) -> dict[str, int]:
    """Idempotently ensure Requirement/Task rows exist for the outcome's template.

    Safe when OutcomeEngine already created rows — ensure_* no-ops on duplicates.
    """
    code = (template_code or outcome.template_code or "").strip()
    if not code:
        return {"requirements": 0, "tasks": 0}
    template = session.exec(
        select(OutcomeTemplate).where(
            OutcomeTemplate.tenant_id == tenant_id,
            OutcomeTemplate.code == code,
            OutcomeTemplate.is_active == True,  # noqa: E712
        )
    ).first()
    req_n = task_n = 0
    if template:
        for req in template.requirements or []:
            if isinstance(req, dict):
                rcode = str(req.get("code") or req.get("id") or "").strip()
                title = str(req.get("title") or req.get("name") or rcode)
                if not rcode:
                    continue
                ensure_requirement(
                    session,
                    tenant_id=tenant_id,
                    outcome=outcome,
                    code=rcode,
                    title=title,
                    mandatory=bool(req.get("mandatory", req.get("is_mandatory", True))),
                    evidence_required=bool(req.get("evidence_required", False)),
                )
                req_n += 1
        for task in template.tasks or []:
            if isinstance(task, dict):
                tcode = str(task.get("code") or task.get("id") or "").strip()
                title = str(task.get("title") or task.get("name") or tcode)
                if not tcode:
                    continue
                ensure_task(
                    session,
                    tenant_id=tenant_id,
                    outcome=outcome,
                    code=tcode,
                    title=title,
                    owner_role=task.get("owner_role"),
                    evidence_required=bool(task.get("evidence_required", False)),
                    category=outcome.category,
                    priority=outcome.priority,
                )
                task_n += 1
    # Always stamp spine marker for audit / control tower
    facts = dict(outcome.facts or {})
    if not facts.get("unified_spine"):
        facts["unified_spine"] = True
        facts["spine_template"] = code
        outcome.facts = facts
        outcome.updated_at = utcnow()
        session.add(outcome)
    return {"requirements": req_n, "tasks": task_n}


def materialize_service_request(
    session: Session,
    *,
    tenant_id: str,
    outcome: Outcome,
    category: str,
    evidence_hint: Optional[str] = None,
    owner_role: Optional[str] = None,
    task_titles: Optional[Sequence[str]] = None,
) -> dict[str, int]:
    """Create the standard desk SERVICE_REQUEST Requirement + work Task(s)."""
    req = ensure_requirement(
        session,
        tenant_id=tenant_id,
        outcome=outcome,
        code="FULFIL",
        title=f"Fulfil {category.replace('_', ' ')} request",
        mandatory=True,
        evidence_required=bool(evidence_hint),
    )
    titles = list(task_titles or []) or [f"Execute {category.replace('_', ' ')}"]
    n = 0
    for i, title in enumerate(titles[:8]):
        code = "WO" if i == 0 else f"WO{i+1}"
        ensure_task(
            session,
            tenant_id=tenant_id,
            outcome=outcome,
            code=code,
            title=str(title)[:200],
            owner_role=owner_role,
            evidence_required=bool(evidence_hint) and i == 0,
            category=category,
            priority=outcome.priority,
            requirement_id=req.requirement_id,
        )
        n += 1
    facts = dict(outcome.facts or {})
    facts["unified_spine"] = True
    if evidence_hint:
        facts["evidence_hint"] = evidence_hint
    outcome.facts = facts
    outcome.updated_at = utcnow()
    session.add(outcome)
    return {"requirements": 1, "tasks": n}


def ensure_evidence(
    session: Session,
    *,
    tenant_id: str,
    outcome: Outcome,
    evidence_type: str,
    description: Optional[str] = None,
    task_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    status: str = "SUBMITTED",
    submitted_by: Optional[str] = None,
) -> Evidence:
    row = Evidence(
        tenant_id=tenant_id,
        outcome_id=outcome.outcome_id,
        task_id=task_id,
        requirement_id=requirement_id,
        evidence_type=evidence_type,
        description=description,
        status=status,
        submitted_by=submitted_by,
    )
    session.add(row)
    session.flush()
    return row


def can_verify_close(session: Session, tenant_id: str, outcome_id: str) -> dict[str, Any]:
    gate = EvidenceEngine(session, tenant_id).gate_for_outcome(outcome_id)
    return {
        "can_verify_close": gate.can_verify_close,
        "missing": gate.missing,
        "reason": gate.reason,
    }


def mark_verified_closed(
    session: Session,
    tenant_id: str,
    outcome: Outcome,
    *,
    force: bool = False,
) -> dict[str, Any]:
    gate = can_verify_close(session, tenant_id, outcome.outcome_id)
    if not gate["can_verify_close"] and not force:
        return {"ok": False, **gate}
    outcome.status = "VERIFIED_CLOSED"
    outcome.verified_at = utcnow()
    outcome.closed_at = outcome.closed_at or utcnow()
    outcome.updated_at = utcnow()
    session.add(outcome)
    session.commit()
    return {"ok": True, **gate, "outcome_id": outcome.outcome_id}
