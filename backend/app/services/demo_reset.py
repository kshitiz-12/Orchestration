"""Demo data reset — clear operational case data; keep masters/seed."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models.intake import (
    AIDecision,
    Conversation,
    DownstreamAction,
    HumanReviewItem,
    ProcessingJob,
    RawEmailEvent,
)
from app.models.org import Invoice, PurchaseOrder, Receipt, Resource
from app.models.outcome import (
    Approval,
    AuditLog,
    Communication,
    Evidence,
    ExceptionRecord,
    Outcome,
    Requirement,
    Task,
    TaskDependency,
    VendorIssue,
)


def reset_demo_operational_data(session: Session, tenant_id: str) -> dict[str, Any]:
    """Wipe emails/outcomes/reviews/jobs for a clean demo; keep org masters."""
    counts: dict[str, int] = {}

    task_ids = {
        t.task_id for t in session.exec(select(Task).where(Task.tenant_id == tenant_id)).all()
    }
    n_deps = 0
    for dep in session.exec(select(TaskDependency)).all():
        if dep.task_id in task_ids or dep.depends_on_task_id in task_ids:
            session.delete(dep)
            n_deps += 1
    counts["task_dependencies"] = n_deps

    def _delete(model) -> int:
        rows = session.exec(select(model).where(model.tenant_id == tenant_id)).all()
        for row in rows:
            session.delete(row)
        counts[getattr(model, "__tablename__", model.__name__)] = len(rows)
        return len(rows)

    for model in (
        Communication,
        Evidence,
        Approval,
        ExceptionRecord,
        Task,
        Requirement,
        VendorIssue,
        DownstreamAction,
        HumanReviewItem,
        AIDecision,
        ProcessingJob,
        AuditLog,
        Invoice,
        Receipt,
        PurchaseOrder,
        Outcome,
        RawEmailEvent,
        Conversation,
    ):
        _delete(model)

    rooms = session.exec(
        select(Resource).where(
            Resource.tenant_id == tenant_id,
            Resource.type.in_(["MEETING_ROOM", "PARKING_SLOT"]),  # type: ignore
        )
    ).all()
    freed = 0
    for room in rooms:
        attrs = dict(room.attributes or {})
        changed = False
        if attrs.pop("booking", None) is not None:
            changed = True
        if attrs.pop("outcome_id", None) is not None:
            changed = True
        if room.status != "AVAILABLE":
            room.status = "AVAILABLE"
            changed = True
        if changed:
            room.attributes = attrs
            session.add(room)
            freed += 1
    counts["resources_freed"] = freed

    session.commit()
    return {"tenant_id": tenant_id, "deleted": counts}
