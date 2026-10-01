"""Time-driven follow-up for service requests, the way a good admin keeps a register:

- dispatched work: one reminder to the team part-way through the SLA, one escalation to the admin at breach
- pending approval: one reminder to the approver
- waiting on the requester: one nudge, then close politely if they never answer
- resolved: closes on its own after a quiet period (the requester was told and can reply "not fixed")

Every step fires at most once per case (timestamps in facts), so the sweep is safe to run every few minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.enums import CommunicationType, OutcomeStatus
from app.core.logging import get_logger
from app.models.org import utcnow
from app.models.outcome import Outcome
from app.services.communication import CommunicationService

logger = get_logger(__name__)

_OPEN = {OutcomeStatus.ACTIVE.value, OutcomeStatus.AT_RISK.value, OutcomeStatus.BLOCKED.value}
_WORKING = {"DISPATCHED", "IN_PROGRESS", "BLOCKED"}
# Share of the SLA after which the team gets its one reminder (tighter for urgent work).
_REMIND_AT = {"URGENT": 0.5, "HIGH": 0.5, "MEDIUM": 0.75, "LOW": 0.75}


def _ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def sweep_desk_cases(
    session: Session,
    tenant_id: str,
    *,
    now: Optional[datetime] = None,
    comms: Optional[CommunicationService] = None,
) -> dict[str, int]:
    from app.agent.desk import SERVICE_TEMPLATE, AdminDesk, _set_facts
    from app.agent.directory import route_for_case

    now = now or utcnow()
    settings = get_settings()
    if comms is None:
        from app.services.approval_actions import default_comms

        comms = default_comms(session, tenant_id)
    desk = AdminDesk(session, tenant_id, comms)
    counts = {"reminded": 0, "escalated": 0, "approval_reminders": 0, "nudged": 0, "closed_no_reply": 0, "auto_closed": 0}
    rows = session.exec(
        select(Outcome).where(Outcome.tenant_id == tenant_id, Outcome.template_code == SERVICE_TEMPLATE)
    ).all()
    for outcome in rows:
        facts = outcome.facts or {}
        stage = facts.get("agent_stage")
        try:
            if stage in _WORKING and outcome.status in _OPEN:
                counts_delta = _sla_followups(desk, outcome, facts, now, route_for_case, _set_facts)
                for k, v in counts_delta.items():
                    counts[k] += v
            elif stage == "AWAITING_APPROVAL" and outcome.status in _OPEN:
                asked = _ts(facts.get("approval_requested_at")) or outcome.updated_at or outcome.created_at
                hours = float(settings.desk_approval_reminder_hours or 8)
                if not facts.get("approval_reminded_at") and asked and now - asked >= timedelta(hours=hours):
                    route = route_for_case(session, tenant_id, facts)
                    outcome.status = OutcomeStatus.AT_RISK.value
                    session.add(outcome)
                    desk._notify_admin(outcome, kind="decision",
                                       headline=f"Reminder - still waiting for your approval ({facts.get('decision_reason') or 'sign-off'})",
                                       route=route)
                    _set_facts(session, outcome, approval_reminded_at=now.isoformat())
                    counts["approval_reminders"] += 1
            elif stage == "AWAITING_INFO" and outcome.status in _OPEN:
                asked = _ts(facts.get("info_requested_at")) or outcome.created_at
                if not asked:
                    continue
                waited = now - asked
                if not facts.get("info_nudged_at") and waited >= timedelta(hours=float(settings.desk_info_nudge_hours or 24)):
                    missing = facts.get("missing") or []
                    desk._tell_requester(
                        outcome,
                        f"Just checking in on {outcome.case_reference} ({outcome.title}) - I still need:\n"
                        + "\n".join(f"- {q}" for q in missing)
                        + "\n\nReply here and I'll take it forward straight away.",
                    )
                    _set_facts(session, outcome, info_nudged_at=now.isoformat())
                    counts["nudged"] += 1
                elif facts.get("info_nudged_at") and waited >= timedelta(hours=float(settings.desk_info_close_hours or 96)):
                    outcome.status = OutcomeStatus.CANCELLED.value
                    outcome.closed_at = now
                    session.add(outcome)
                    _set_facts(session, outcome, agent_stage="CLOSED_NO_REPLY",
                               resolution_note="Closed - requester did not send the details")
                    desk._ticket_status(outcome, "CLOSED")
                    desk.record_closure(outcome, "requester_non_response")
                    desk._tell_requester(
                        outcome,
                        f"I haven't heard back on {outcome.case_reference} ({outcome.title}), so I've closed it for now. "
                        "Just reply here whenever you're ready and I'll pick it up again.",
                    )
                    counts["closed_no_reply"] += 1
            elif stage == "RESOLVED" and outcome.status == OutcomeStatus.RESOLVED.value:
                resolved = _ts(facts.get("resolved_at")) or outcome.updated_at
                if resolved and now - resolved >= timedelta(hours=float(settings.desk_autoclose_hours or 72)):
                    desk.auto_close_resolved(outcome)
                    counts["auto_closed"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("desk_sweep_case_failed", outcome_id=outcome.outcome_id, error=str(exc))
    session.commit()
    return counts


def _sla_followups(desk, outcome: Outcome, facts: dict, now: datetime, route_for_case, set_facts) -> dict[str, int]:
    out = {"reminded": 0, "escalated": 0}
    due = outcome.due_at
    start = _ts(facts.get("dispatched_at")) or outcome.created_at
    if not due or not start or due <= start:
        return out
    route = route_for_case(desk.session, desk.tenant_id, facts)
    share = _REMIND_AT.get(outcome.priority or "MEDIUM", 0.75)
    remind_at = start + (due - start) * share
    if now >= due and not facts.get("sla_escalated_at"):
        outcome.status = OutcomeStatus.AT_RISK.value
        desk.session.add(outcome)
        set_facts(desk.session, outcome, sla_escalated_at=now.isoformat(), sla_breached=True)
        overdue_h = max(0.0, (now - due).total_seconds() / 3600)
        desk._notify_admin(
            outcome, kind="escalation",
            headline=f"SLA missed - {route.department_name} has not closed this"
            + (f" ({overdue_h:.0f}h overdue)" if overdue_h >= 1 else ""),
        )
        out["escalated"] = 1
        return out
    if now >= remind_at and not facts.get("sla_reminded_at") and not facts.get("sla_escalated_at"):
        set_facts(desk.session, outcome, sla_reminded_at=now.isoformat())
        if route.recipients and not route.redirected_to_admin:
            from app.engine.event_services import fmt_local

            body = desk._briefing(
                outcome,
                f"Reminder - due by {fmt_local(due + timedelta(hours=5, minutes=30))}. "
                'Reply "on it", "issue: <what is blocking>" or "done".',
                kind="work",
            )
            desk.comms.send_case_update(
                outcome=outcome,
                communication_type=CommunicationType.ACTION_REQUIRED.value,
                body=body,
                recipients=route.recipients,
                action_label="REMINDER",
                subject_hint="Due soon",
                suppress_fingerprint=f"sla_remind:{outcome.outcome_id}:{facts.get('dispatched_at')}",
            )
            out["reminded"] = 1
    return out
