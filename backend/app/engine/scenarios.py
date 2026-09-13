from typing import Any, Optional

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.engine.outcome_engine import OutcomeEngine
from app.models.org import Invoice, PurchaseOrder, Receipt, Resource, Vendor
from app.models.outcome import Outcome, Task
from app.schemas.ai import ExtractionResult
from app.services.communication import CommunicationService

logger = get_logger(__name__)

EVENT_TO_TEMPLATE = {
    "ONBOARDING": "ONBOARDING",
    "PARKING_CONFLICT": "PARKING_CONFLICT",
    "FURNITURE_ISSUE": "FURNITURE_ISSUE",
    "VENDOR_ESCALATION": "VENDOR_ESCALATION",
    "INVOICE": "INVOICE",
    "MEETING_ROOM": "MEETING_ROOM",
    "GENERAL": "GENERAL",
}

MEETING_ROOM_TEMPLATE = {
    "code": "MEETING_ROOM",
    "name": "Meeting room booking",
    "category": "MEETING_ROOM",
    "case_prefix": "ROOM",
    "requirements": [
        {"code": "BOOKING", "title": "Meeting room reserved for requester", "is_mandatory": True},
    ],
    "tasks": [
        {
            "code": "RESERVE_ROOM",
            "title": "Reserve meeting room (auto when available)",
            "owner_role": "OPERATOR",
            "task_group": "Ops",
            "requirement_code": "BOOKING",
        },
    ],
}

# Sensitive flags only — catering/AV/location are normal captured fields now.


def ensure_meeting_room_template(session: Session, tenant_id: str) -> None:
    """Idempotent — existing Supabase tenants won't re-run full seed."""
    from app.models.org import OutcomeTemplate

    existing = session.exec(
        select(OutcomeTemplate).where(
            OutcomeTemplate.tenant_id == tenant_id,
            OutcomeTemplate.code == "MEETING_ROOM",
        )
    ).first()
    if existing:
        return
    session.add(OutcomeTemplate(tenant_id=tenant_id, **MEETING_ROOM_TEMPLATE))
    session.flush()


def ensure_meeting_room_resources(session: Session, tenant_id: str) -> None:
    """Seed bookable meeting-room resources when an existing tenant lacks them."""
    from app.models.org import Location

    existing = session.exec(
        select(Resource).where(
            Resource.tenant_id == tenant_id,
            Resource.type == "MEETING_ROOM",
        )
    ).first()
    if existing:
        return

    locations = session.exec(
        select(Location).where(
            Location.tenant_id == tenant_id,
            Location.type == "ROOM",
        )
    ).all()
    capacities = [4, 6, 8, 10, 12, 16]
    if locations:
        for i, loc in enumerate(locations[:6]):
            session.add(
                Resource(
                    tenant_id=tenant_id,
                    type="MEETING_ROOM",
                    name=f"Meeting Room {loc.name}",
                    location_id=loc.location_id,
                    status="AVAILABLE",
                    attributes={"capacity": capacities[i % len(capacities)]},
                )
            )
    else:
        for i, cap in enumerate(capacities[:3], start=1):
            session.add(
                Resource(
                    tenant_id=tenant_id,
                    type="MEETING_ROOM",
                    name=f"Meeting Room {i}",
                    status="AVAILABLE",
                    attributes={"capacity": cap},
                )
            )
    session.flush()


class ScenarioOrchestrator:
    """Applies scenario-specific deterministic rules after AI extraction."""

    def __init__(self, session: Session, tenant_id: str, communications: Optional[CommunicationService] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.engine = OutcomeEngine(session, tenant_id)
        self.comms = communications or CommunicationService(session, tenant_id)

    def orchestrate(
        self,
        *,
        extraction: ExtractionResult,
        requester_email: str,
        conversation_id: str,
        business_event_id: str,
        context: dict[str, Any],
    ) -> Outcome:
        ensure_meeting_room_template(self.session, self.tenant_id)
        template = EVENT_TO_TEMPLATE.get(extraction.event_type, "GENERAL")
        facts = dict(extraction.entities)
        facts["issues"] = [i.model_dump() for i in extraction.issues]
        outcome = self.engine.create_outcome_from_template(
            template_code=template,
            title=extraction.summary[:200] or extraction.event_type,
            summary=extraction.summary,
            requester_email=requester_email,
            conversation_id=conversation_id,
            business_event_id=business_event_id,
            facts=facts,
            priority=extraction.recommended_priority,
        )

        if template == "ONBOARDING":
            self._scenario_a(outcome, facts, context)
        elif template == "PARKING_CONFLICT":
            self._scenario_b_parking(outcome, facts, context)
        elif template == "FURNITURE_ISSUE":
            self._scenario_b_chair(outcome, facts, context)
        elif template == "VENDOR_ESCALATION":
            self._scenario_c(outcome, extraction)
        elif template == "INVOICE":
            self._scenario_d(outcome, facts, context, extraction)
        elif template == "MEETING_ROOM":
            self._scenario_meeting_room(outcome, facts, extraction)

        self.session.commit()
        self.session.refresh(outcome)
        return outcome

    def _scenario_meeting_room(
        self,
        outcome: Outcome,
        facts: dict,
        extraction: Optional[ExtractionResult] = None,
    ) -> None:
        """Core facts → assume silence on facilities → propose → await confirm.

        Dynamic: later replies can add catering/AV/etc. before or after booking.
        """
        from app.services.meeting_room import (
            apply_meeting_room_defaults,
            meeting_room_details_complete,
            meeting_room_gaps,
            requirement_fingerprint,
        )

        ensure_meeting_room_resources(self.session, self.tenant_id)

        merged = {**(outcome.facts or {}), **facts}
        if extraction and extraction.entities:
            for key, value in extraction.entities.items():
                if value is not None and value != "":
                    merged[key] = value

        attendees = merged.get("attendees")
        when = merged.get("date")
        start = merged.get("preferred_time") or merged.get("time_window")
        duration = merged.get("duration_hours")
        end = merged.get("end_time")

        if attendees and when and (start or end or duration):
            outcome.summary = (
                f"Meeting room for {attendees} on {when}"
                + (f" at {start}" if start else "")
                + (f"–{end}" if end else "")
                + (f" ({duration}h)" if duration else "")
            )
        outcome.facts = merged
        self.session.add(outcome)

        # Already booked — still accept late add-on requests
        if merged.get("booked_room"):
            incoming = (extraction.entities if extraction else {}) or {}
            deltas = {
                k: incoming[k]
                for k in (
                    "catering",
                    "hybrid_av",
                    "special_access",
                    "location_preference",
                    "meeting_type",
                )
                if k in incoming
                and incoming.get(k) not in (None, "")
                and incoming.get(k) != (merged.get("booked_room") or {}).get(k)
            }
            if deltas:
                self._handle_post_booking_updates(outcome, {**merged, **deltas})
            return

        # Confirm path (may also include new extras in the same reply)
        confirmed = bool(
            merged.get("booking_confirmed")
            or (extraction and (extraction.entities or {}).get("booking_confirmed"))
        )
        if merged.get("pending_confirmation") and confirmed:
            merged = apply_meeting_room_defaults(merged)
            if merged.get("proposed_room"):
                # Refresh proposal snapshot with any last-minute extras
                proposed = dict(merged["proposed_room"])
                for key in (
                    "meeting_type",
                    "hybrid_av",
                    "location_preference",
                    "catering",
                    "special_access",
                    "attendees",
                    "date",
                    "preferred_time",
                    "end_time",
                    "duration_hours",
                ):
                    if merged.get(key) is not None:
                        proposed[key if key != "preferred_time" else "start"] = (
                            merged.get("preferred_time") if key == "preferred_time" else merged.get(key)
                        )
                if merged.get("preferred_time"):
                    proposed["start"] = merged["preferred_time"]
                merged["proposed_room"] = proposed
                outcome.facts = merged
                self.session.add(outcome)
            self._finalize_proposed_meeting_room(outcome, actor="requester")
            return

        if not meeting_room_details_complete(merged):
            gaps = meeting_room_gaps(merged)
            outcome.facts = {
                **merged,
                "checklist_missing": [g["field"] for g in gaps],
            }
            self.session.add(outcome)
            return

        # Core complete — apply silence defaults (no AV, no catering, etc.)
        merged = apply_meeting_room_defaults(merged)
        outcome.facts = merged
        self.session.add(outcome)

        sensitive = self._meeting_room_extraordinary(merged, extraction)
        if sensitive:
            outcome.facts = {
                **merged,
                "auto_book_skipped": sensitive,
                "needs_ops": True,
                "pending_confirmation": False,
            }
            self.session.add(outcome)
            self._send_meeting_room_ops_ack(
                outcome,
                reason="special_request",
                when=when,
                start=start,
                end=end,
                duration=duration,
                attendees=attendees,
            )
            logger.info(
                "meeting_room_ops_required",
                outcome_id=outcome.outcome_id,
                reason=sensitive,
            )
            return

        # Pending proposal: if requirements changed, refresh and re-ask confirm
        if merged.get("pending_confirmation") and merged.get("proposed_room"):
            prev_fp = (merged.get("proposed_room") or {}).get("fingerprint")
            new_fp = requirement_fingerprint(merged)
            if prev_fp and prev_fp != new_fp:
                room = None
                rid = (merged.get("proposed_room") or {}).get("resource_id")
                if rid:
                    room = self.session.get(Resource, rid)
                if room is None:
                    try:
                        needed = int(attendees or 1)
                    except (TypeError, ValueError):
                        needed = 1
                    room = self._find_available_meeting_room(
                        needed,
                        location_preference=merged.get("location_preference"),
                    )
                if room:
                    self._propose_meeting_room(outcome, room, merged, updated=True)
            return

        try:
            needed = int(attendees)
        except (TypeError, ValueError):
            needed = 0
        room = self._find_available_meeting_room(
            needed,
            location_preference=merged.get("location_preference"),
        )
        if not room:
            outcome.facts = {
                **merged,
                "auto_book_skipped": "no_room_available",
                "needs_ops": True,
            }
            self.session.add(outcome)
            self.engine.create_exception(
                outcome=outcome,
                exception_type="NO_MEETING_ROOM",
                title="No meeting room available",
                description=(
                    f"No available room fits {needed or 'requested'} attendees. "
                    "Operator must arrange an alternative."
                ),
                severity="MEDIUM",
                owner_role="OPERATOR",
            )
            self._send_meeting_room_ops_ack(
                outcome,
                reason="no_room_available",
                when=when,
                start=start,
                end=end,
                duration=duration,
                attendees=attendees,
            )
            return

        self._propose_meeting_room(outcome, room, merged, updated=False)

    def _handle_post_booking_updates(self, outcome: Outcome, facts: dict) -> None:
        """Requester added needs after confirmation — record and acknowledge."""
        extras = {
            k: facts.get(k)
            for k in ("catering", "hybrid_av", "special_access", "location_preference", "meeting_type")
            if facts.get(k) is not None
        }
        history = list(facts.get("post_booking_requests") or [])
        history.append(extras)
        outcome.facts = {
            **facts,
            "post_booking_requests": history,
            "needs_ops": True,
        }
        self.session.add(outcome)
        body = (
            "Thanks — we’ve noted your additional request against the confirmed booking.\n\n"
            + "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in extras.items())
            + f"\n\nCase: {outcome.case_reference}\n"
            "Our workplace team will follow up shortly if anything else is needed."
        )
        if outcome.requester_email:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="INFORMATION_ONLY",
                body=body,
                recipients=[outcome.requester_email],
                action_label="UPDATE NOTED",
            )

    def _propose_meeting_room(
        self,
        outcome: Outcome,
        room: Resource,
        facts: dict,
        *,
        updated: bool = False,
    ) -> None:
        """Hold an available room and ask the requester to confirm the summary."""
        from app.services.meeting_room import requirement_fingerprint, summarize_meeting_requirements

        attendees = facts.get("attendees")
        when = facts.get("date")
        start = facts.get("preferred_time") or facts.get("time_window")
        duration = facts.get("duration_hours")
        end = facts.get("end_time")
        try:
            needed = int(attendees or 1)
        except (TypeError, ValueError):
            needed = 1

        proposal = {
            "resource_id": room.resource_id,
            "name": room.name,
            "capacity": (room.attributes or {}).get("capacity"),
            "attendees": needed,
            "date": when,
            "start": start,
            "end": end,
            "duration_hours": duration,
            "meeting_type": facts.get("meeting_type"),
            "hybrid_av": facts.get("hybrid_av"),
            "location_preference": facts.get("location_preference"),
            "catering": facts.get("catering"),
            "special_access": facts.get("special_access"),
            "assigned_to_email": outcome.requester_email,
            "fingerprint": requirement_fingerprint(facts),
        }
        room.status = "RESERVED"
        room.attributes = {
            **(room.attributes or {}),
            "booking": {**proposal, "pending_confirmation": True},
        }
        self.session.add(room)

        outcome.facts = {
            **facts,
            "proposed_room": proposal,
            "pending_confirmation": True,
            "needs_ops": False,
            "checklist_missing": [],
        }
        self.session.add(outcome)

        req_lines = summarize_meeting_requirements(facts)
        req_block = "\n".join(f"- {line}" for line in req_lines)
        intro = (
            "Thanks — we’ve updated what we have on file for your request.\n\n"
            if updated
            else "Good news — a room is available for your request.\n\n"
        )
        body = (
            f"{intro}"
            f"Proposed room: {room.name}\n"
            f"Case: {outcome.case_reference}\n\n"
            f"Here’s what we understood as your requirements:\n{req_block}\n\n"
            "Should we confirm this booking?\n"
            "Reply \"confirm\" (or \"yes\") to lock it in.\n"
            "If you need any other facilities — AV, catering, a different floor, visitor passes, "
            "etc. — mention them in your reply and we’ll update before confirming."
        )
        if outcome.requester_email:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="ACTION_REQUIRED",
                body=body,
                recipients=[outcome.requester_email],
                action_label="CONFIRM BOOKING",
            )
        if outcome.conversation_id:
            from app.models.intake import Conversation as ConvModel

            conv = self.session.get(ConvModel, outcome.conversation_id)
            if conv:
                conv.facts = {**(conv.facts or {}), **(outcome.facts or {})}
                self.session.add(conv)
        logger.info(
            "meeting_room_proposed",
            outcome_id=outcome.outcome_id,
            room=room.name,
            requester=outcome.requester_email,
            updated=updated,
        )

    def _finalize_proposed_meeting_room(self, outcome: Outcome, *, actor: str) -> None:
        """Convert a proposed hold into a confirmed booking after requester/ops confirm."""
        facts = dict(outcome.facts or {})
        proposal = facts.get("proposed_room") or {}
        if not proposal:
            raise ValueError("No proposed room to confirm")

        room = None
        if proposal.get("resource_id"):
            room = self.session.get(Resource, proposal["resource_id"])

        requester = (
            self.engine.find_person_by_email(outcome.requester_email or "")
            if outcome.requester_email
            else None
        )
        booking = {
            **proposal,
            "assigned_to_email": outcome.requester_email,
            "assigned_to_person_id": requester.person_id if requester else None,
            "auto": actor == "system" or actor == "requester",
            "confirmed_by": actor,
            "pending_confirmation": False,
        }
        if room:
            room.status = "RESERVED"
            if requester:
                room.allocated_to_person_id = requester.person_id
            room.attributes = {**(room.attributes or {}), "booking": booking}
            self.session.add(room)

        outcome.facts = {
            **facts,
            "booked_room": booking,
            "assigned_to": outcome.requester_email,
            "pending_confirmation": False,
            "needs_ops": False,
            "booking_confirmed": True,
        }
        if requester and not outcome.requester_person_id:
            outcome.requester_person_id = requester.person_id
        self.session.add(outcome)

        task = self.session.exec(
            select(Task).where(
                Task.outcome_id == outcome.outcome_id,
                Task.code == "RESERVE_ROOM",
            )
        ).first()
        if task and task.status not in {"VERIFIED", "CLOSED"}:
            self.engine.update_task_status(
                task,
                "VERIFIED",
                actor=actor,
                resolution=f"Confirmed {booking.get('name')} for {outcome.requester_email}",
            )

        when = booking.get("date")
        start = booking.get("start")
        end = booking.get("end")
        duration = booking.get("duration_hours")
        when_bits = f" on {when}" if when else ""
        time_bits = ""
        if start and end:
            time_bits = f" from {start} to {end}"
        elif start:
            time_bits = f" at {start}"
        if duration and not end:
            time_bits += f" ({duration}h)"
        body = (
            f"Your meeting room booking is confirmed.\n\n"
            f"Room: {booking.get('name')}\n"
            f"For: {outcome.requester_email}\n"
            f"Attendees: {booking.get('attendees')}{when_bits}{time_bits}\n"
            f"Case: {outcome.case_reference}\n\n"
            "No further action needed unless your plans change."
        )
        if outcome.requester_email:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="COMPLETED",
                body=body,
                recipients=[outcome.requester_email],
                action_label="BOOKING CONFIRMED",
            )
        try:
            self.engine.try_close(outcome, actor=actor)
        except ValueError as exc:
            logger.info(
                "meeting_room_confirmed_not_closed",
                outcome_id=outcome.outcome_id,
                reason=str(exc),
            )
        logger.info(
            "meeting_room_confirmed",
            outcome_id=outcome.outcome_id,
            room=booking.get("name"),
            actor=actor,
        )

    def confirm_meeting_room_booking(
        self,
        outcome: Outcome,
        *,
        actor: str,
        room_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Outcome:
        """Operator confirmation: reserve room, email requester, close case."""
        if outcome.template_code != "MEETING_ROOM":
            raise ValueError("This action is only for meeting room requests")
        ensure_meeting_room_resources(self.session, self.tenant_id)

        facts = dict(outcome.facts or {})
        if facts.get("booked_room"):
            raise ValueError("This booking is already confirmed")

        # If a proposal is waiting, finalize that (optionally override room name)
        if facts.get("proposed_room") and not room_name:
            if note:
                facts["ops_note"] = note
                outcome.facts = facts
                self.session.add(outcome)
            self._finalize_proposed_meeting_room(outcome, actor=actor)
            self.session.commit()
            self.session.refresh(outcome)
            return outcome

        attendees = facts.get("attendees")
        when = facts.get("date")
        start = facts.get("preferred_time") or facts.get("time_window")
        duration = facts.get("duration_hours")
        end = facts.get("end_time")
        try:
            needed = int(attendees or 1)
        except (TypeError, ValueError):
            needed = 1

        room: Optional[Resource] = None
        if room_name and room_name.strip():
            wanted = room_name.strip().lower()
            candidates = self.session.exec(
                select(Resource).where(
                    Resource.tenant_id == self.tenant_id,
                    Resource.type == "MEETING_ROOM",
                )
            ).all()
            room = next((r for r in candidates if (r.name or "").lower() == wanted), None)
            if room is None:
                room = next((r for r in candidates if wanted in (r.name or "").lower()), None)
        if room is None:
            room = self._find_available_meeting_room(
                needed,
                location_preference=facts.get("location_preference"),
            )

        display_name = (room.name if room else None) or (room_name and room_name.strip()) or "Assigned meeting room"
        proposal = {
            "resource_id": room.resource_id if room else None,
            "name": display_name,
            "capacity": (room.attributes or {}).get("capacity") if room else None,
            "attendees": needed,
            "date": when,
            "start": start,
            "end": end,
            "duration_hours": duration,
            "meeting_type": facts.get("meeting_type"),
            "hybrid_av": facts.get("hybrid_av"),
            "location_preference": facts.get("location_preference"),
            "catering": facts.get("catering"),
            "special_access": facts.get("special_access"),
            "note": note,
        }
        outcome.facts = {**facts, "proposed_room": proposal, "pending_confirmation": True}
        self.session.add(outcome)
        self._finalize_proposed_meeting_room(outcome, actor=actor)
        self.session.commit()
        self.session.refresh(outcome)
        return outcome

    def _send_meeting_room_ops_ack(
        self,
        outcome: Outcome,
        *,
        reason: str,
        when: Any = None,
        start: Any = None,
        end: Any = None,
        duration: Any = None,
        attendees: Any = None,
    ) -> None:
        """Professional holding reply while an operator finalises the booking."""
        if not outcome.requester_email:
            return
        facts = dict(outcome.facts or {})
        if facts.get("ops_ack_sent"):
            return

        when_bits = f" on {when}" if when else ""
        time_bits = ""
        if start and end:
            time_bits = f" from {start} to {end}"
        elif start:
            time_bits = f" starting {start}"
        if duration and not end:
            time_bits += f" ({duration}h)"
        attendee_bits = f" for {attendees} attendees" if attendees else ""

        if reason == "no_room_available":
            detail = (
                "We are checking alternative rooms and availability against your request"
                f"{attendee_bits}{when_bits}{time_bits}."
            )
        else:
            detail = (
                "Your request includes details that need a short review by our workplace team"
                f"{attendee_bits}{when_bits}{time_bits}."
            )

        body = (
            "Thank you for your meeting room request.\n\n"
            f"{detail}\n\n"
            "We have received your details and will contact you with a confirmation "
            "as soon as possible.\n\n"
            f"Reference: {outcome.case_reference}\n\n"
            "If anything changes (time, attendees, or requirements), simply reply to this email."
        )
        self.comms.send_case_update(
            outcome=outcome,
            communication_type="INFORMATION_ONLY",
            body=body,
            recipients=[outcome.requester_email],
            action_label="REQUEST RECEIVED",
        )
        facts["ops_ack_sent"] = True
        outcome.facts = facts
        self.session.add(outcome)

    def _meeting_room_extraordinary(
        self,
        facts: dict,
        extraction: Optional[ExtractionResult],
    ) -> Optional[str]:
        """Ops only for sensitive flags — facility needs are normal checklist fields."""
        del facts  # checklist fields are handled elsewhere
        if not extraction:
            return None
        if extraction.human_review_required:
            return "human_review_required"
        if extraction.safety_concern:
            return "safety_concern"
        if extraction.financial_action:
            return "financial_action"
        if extraction.access_control_action:
            return "access_control_action"
        return None

    def _find_available_meeting_room(
        self,
        attendees: int,
        location_preference: Optional[str] = None,
    ) -> Optional[Resource]:
        rooms = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "MEETING_ROOM",
                Resource.status == "AVAILABLE",
            )
        ).all()
        needed = max(int(attendees or 0), 1)
        fitting = []
        for room in rooms:
            capacity = (room.attributes or {}).get("capacity")
            try:
                cap = int(capacity) if capacity is not None else 999
            except (TypeError, ValueError):
                cap = 999
            if cap >= needed:
                fitting.append((cap, room))
        if not fitting:
            return None
        pref = (location_preference or "").strip().lower()
        if pref and pref not in {"any", "none", "n/a", "na", "no preference", "wherever"}:
            preferred = [
                (cap, room)
                for cap, room in fitting
                if pref in (room.name or "").lower()
                or pref in str((room.attributes or {}).get("floor") or "").lower()
                or pref in str((room.attributes or {}).get("building") or "").lower()
            ]
            if preferred:
                fitting = preferred
        fitting.sort(key=lambda item: item[0])
        return fitting[0][1]

    def _scenario_a(self, outcome: Outcome, facts: dict, context: dict) -> None:
        available = context.get("available_seats_count", 0)
        if facts.get("permanent_seat_available") is False or available == 0:
            self.engine.create_exception(
                outcome=outcome,
                exception_type="NO_PERMANENT_SEAT",
                title="No permanent seat available",
                description="Permanent seating unavailable. Temporary alternatives require workplace manager decision.",
                options=[
                    {"code": "TEMP_HOTDESK", "label": "Reserve temporary hot-desk"},
                    {"code": "TEMP_VISITOR", "label": "Visitor seating for day-1"},
                    {"code": "DEFER_ONSITE", "label": "Defer onsite until permanent seat"},
                ],
                owner_role="WORKPLACE",
            )
            self.engine.apply_blocker(
                outcome,
                blocker_code="NO_PERMANENT_SEAT",
                blocked_task_codes=["SEAT_PERMANENT"],
                reason="No permanent seat available",
            )
            self.engine.request_approval(
                outcome=outcome,
                approval_type="SEATING_ALTERNATIVE",
                approver_role="WORKPLACE",
                payload={"options": ["TEMP_HOTDESK", "TEMP_VISITOR", "DEFER_ONSITE"]},
            )
            # Ensure independent tasks continue (laptop, ID, access, induction)
            tasks = self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
            for t in tasks:
                if t.code != "SEAT_PERMANENT" and not t.is_blocked:
                    if t.status == "NOT_STARTED":
                        t.status = "ASSIGNED"
                        self.session.add(t)

    def _scenario_b_parking(self, outcome: Outcome, facts: dict, context: dict) -> None:
        allocated = context.get("allocated_resources") or []
        parking = next((r for r in allocated if r["type"] == "PARKING_SLOT"), None)
        if parking:
            facts["verified_allocation"] = parking
            outcome.facts = {**(outcome.facts or {}), **facts}
            res = self.session.get(Resource, parking["resource_id"])
            if res:
                res.status = "CONFLICT"
                self.session.add(res)
        # Find temporary alternative
        alt = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "PARKING_SLOT",
                Resource.status == "AVAILABLE",
            )
        ).first()
        if alt:
            outcome.facts = {
                **(outcome.facts or {}),
                "temporary_alternative": {
                    "resource_id": alt.resource_id,
                    "name": alt.name,
                },
            }
            alt.status = "RESERVED"
            self.session.add(alt)
        self.engine.request_approval(
            outcome=outcome,
            approval_type="TEMP_PARKING",
            approver_role="SECURITY",
            payload={"temporary": outcome.facts.get("temporary_alternative")},
        )

    def _scenario_b_chair(self, outcome: Outcome, facts: dict, context: dict) -> None:
        # Immediate restoration + separate root cause already in template tasks
        self.engine.create_exception(
            outcome=outcome,
            exception_type="MISSING_CHAIR",
            title="Chair missing",
            description="Immediate temporary restoration and separate root-cause corrective action required.",
            severity="MEDIUM",
            owner_role="ADMIN",
        )

    def _scenario_c(self, outcome: Outcome, extraction: ExtractionResult) -> None:
        issues = [i.model_dump() for i in extraction.issues] or [
            {"issue_type": "QUALITY", "summary": extraction.summary, "severity": "MEDIUM"}
        ]
        self.engine.add_vendor_issues(outcome, issues)
        # Never auto-sanction
        if extraction.vendor_sanction:
            self.engine.request_approval(
                outcome=outcome,
                approval_type="VENDOR_SANCTION",
                approver_role="PROCUREMENT",
                payload={"recommended": False, "note": "Allegations remain UNVERIFIED"},
            )

    def _scenario_d(
        self,
        outcome: Outcome,
        facts: dict,
        context: dict,
        extraction: ExtractionResult,
    ) -> None:
        invoice_number = str(facts.get("invoice_number") or facts.get("invoice_no") or "")
        amount = float(facts.get("amount") or 0)
        quantity = float(facts.get("quantity") or 0)
        unit_rate = float(facts.get("unit_rate") or facts.get("rate") or 0)
        po_number = facts.get("po_number")
        bank_changed = bool(facts.get("bank_details_changed")) or extraction.entities.get("bank_details_changed")

        # Duplicate invoice check
        if invoice_number:
            dup = self.session.exec(
                select(Invoice).where(
                    Invoice.tenant_id == self.tenant_id,
                    Invoice.invoice_number == invoice_number,
                )
            ).first()
            if dup:
                inv = Invoice(
                    tenant_id=self.tenant_id,
                    invoice_number=invoice_number,
                    amount=amount,
                    quantity=quantity,
                    unit_rate=unit_rate,
                    match_status="DUPLICATE",
                    outcome_id=outcome.outcome_id,
                    bank_details_changed=bool(bank_changed),
                    attributes={"duplicate_of": dup.invoice_id},
                )
                # Use unique constraint carefully — append suffix for record
                inv.invoice_number = f"{invoice_number}#DUP#{outcome.case_reference}"
                self.session.add(inv)
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="DUPLICATE_INVOICE",
                    title="Duplicate invoice detected",
                    description=f"Invoice {invoice_number} already exists ({dup.invoice_id})",
                    severity="HIGH",
                    owner_role="FINANCE",
                )
                self.engine.apply_blocker(
                    outcome,
                    "DUPLICATE_INVOICE",
                    ["ERP_HANDOFF", "PAYMENT_APPROVAL"],
                    "Duplicate invoice — settlement blocked",
                )
                return

        po = None
        if po_number:
            po = self.session.exec(
                select(PurchaseOrder).where(PurchaseOrder.po_number == str(po_number))
            ).first()
        receipt = None
        if po:
            receipt = self.session.exec(select(Receipt).where(Receipt.po_id == po.po_id)).first()

        match_status = "PENDING_REVIEW"
        if bank_changed:
            match_status = "BANK_CHANGE_FLAGGED"
            self.engine.create_exception(
                outcome=outcome,
                exception_type="BANK_DETAILS_CHANGE",
                title="Bank details change requested",
                description="Independent authorised verification required. No automatic update.",
                severity="CRITICAL",
                owner_role="FINANCE",
            )
            self.engine.request_approval(
                outcome=outcome,
                approval_type="BANK_DETAILS_VERIFICATION",
                approver_role="FINANCE",
                payload={"source": "email", "auto_update": False},
            )
        elif not po:
            match_status = "MISSING_PO"
            self.engine.create_exception(
                outcome=outcome,
                exception_type="MISSING_PO",
                title="Purchase order missing",
                description="Invoice cannot be matched without PO",
                owner_role="PROCUREMENT",
            )
        elif not receipt:
            match_status = "MISSING_RECEIPT"
            self.engine.create_exception(
                outcome=outcome,
                exception_type="MISSING_RECEIPT",
                title="Goods receipt / service entry missing",
                description="Three-way match requires receipt/service entry",
                owner_role="PROCUREMENT",
            )
        else:
            # Deterministic three-way match with prototype tolerances
            qty_tol = 0.0
            rate_tol = 0.01
            if quantity and abs(quantity - receipt.quantity_received) > qty_tol:
                match_status = "QUANTITY_MISMATCH"
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="QUANTITY_MISMATCH",
                    title="Invoice quantity mismatch",
                    description=f"Invoice qty {quantity} vs receipt {receipt.quantity_received}",
                    owner_role="PROCUREMENT",
                )
            elif unit_rate and abs(unit_rate - po.unit_rate) > rate_tol:
                match_status = "RATE_MISMATCH"
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="RATE_MISMATCH",
                    title="Invoice rate mismatch",
                    description=f"Invoice rate {unit_rate} vs PO {po.unit_rate}",
                    owner_role="FINANCE",
                )
            else:
                expected = po.quantity * po.unit_rate
                if amount and abs(amount - expected) > 1.0:
                    match_status = "RATE_MISMATCH"
                    self.engine.create_exception(
                        outcome=outcome,
                        exception_type="AMOUNT_MISMATCH",
                        title="Invoice amount mismatch",
                        description=f"Invoice amount {amount} vs expected {expected}",
                        owner_role="FINANCE",
                    )
                else:
                    match_status = "MATCHED"
                    self.engine.request_approval(
                        outcome=outcome,
                        approval_type="INVOICE_PAYMENT_APPROVAL",
                        approver_role="FINANCE",
                        payload={
                            "invoice_number": invoice_number,
                            "amount": amount,
                            "po_number": po.po_number,
                            "auto_payment": False,
                        },
                    )

        vendor_id = po.vendor_id if po else None
        if not vendor_id and facts.get("vendor_name"):
            vendor = self.session.exec(
                select(Vendor).where(Vendor.name == facts["vendor_name"])
            ).first()
            vendor_id = vendor.vendor_id if vendor else None

        inv = Invoice(
            tenant_id=self.tenant_id,
            vendor_id=vendor_id,
            po_id=po.po_id if po else None,
            receipt_id=receipt.receipt_id if receipt else None,
            invoice_number=invoice_number or f"UNKNOWN-{outcome.case_reference}",
            amount=amount,
            quantity=quantity,
            unit_rate=unit_rate,
            match_status=match_status,
            bank_details_changed=bool(bank_changed),
            outcome_id=outcome.outcome_id,
            erp_handoff_status="NOT_STARTED",
            attributes={"note": "LLM must not approve payment"},
        )
        self.session.add(inv)
        # Never auto-release payment
        outcome.facts = {
            **(outcome.facts or {}),
            "invoice_match_status": match_status,
            "payment_auto_approved": False,
        }
        self.session.add(outcome)
