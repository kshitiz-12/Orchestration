"""One place that applies an approval decision (dashboard, admin mail reply, or signed link)."""

from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session

from app.audit.service import AuditService
from app.core.enums import AuditAction
from app.core.logging import get_logger
from app.models.org import utcnow
from app.models.outcome import Approval, Outcome
from app.services.communication import CommunicationService, resolve_requester_name

logger = get_logger(__name__)

COST_APPROVAL_TYPES = ("CATERING_SPEND", "EVENT_COST")


def approval_pretty(approval_type: str, facts: Optional[dict[str, Any]] = None) -> str:
    if approval_type in COST_APPROVAL_TYPES:
        charged = ((facts or {}).get("cost_plan") or {}).get("chargeable") or []
        if charged:
            return "cost for " + ", ".join(n[:1].lower() + n[1:] for n in charged)
        return "catering spend"
    return approval_type.replace("_", " ").lower()


def default_comms(session: Session, tenant_id: str) -> CommunicationService:
    from app.connectors.factory import get_email_provider

    email = get_email_provider(session, tenant_id)
    return CommunicationService(session, tenant_id, email_sender=email if email.is_connected() else None)


def apply_decision(
    session: Session,
    tenant_id: str,
    approval: Approval,
    *,
    approved: bool,
    actor: str,
    note: str = "",
    via: str,
    comms: Optional[CommunicationService] = None,
    notify_requester: bool = True,
    approver_person_id: Optional[str] = None,
) -> Optional[Outcome]:
    """Record the decision, run the case-side effects, and tell the requester."""
    from app.engine.meeting_scenario import ClientMeetingOrchestrator
    from app.engine.outcome_engine import OutcomeEngine

    decision = "APPROVED" if approved else "REJECTED"
    approval.decision = decision
    approval.reason = note or f"{decision.title()} ({via})"
    approval.decided_at = utcnow()
    if approver_person_id:
        approval.approver_person_id = approver_person_id
    session.add(approval)
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=actor,
        action=AuditAction.APPROVAL_GRANTED if approved else AuditAction.APPROVAL_REJECTED,
        entity_type="Approval",
        entity_id=approval.approval_id,
        after={"decision": decision, "reason": approval.reason, "via": via},
        correlation_id=approval.outcome_id,
    )
    outcome = session.get(Outcome, approval.outcome_id) if approval.outcome_id else None
    if outcome is None:
        return None
    comms = comms or default_comms(session, tenant_id)
    orch = ClientMeetingOrchestrator(session, tenant_id, OutcomeEngine(session, tenant_id), comms)
    orch.on_approval_decided(outcome, approval, approved=approved, note=note)
    if via != "admin_mail":
        orch.admin_ops.notify(
            outcome,
            kind="update",
            headline=f"{approval_pretty(approval.approval_type, outcome.facts).capitalize()}: "
            f"{'approved' if approved else 'not approved'} ({via.replace('_', ' ')})",
            detail=f"Reason: {note}" if note else "",
            fingerprint=f"decided:{approval.approval_id}",
            facts=dict(outcome.facts or {}),
        )

    if notify_requester and outcome.requester_email:
        facts = dict(outcome.facts or {})
        pretty = approval_pretty(approval.approval_type, facts)
        if approved:
            lines = [f"Approved: {pretty}. We're arranging it now."]
        else:
            lines = [f"Not approved: {pretty}." + (f" Reason: {note}" if note else "")]
            if facts.get("booked_room"):
                lines.append("Your room booking and the no-cost services go ahead as planned.")
        name = resolve_requester_name(session, outcome=outcome)
        from app.services.no_resource_flow import format_outbound_greeting

        comms.send_case_update(
            outcome=outcome,
            communication_type="INFORMATION_ONLY",
            body=f"{format_outbound_greeting(name)}\n\n" + "\n\n".join(lines) + f"\n\nCase: {outcome.case_reference}",
            recipients=[outcome.requester_email],
            action_label="UPDATE",
            subject_hint=f"Cost {'approved' if approved else 'not approved'}",
            suppress_fingerprint=f"decision:{approval.approval_id}:{decision}",
        )
    logger.info("approval_decided", approval_id=approval.approval_id, decision=decision, via=via)
    return outcome
