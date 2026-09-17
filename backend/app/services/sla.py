"""SLA clocks — escalate overdue tasks and mark outcomes AT_RISK."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from app.audit.service import AuditService
from app.core.enums import AuditAction, OutcomeStatus
from app.models.org import utcnow
from app.models.outcome import Outcome, Task
from app.policy.meeting_policy import load_meeting_policy


def tick_sla(session: Session, tenant_id: str) -> dict[str, Any]:
    """
    Mark overdue open tasks, escalate long-overdue ones, set outcomes AT_RISK.
    Safe to run periodically from the worker.
    """
    now = utcnow()
    policy = load_meeting_policy(session, tenant_id)
    escalate_after = timedelta(hours=int(policy.escalate_overdue_after_hours or 4))

    tasks = session.exec(
        select(Task).where(
            Task.tenant_id == tenant_id,
            Task.status.notin_(["CLOSED", "CANCELLED", "VERIFIED"]),  # type: ignore
        )
    ).all()

    overdue = 0
    escalated = 0
    at_risk = 0
    audit = AuditService(session)

    touched_outcomes: set[str] = set()
    for task in tasks:
        if not task.due_at or task.due_at >= now:
            continue
        overdue += 1
        meta = dict(task.result or {}) if isinstance(task.result, dict) else {}
        was_overdue = bool(meta.get("sla_overdue"))
        meta["sla_overdue"] = True
        meta["sla_overdue_at"] = meta.get("sla_overdue_at") or now.isoformat()
        late_for = now - task.due_at
        if late_for >= escalate_after and not meta.get("sla_escalated"):
            meta["sla_escalated"] = True
            meta["sla_escalated_at"] = now.isoformat()
            escalated += 1
            audit.record(
                tenant_id=tenant_id,
                actor="system",
                action=AuditAction.TASK_BLOCKED,
                entity_type="Task",
                entity_id=task.task_id,
                after={
                    "reason": "sla_escalated",
                    "due_at": task.due_at.isoformat(),
                    "late_hours": round(late_for.total_seconds() / 3600, 2),
                },
                correlation_id=task.outcome_id,
            )
        task.result = meta
        session.add(task)
        if task.outcome_id:
            touched_outcomes.add(task.outcome_id)
        if not was_overdue:
            audit.record(
                tenant_id=tenant_id,
                actor="system",
                action=AuditAction.TASK_STATUS_CHANGED,
                entity_type="Task",
                entity_id=task.task_id,
                after={"sla_overdue": True, "due_at": task.due_at.isoformat()},
                correlation_id=task.outcome_id,
            )

    for oid in touched_outcomes:
        outcome = session.get(Outcome, oid)
        if not outcome or outcome.status in {OutcomeStatus.CLOSED.value, OutcomeStatus.CANCELLED.value}:
            continue
        if outcome.status != OutcomeStatus.AT_RISK.value:
            outcome.status = OutcomeStatus.AT_RISK.value
            session.add(outcome)
            at_risk += 1
            facts = dict(outcome.facts or {})
            facts["sla_at_risk"] = True
            facts["sla_ticked_at"] = now.isoformat()
            outcome.facts = facts
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(outcome, "facts")

    session.commit()
    return {
        "overdue_tasks": overdue,
        "escalated_tasks": escalated,
        "outcomes_marked_at_risk": at_risk,
        "policy_version": policy.version,
    }
