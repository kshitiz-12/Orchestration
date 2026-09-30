"""Periodic sweep: remind requesters about held rooms, release holds that lapse."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.org import RoomBooking, utcnow
from app.models.outcome import Outcome
from app.services.communication import CommunicationService, resolve_requester_name
from app.services.no_resource_flow import format_outbound_greeting

logger = get_logger(__name__)

_IST = timedelta(hours=5, minutes=30)


def format_local(ts: Optional[datetime]) -> str:
    if not ts:
        return "—"
    return (ts + _IST).strftime("%d %b, %I:%M %p IST").lstrip("0")


def _comms(session: Session, tenant_id: str) -> CommunicationService:
    from app.connectors.factory import get_email_provider

    email = get_email_provider(session, tenant_id)
    return CommunicationService(session, tenant_id, email_sender=email if email.is_connected() else None)


def sweep_proposal_holds(
    session: Session,
    tenant_id: str,
    *,
    now: Optional[datetime] = None,
    comms: Optional[CommunicationService] = None,
) -> dict[str, Any]:
    now = now or utcnow()
    settings = get_settings()
    remind_after = timedelta(hours=float(settings.proposal_reminder_hours or 12))
    comms = comms or _comms(session, tenant_id)

    held = session.exec(
        select(RoomBooking).where(RoomBooking.tenant_id == tenant_id, RoomBooking.status == "HELD")
    ).all()
    reminded = expired = superseded = 0
    for booking in held:
        outcome = session.get(Outcome, booking.outcome_id) if booking.outcome_id else None
        facts = dict(outcome.facts or {}) if outcome else {}
        provisional = facts.get("provisional_hold") or {}
        if outcome and provisional.get("booking_id") == booking.booking_id:
            # Held while the requester answers the remaining questions: lapse quietly, no reminders
            if outcome.status in {"CANCELLED", "CLOSED"} or (booking.hold_expires_at and booking.hold_expires_at <= now):
                booking.status = "EXPIRED"
                session.add(booking)
                facts.pop("provisional_hold", None)
                outcome.facts = facts
                session.add(outcome)
                flag_modified(outcome, "facts")
                expired += 1
            continue
        proposal = facts.get("proposed_room") or {}
        proposal_ids = (
            {proposal.get("booking_id")}
            | {r.get("booking_id") for r in proposal.get("rooms") or []}
            | set(proposal.get("extra_day_booking_ids") or [])
        )
        proposal_ids.discard(None)
        still_proposed = bool(
            outcome
            and outcome.status not in {"CANCELLED", "CLOSED"}
            and facts.get("pending_confirmation")
            and not facts.get("booked_room")
            and (not proposal_ids or booking.booking_id in proposal_ids)
        )
        if not still_proposed:
            booking.status = "RELEASED"
            session.add(booking)
            superseded += 1
            continue
        label = proposal.get("name") or booking.room_name
        group = proposal.get("booking_id") or booking.booking_id

        extra_day = booking.booking_id in set(proposal.get("extra_day_booking_ids") or [])
        if booking.hold_expires_at and booking.hold_expires_at <= now:
            booking.status = "EXPIRED"
            session.add(booking)
            if extra_day:
                expired += 1
                continue
            facts["proposed_room"] = {**proposal, "hold_expired": True}
            facts["last_action"] = "proposal_hold_expired"
            outcome.facts = facts
            session.add(outcome)
            flag_modified(outcome, "facts")
            _mail(
                comms,
                session,
                outcome,
                label="HOLD RELEASED",
                lines=[
                    f"We held {label} for you but didn't hear back, so the hold has been released.",
                    'Reply "confirm" and we\'ll book it if it\'s still free (or offer the next best room), '
                    "or tell us what to change.",
                ],
                fingerprint=f"hold_expired:{group}",
            )
            expired += 1
            continue

        if extra_day:
            continue
        if not booking.reminder_sent_at and booking.created_at + remind_after <= now:
            booking.reminder_sent_at = now
            session.add(booking)
            _mail(
                comms,
                session,
                outcome,
                label="REMINDER",
                lines=[
                    f"{label} is still held for you until {format_local(booking.hold_expires_at)}.",
                    'Reply "confirm" to lock it in, or tell us what to change.',
                ],
                fingerprint=f"hold_reminder:{group}",
            )
            reminded += 1

    session.commit()
    result = {"reminded": reminded, "expired": expired, "superseded": superseded}
    if reminded or expired:
        logger.info("hold_sweep", **result)
    return result


def _mail(
    comms: CommunicationService,
    session: Session,
    outcome: Outcome,
    *,
    label: str,
    lines: list[str],
    fingerprint: str,
) -> None:
    if not outcome.requester_email:
        return
    name = resolve_requester_name(session, outcome=outcome)
    comms.send_case_update(
        outcome=outcome,
        communication_type="ACTION_REQUIRED",
        body=f"{format_outbound_greeting(name)}\n\n" + "\n\n".join(lines) + f"\n\nCase: {outcome.case_reference}",
        recipients=[outcome.requester_email],
        action_label=label,
        subject_hint=outcome.summary or label.title(),
        suppress_fingerprint=fingerprint,
    )


def run_all_sweeps(session: Session, tenant_id: str) -> dict[str, Any]:
    from app.services.sla import tick_sla

    out: dict[str, Any] = {}
    try:
        out["holds"] = sweep_proposal_holds(session, tenant_id)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("hold_sweep_failed", error=str(exc))
    try:
        from app.engine.event_services import sweep_event_followups

        out["events"] = sweep_event_followups(session, tenant_id)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("event_followups_failed", error=str(exc))
    try:
        out["sla"] = tick_sla(session, tenant_id)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("sla_tick_failed", error=str(exc))
    try:
        from app.agent.digest import send_admin_digest

        out["digest"] = send_admin_digest(session, tenant_id)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("admin_digest_failed", error=str(exc))
    return out
