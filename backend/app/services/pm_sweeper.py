"""PM due → Outcome/WO generation (M06 production loop)."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.agent.directory import route_for
from app.core.enums import CommunicationType, OutcomeStatus
from app.core.logging import get_logger
from app.engine.outcome_engine import OutcomeEngine
from app.engine.outcome_spine import materialize_service_request
from app.models.facilities import PreventiveSchedule
from app.models.org import utcnow
from app.models.outcome import Outcome
from app.services.communication import CommunicationService

logger = get_logger(__name__)


def sweep_preventive_maintenance(session: Session, tenant_id: str) -> dict[str, Any]:
    """Create desk-style outcomes for overdue ACTIVE PM schedules (once per due cycle)."""
    now = utcnow()
    rows = session.exec(
        select(PreventiveSchedule).where(
            PreventiveSchedule.tenant_id == tenant_id,
            PreventiveSchedule.status == "ACTIVE",
        )
    ).all()
    created = 0
    skipped = 0
    for sched in rows:
        if not sched.next_due_at or sched.next_due_at > now:
            continue
        # Avoid duplicate open PM outcomes for same schedule
        marker = f"pm:{sched.schedule_id}:{sched.next_due_at.date().isoformat()}"
        existing = session.exec(
            select(Outcome).where(
                Outcome.tenant_id == tenant_id,
                Outcome.status.notin_(["CLOSED", "CANCELLED", "VERIFIED_CLOSED"]),
            )
        ).all()
        if any((o.facts or {}).get("pm_marker") == marker for o in existing):
            skipped += 1
            continue

        engine = OutcomeEngine(session, tenant_id)
        ref = engine.next_case_reference("PM")
        route = route_for(session, tenant_id, "maintenance", sched.location_id)
        outcome = Outcome(
            tenant_id=tenant_id,
            case_reference=ref,
            template_code="SERVICE_REQUEST",
            category="MAINTENANCE",
            title=f"PM due: {sched.title}",
            summary=f"Preventive maintenance due for schedule {sched.schedule_id}",
            status=OutcomeStatus.ACTIVE.value,
            priority="MEDIUM",
            facts={
                "agent_case": True,
                "agent_category": "maintenance",
                "category_label": "Preventive maintenance",
                "agent_stage": "DISPATCHED",
                "pm_schedule_id": sched.schedule_id,
                "pm_marker": marker,
                "asset_id": sched.asset_id,
                "location_id": sched.location_id,
                "checklist": sched.checklist or [],
                "department_code": route.department_code,
                "department_name": route.department_name,
                "unified_spine": True,
            },
            due_at=sched.next_due_at,
        )
        session.add(outcome)
        session.flush()
        materialize_service_request(
            session,
            tenant_id=tenant_id,
            outcome=outcome,
            category="maintenance",
            evidence_hint="PM checklist completed / photo",
            owner_role=route.department_code or "FACILITIES",
            task_titles=[f"Complete PM: {sched.title}"],
        )
        if route.recipients:
            try:
                CommunicationService(session, tenant_id).send_case_update(
                    outcome=outcome,
                    communication_type=CommunicationType.ACTION_REQUIRED.value,
                    body=(
                        f"Preventive maintenance is due.\n\n"
                        f"Case: {ref}\n"
                        f"Schedule: {sched.title}\n"
                        f"Checklist: {sched.checklist or []}\n"
                        f'Reply "done" with completion evidence when finished.'
                    ),
                    recipients=list(route.recipients),
                    action_label="PM WORK ORDER",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("pm_wo_mail_failed", error=str(exc), schedule_id=sched.schedule_id)
        created += 1
    if created:
        session.commit()
    return {"created": created, "skipped": skipped, "checked": len(rows)}
