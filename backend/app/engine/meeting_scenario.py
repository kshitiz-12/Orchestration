"""Client meeting outcome orchestration (prototype-fidelity full path)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.core.logging import get_logger
from app.domain.meeting import MeetingStage
from app.engine.outcome_engine import OutcomeEngine
from app.engine.outcome_pattern import append_decision_trace
from app.engine.outcome_reducer import reduce_meeting_facts
from app.models.org import Contract, Resource, Vendor, utcnow
from app.models.outcome import Outcome, Requirement, Task
from app.policy.meeting_policy import (
    active_modules,
    build_no_resource_alternatives,
    ensure_meeting_policy_rule,
    load_meeting_policy,
)
from app.schemas.ai import ExtractionResult
from app.services.communication import CommunicationService, resolve_requester_name
from app.services.meeting_room import (
    apply_internal_vc_policy,
    apply_meeting_room_defaults,
    catering_needed,
    compute_hold_window,
    external_visitor_count,
    guest_vehicle_count,
    hybrid_needed,
    is_booking_confirmation,
    is_employee_satisfied,
    is_low_risk_auto_bookable,
    meeting_room_details_complete,
    meeting_room_gaps,
    presentation_needed,
    requirement_fingerprint,
    score_meeting_room,
    summarize_meeting_requirements,
)

logger = get_logger(__name__)

MEETING_ROOM_TEMPLATE = {
    "code": "MEETING_ROOM",
    "name": "Client meeting arrangement",
    "category": "MEETING_ROOM",
    "case_prefix": "ROOM",
    "requirements": [
        {"code": "BOOKING", "title": "Meeting room reserved", "is_mandatory": True},
        {"code": "APPROVAL", "title": "Catering / spend approval", "is_mandatory": False},
        {"code": "VISITORS", "title": "Visitor access prepared", "is_mandatory": False},
        {"code": "PARKING", "title": "Guest parking allocated", "is_mandatory": False},
        {"code": "AV", "title": "AV / VC ready", "is_mandatory": False},
        {"code": "CATERING", "title": "Catering arranged", "is_mandatory": False},
        {"code": "READINESS", "title": "Pre-meeting readiness", "is_mandatory": True},
        {"code": "EMPLOYEE_CONFIRM", "title": "Organiser confirmation", "is_mandatory": True},
        {"code": "INVOICE", "title": "Invoice & payment (financial)", "is_mandatory": False},
    ],
    "tasks": [
        {
            "code": "RESERVE_ROOM",
            "title": "Reserve meeting room",
            "owner_role": "OPERATOR",
            "task_group": "Ops",
            "requirement_code": "BOOKING",
        },
        {
            "code": "CATERING_APPROVAL",
            "title": "Obtain catering spend approval",
            "owner_role": "MANAGER",
            "task_group": "Approval",
            "requirement_code": "APPROVAL",
            "is_mandatory": False,
        },
        {
            "code": "PREPARE_VISITORS",
            "title": "Prepare visitor access records",
            "owner_role": "SECURITY",
            "task_group": "Visitors",
            "requirement_code": "VISITORS",
            "is_mandatory": False,
        },
        {
            "code": "ALLOCATE_PARKING",
            "title": "Allocate guest parking",
            "owner_role": "SECURITY",
            "task_group": "Parking",
            "requirement_code": "PARKING",
            "is_mandatory": False,
        },
        {
            "code": "AV_TEST",
            "title": "AV / VC test before meeting",
            "owner_role": "IT",
            "task_group": "AV",
            "requirement_code": "AV",
            "is_mandatory": False,
        },
        {
            "code": "HOUSEKEEPING",
            "title": "Room setup & housekeeping",
            "owner_role": "ADMIN",
            "task_group": "Setup",
            "requirement_code": "READINESS",
        },
        {
            "code": "VENDOR_CATERING",
            "title": "Assign catering vendor",
            "owner_role": "OPERATOR",
            "task_group": "Catering",
            "requirement_code": "CATERING",
            "is_mandatory": False,
        },
        {
            "code": "EMPLOYEE_CONFIRM",
            "title": "Organiser satisfaction confirmation",
            "owner_role": "OPERATOR",
            "task_group": "Close",
            "requirement_code": "EMPLOYEE_CONFIRM",
        },
        {
            "code": "INVOICE_VALIDATE",
            "title": "Validate catering invoice",
            "owner_role": "FINANCE",
            "task_group": "Finance",
            "requirement_code": "INVOICE",
            "is_mandatory": False,
        },
        {
            "code": "INVOICE_POST",
            "title": "Post invoice to ERP (stub)",
            "owner_role": "FINANCE",
            "task_group": "Finance",
            "requirement_code": "INVOICE",
            "is_mandatory": False,
        },
        {
            "code": "INVOICE_PAY",
            "title": "Confirm payment (stub)",
            "owner_role": "FINANCE",
            "task_group": "Finance",
            "requirement_code": "INVOICE",
            "is_mandatory": False,
        },
    ],
}


def ensure_meeting_room_template(session: Session, tenant_id: str) -> None:
    from app.models.org import OutcomeTemplate

    existing = session.exec(
        select(OutcomeTemplate).where(
            OutcomeTemplate.tenant_id == tenant_id,
            OutcomeTemplate.code == "MEETING_ROOM",
        )
    ).first()
    if existing:
        # Upgrade thin templates in place for existing tenants
        existing.name = MEETING_ROOM_TEMPLATE["name"]
        existing.requirements = MEETING_ROOM_TEMPLATE["requirements"]
        existing.tasks = MEETING_ROOM_TEMPLATE["tasks"]
        existing.case_prefix = MEETING_ROOM_TEMPLATE["case_prefix"]
        session.add(existing)
        session.flush()
        return
    session.add(OutcomeTemplate(tenant_id=tenant_id, **MEETING_ROOM_TEMPLATE))
    session.flush()


def ensure_meeting_room_resources(session: Session, tenant_id: str) -> None:
    from app.models.org import Location

    rooms = session.exec(
        select(Resource).where(
            Resource.tenant_id == tenant_id,
            Resource.type == "MEETING_ROOM",
        )
    ).all()
    if not rooms:
        locations = session.exec(
            select(Location).where(
                Location.tenant_id == tenant_id,
                Location.type == "ROOM",
            )
        ).all()
        specs = [
            (8, False, True, False, "Focus Room 5A", "5", "finance"),
            (8, True, True, False, "Focus Room 5B", "5", "finance"),
            (10, True, True, False, "Meeting Room 5C", "5", ""),
            (16, True, True, False, "Conference Room 8B", "8", ""),
            (20, True, True, False, "Conference Room 12A", "12", ""),
            (16, True, True, True, "Conference Room 10B", "10", ""),
            (12, True, False, False, "Meeting Room F1-R1", "1", ""),
            (10, False, True, False, "Meeting Room F1-R2", "1", ""),
            (8, True, True, False, "Meeting Room F2-R1", "2", ""),
            (6, False, False, False, "Huddle Room F2-R2", "2", ""),
        ]
        for i, (cap, vc, display, complaint, name, floor, near) in enumerate(specs):
            loc = locations[i] if i < len(locations) else None
            session.add(
                Resource(
                    tenant_id=tenant_id,
                    type="MEETING_ROOM",
                    name=name,
                    location_id=loc.location_id if loc else None,
                    status="AVAILABLE",
                    attributes={
                        "capacity": cap,
                        "video_conferencing": vc,
                        "presentation_display": display,
                        "display": display,
                        "open_complaint": complaint,
                        "floor": floor,
                        "near_department": near,
                    },
                )
            )
        session.flush()
    else:
        # Enrich attributes if bare
        for i, room in enumerate(rooms):
            attrs = dict(room.attributes or {})
            changed = False
            if "video_conferencing" not in attrs:
                attrs["video_conferencing"] = i % 2 == 0
                changed = True
            if "presentation_display" not in attrs:
                attrs["presentation_display"] = True
                changed = True
            if "open_complaint" not in attrs:
                attrs["open_complaint"] = "10B" in (room.name or "")
                changed = True
            if changed:
                room.attributes = attrs
                session.add(room)
        session.flush()

    # Always ensure a large room exists (prototype demos often request 20–40 people)
    large = session.exec(
        select(Resource).where(
            Resource.tenant_id == tenant_id,
            Resource.type == "MEETING_ROOM",
            Resource.name == "Auditorium A",
        )
    ).first()
    if not large:
        session.add(
            Resource(
                tenant_id=tenant_id,
                type="MEETING_ROOM",
                name="Auditorium A",
                status="AVAILABLE",
                attributes={
                    "capacity": 40,
                    "video_conferencing": True,
                    "presentation_display": True,
                    "display": True,
                    "open_complaint": False,
                    "floor": "G",
                    "near_department": "",
                },
            )
        )
        session.flush()
    elif large.status != "AVAILABLE" and not (large.attributes or {}).get("booking"):
        large.status = "AVAILABLE"
        session.add(large)
        session.flush()

    # Ensure enough parking for demos
    parking = session.exec(
        select(Resource).where(
            Resource.tenant_id == tenant_id,
            Resource.type == "PARKING_SLOT",
        )
    ).all()
    available = [p for p in parking if p.status == "AVAILABLE"]
    if len(available) < 3:
        for i in range(3 - len(available)):
            session.add(
                Resource(
                    tenant_id=tenant_id,
                    type="PARKING_SLOT",
                    name=f"Guest-P-{i + 10:02d}",
                    status="AVAILABLE",
                    attributes={"guest": True},
                )
            )
        session.flush()

    # FreshServe catering vendor + contract
    vendor = session.exec(
        select(Vendor).where(
            Vendor.tenant_id == tenant_id,
            Vendor.name == "FreshServe Catering Pvt. Ltd.",
        )
    ).first()
    if not vendor:
        vendor = Vendor(
            tenant_id=tenant_id,
            name="FreshServe Catering Pvt. Ltd.",
            category="Catering",
            contact_email="orders@freshserve.demo",
            location="Corporate Office",
            status="ACTIVE",
            approved_services=["High tea", "Lunch"],
            pricing={"currency": "INR", "per_person": 450},
        )
        session.add(vendor)
        session.flush()
        session.add(
            Contract(
                tenant_id=tenant_id,
                vendor_id=vendor.vendor_id,
                name="CAT-GGN-2026-04",
                rate_card={"unit_rate": 450.0, "currency": "INR", "unit": "per_person"},
                status="ACTIVE",
            )
        )
        session.flush()


class ClientMeetingOrchestrator:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        engine: OutcomeEngine,
        comms: CommunicationService,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.engine = engine
        self.comms = comms

    def _save_facts(self, outcome: Outcome, facts: dict) -> None:
        """Persist a new facts dict so JSON mutations are not dropped on commit."""
        outcome.facts = dict(facts)
        self.session.add(outcome)
        flag_modified(outcome, "facts")

    def run(self, outcome: Outcome, facts: dict, extraction: Optional[ExtractionResult] = None) -> None:
        ensure_meeting_room_resources(self.session, self.tenant_id)
        policy = load_meeting_policy(self.session, self.tenant_id)
        ensure_meeting_policy_rule(self.session, self.tenant_id)
        text_blob = ""
        if extraction:
            text_blob = f"{extraction.summary or ''} {extraction.reason or ''}"
            raw = (extraction.entities or {}).get("raw_reply")
            if raw:
                text_blob = f"{text_blob} {raw}"

        incoming = dict(facts or {})
        if extraction and extraction.entities:
            incoming.update(
                {k: v for k, v in extraction.entities.items() if v is not None and v != ""}
            )
        merged = reduce_meeting_facts(
            outcome.facts,
            primary_entities=incoming,
            source_text=text_blob,
        )
        merged["policy_version"] = policy.version
        merged["policy_code"] = policy.code
        merged = append_decision_trace(
            merged,
            {
                "at": utcnow().isoformat(),
                "kind": "reduce",
                "policy_version": policy.version,
                "interpretation_path": incoming.get("interpretation_path")
                or (outcome.facts or {}).get("interpretation_path"),
                "stage": merged.get("orchestration_stage"),
                "gaps": list(merged.get("checklist_missing") or []),
            },
        )

        if not merged.get("registration_ack_sent"):
            # Do not send a separate "registered" mail — incomplete cases get one
            # consolidated ask from the pipeline; complete cases get propose/book/no-fit.
            merged["registration_ack_sent"] = True
            merged["registration_ack_deferred"] = True

        if not merged.get("primary_office"):
            merged["primary_office"] = "Corporate Office, Gurugram"
            merged = reduce_meeting_facts(merged, primary_entities={}, source_text=text_blob)

        attendees = merged.get("attendees")
        when = merged.get("date")
        start = merged.get("preferred_time")
        duration = merged.get("duration_hours")
        end = merged.get("end_time")
        if attendees and when and (start or end or duration):
            outcome.summary = (
                f"Meeting for {attendees} on {when}"
                + (f" at {start}" if start else "")
                + (f"–{end}" if end else "")
                + (f" ({duration}h)" if duration else "")
            )

        if merged.get("booked_room") and (
            merged.get("employee_satisfied")
            or is_employee_satisfied(text_blob)
        ):
            merged["employee_satisfied"] = True
            merged["orchestration_stage"] = MeetingStage.CLOSED.value
            merged["last_action"] = "closed"
            self._save_facts(outcome, merged)
            if (merged.get("operational_status") or "") != "CLOSED":
                self.engine.close_operational(outcome, actor="requester")
                self._maybe_start_invoice(outcome)
            return

        if merged.get("booked_room") and (merged.get("operational_status") or "") != "CLOSED":
            self._handle_post_booking(outcome, merged, extraction)
            return

        confirmed = bool(
            merged.get("booking_confirmed")
            or (extraction and is_booking_confirmation(text_blob))
        )
        if merged.get("pending_confirmation") and confirmed:
            merged = apply_meeting_room_defaults(merged)
            merged = apply_internal_vc_policy(merged)
            hold = compute_hold_window(merged)
            merged.update(hold)
            merged["orchestration_stage"] = MeetingStage.AUTO_BOOKED.value
            self._save_facts(outcome, merged)
            self._finalize_booking(outcome, actor="requester")
            return

        gaps = meeting_room_gaps(merged)
        merged["checklist_missing"] = [g["field"] for g in gaps]
        if gaps:
            merged["orchestration_stage"] = MeetingStage.AWAITING_REQUIREMENTS.value
            merged["outbound_required"] = "clarify"
            merged["last_action"] = "await_requirements"
            self._save_facts(outcome, merged)
            return

        merged["checklist_missing"] = []
        merged = apply_meeting_room_defaults(merged)
        merged = apply_internal_vc_policy(merged)
        hold = compute_hold_window(merged, policy=policy)
        merged.update(hold)
        merged["modules_active"] = active_modules(merged, policy)
        merged["orchestration_stage"] = MeetingStage.SEARCHING.value
        self._save_facts(outcome, merged)

        if extraction and (
            extraction.safety_concern
            or extraction.vendor_sanction
        ):
            merged["needs_ops"] = True
            merged["auto_book_skipped"] = "sensitive_flags"
            merged["last_action"] = "ops_ack"
            merged["outbound_required"] = "ops_ack"
            self._save_facts(outcome, merged)
            self._ops_ack(outcome, merged, reason="special_request")
            return

        if merged.get("pending_confirmation") and merged.get("proposed_room"):
            prev_fp = (merged.get("proposed_room") or {}).get("fingerprint")
            new_fp = requirement_fingerprint(merged)
            if prev_fp and prev_fp != new_fp:
                room = self._pick_room(merged)
                if room:
                    self._propose(outcome, room, merged, updated=True)
                    self._maybe_auto_book_low_risk(outcome)
                    return
            merged["orchestration_stage"] = MeetingStage.PROPOSED.value
            merged["last_action"] = "await_confirm"
            merged["outbound_required"] = "confirm_booking"
            self._save_facts(outcome, merged)
            if outcome.requester_email:
                room_name = (merged.get("proposed_room") or {}).get("name") or "the proposed room"
                name = resolve_requester_name(self.session, outcome=outcome)
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type="ACTION_REQUIRED",
                    body=(
                        f"Dear {name},\n\n"
                        f"We still have {room_name} proposed for this request.\n\n"
                        "Reply \"confirm\" to lock it in, or tell us what to change "
                        "(time, headcount, equipment).\n\n"
                        f"Case: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="AWAITING CONFIRMATION",
                )
            return

        room = self._pick_room(merged)
        if not room:
            max_cap = self._max_room_capacity()
            # Collect zero-score rooms for near-miss alternatives
            all_rooms = self.session.exec(
                select(Resource).where(
                    Resource.tenant_id == self.tenant_id,
                    Resource.type == "MEETING_ROOM",
                )
            ).all()
            zero_scores = []
            for r in all_rooms:
                s, reasons = score_meeting_room(r, merged)
                if s <= 0:
                    zero_scores.append({"name": r.name, "score": s, "reasons": reasons})
            alternatives = build_no_resource_alternatives(
                merged,
                max_capacity=max_cap,
                room_scores=zero_scores,
                policy=policy,
            )
            merged["needs_ops"] = True
            merged["auto_book_skipped"] = "no_room_available"
            merged["orchestration_stage"] = MeetingStage.NO_RESOURCE.value
            merged["outbound_required"] = "no_resource"
            merged["last_action"] = "no_resource"
            merged["inventory_max_capacity"] = max_cap
            merged["no_resource_alternatives"] = alternatives
            merged = append_decision_trace(
                merged,
                {
                    "at": utcnow().isoformat(),
                    "kind": "no_resource",
                    "policy_version": policy.version,
                    "alternatives": [a["code"] for a in alternatives],
                    "max_capacity": max_cap,
                    "requested_attendees": merged.get("attendees"),
                },
            )
            self._save_facts(outcome, merged)
            self.engine.create_exception(
                outcome=outcome,
                exception_type="NO_MEETING_ROOM",
                title="No suitable meeting room available",
                description=(
                    f"No available room met capacity/equipment for {merged.get('attendees')} attendees."
                ),
                options=[
                    {"code": a["code"], "label": a["label"]} for a in alternatives if a.get("code") != "REVIEW_NEAR_MISS"
                ],
                severity="MEDIUM",
                owner_role="OPERATOR",
            )
            if outcome.requester_email:
                name = resolve_requester_name(self.session, outcome=outcome)
                alt_lines = "\n".join(f"- {a['label']}" for a in alternatives if a.get("code") != "REVIEW_NEAR_MISS")
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type="INFORMATION_ONLY",
                    body=(
                        f"Dear {name},\n\n"
                        "We could not find a room that fits this request "
                        f"({merged.get('attendees')} people"
                        f"{', display/VC as needed' if merged.get('hybrid_av') or merged.get('presentation_display') else ''}"
                        f"; largest room holds {merged.get('inventory_max_capacity') or 'fewer'}).\n\n"
                        "Please reply with one of these options:\n"
                        f"{alt_lines}\n\n"
                        f"Case: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="NO ROOM AVAILABLE",
                )
            return

        merged["orchestration_stage"] = MeetingStage.PROPOSED.value
        merged = append_decision_trace(
            merged,
            {
                "at": utcnow().isoformat(),
                "kind": "propose",
                "policy_version": policy.version,
                "room": room.name,
                "score": (merged.get("recommended_room") or {}).get("score"),
                "modules_active": merged.get("modules_active"),
            },
        )
        self._propose(outcome, room, merged, updated=False)
        self._maybe_auto_book_low_risk(outcome)

    def _handle_post_booking(self, outcome: Outcome, merged: dict, extraction: Optional[ExtractionResult]) -> None:
        incoming = (extraction.entities if extraction else {}) or {}
        deltas = {
            k: incoming[k]
            for k in (
                "catering",
                "hybrid_av",
                "special_access",
                "location_preference",
                "meeting_type",
                "dietary",
                "guest_vehicles",
                "external_visitors",
            )
            if k in incoming
            and incoming.get(k) not in (None, "")
            and incoming.get(k) != (merged.get("booked_room") or {}).get(k)
        }
        merged["orchestration_stage"] = MeetingStage.MONITORING.value
        if deltas:
            history = list(merged.get("post_booking_requests") or [])
            history.append(deltas)
            merged.update(deltas)
            merged["post_booking_requests"] = history
            merged["needs_ops"] = True
            merged["last_action"] = "post_booking_update"
            merged["outbound_required"] = "update_noted"
            self._save_facts(outcome, merged)
            if outcome.requester_email:
                name = resolve_requester_name(self.session, outcome=outcome)
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type="INFORMATION_ONLY",
                    body=(
                        f"Dear {name},\n\n"
                        "Thanks — we’ve noted your additional request against the confirmed booking.\n\n"
                        + "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in deltas.items())
                        + f"\n\nCase: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="UPDATE NOTED",
                )
        else:
            merged["last_action"] = "monitoring"
            merged["outbound_required"] = "suppressed"
            self._save_facts(outcome, merged)
            self.comms.record_suppressed(outcome=outcome, reason="no_new_facts_post_booking")

    def _maybe_auto_book_low_risk(self, outcome: Outcome) -> None:
        facts = dict(outcome.facts or {})
        score = float((facts.get("recommended_room") or {}).get("score") or 0)
        if not facts.get("pending_confirmation") or not facts.get("proposed_room"):
            return
        if not is_low_risk_auto_bookable(facts, score):
            return
        facts["auto_booked_low_risk"] = True
        facts["booking_confirmed"] = True
        facts["orchestration_stage"] = MeetingStage.AUTO_BOOKED.value
        facts["last_action"] = "auto_booked"
        self._save_facts(outcome, facts)
        self._finalize_booking(outcome, actor="system_low_risk")

    def _pick_room(self, facts: dict) -> Optional[Resource]:
        rooms = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "MEETING_ROOM",
                Resource.status == "AVAILABLE",
            )
        ).all()
        # Include currently held proposed room for this outcome (status RESERVED)
        held_id = (facts.get("proposed_room") or {}).get("resource_id")
        if held_id:
            held = self.session.get(Resource, held_id)
            if held and held not in rooms:
                rooms = list(rooms) + [held]
        scored = []
        for room in rooms:
            score, reasons = score_meeting_room(room, facts)
            if score > 0:
                scored.append((score, room, reasons))
        if not scored:
            return None
        scored.sort(key=lambda x: (-x[0], (x[1].attributes or {}).get("capacity") or 999))
        best = scored[0]
        facts["room_scores"] = [
            {"name": r.name, "score": s, "reasons": rs} for s, r, rs in scored[:5]
        ]
        facts["recommended_room"] = {"name": best[1].name, "score": best[0], "reasons": best[2]}
        return best[1]

    def _max_room_capacity(self) -> int:
        rooms = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "MEETING_ROOM",
            )
        ).all()
        caps: list[int] = []
        for room in rooms:
            try:
                caps.append(int((room.attributes or {}).get("capacity") or 0))
            except (TypeError, ValueError):
                continue
        return max(caps) if caps else 0

    def _send_registration_ack(self, outcome: Outcome, facts: dict) -> None:
        """Legacy helper — meeting flow no longer sends a standalone register mail."""
        return

    def _ops_ack(self, outcome: Outcome, facts: dict, *, reason: str) -> None:
        if not outcome.requester_email or facts.get("ops_ack_sent"):
            return
        name = resolve_requester_name(self.session, outcome=outcome)
        body = (
            f"Dear {name},\n\n"
            "Thank you for your meeting room request.\n\n"
            "Your request needs a short review by our workplace team "
            f"({reason.replace('_', ' ')}).\n\n"
            "We have received your details and will contact you with a confirmation "
            "as soon as possible.\n\n"
            f"Reference: {outcome.case_reference}"
        )
        self.comms.send_case_update(
            outcome=outcome,
            communication_type="INFORMATION_ONLY",
            body=body,
            recipients=[outcome.requester_email],
            action_label="REQUEST RECEIVED",
        )
        facts["ops_ack_sent"] = True
        self._save_facts(outcome, facts)

    def _propose(self, outcome: Outcome, room: Resource, facts: dict, *, updated: bool) -> None:
        try:
            needed = int(facts.get("attendees") or 1)
        except (TypeError, ValueError):
            needed = 1
        proposal = {
            "resource_id": room.resource_id,
            "name": room.name,
            "capacity": (room.attributes or {}).get("capacity"),
            "score": (facts.get("recommended_room") or {}).get("score"),
            "attendees": needed,
            "date": facts.get("date"),
            "start": facts.get("preferred_time") or facts.get("time_window"),
            "end": facts.get("end_time"),
            "duration_hours": facts.get("duration_hours"),
            "hold_start": facts.get("hold_start"),
            "hold_end": facts.get("hold_end"),
            "meeting_type": facts.get("meeting_type"),
            "hybrid_av": facts.get("hybrid_av"),
            "presentation_display": facts.get("presentation_display"),
            "location_preference": facts.get("location_preference"),
            "catering": facts.get("catering"),
            "special_access": facts.get("special_access"),
            "external_visitors": facts.get("external_visitors"),
            "guest_vehicles": facts.get("guest_vehicles"),
            "dietary": facts.get("dietary"),
            "confidentiality": facts.get("confidentiality"),
            "assigned_to_email": outcome.requester_email,
            "fingerprint": requirement_fingerprint(facts),
        }
        room.status = "RESERVED"
        room.attributes = {**(room.attributes or {}), "booking": {**proposal, "pending_confirmation": True}}
        self.session.add(room)
        facts = {
            **facts,
            "proposed_room": proposal,
            "pending_confirmation": True,
            "needs_ops": False,
            "checklist_missing": [],
            "execution_plan": self._execution_plan(facts, room.name),
            "orchestration_stage": MeetingStage.PROPOSED.value,
            "last_action": "proposed",
            "outbound_required": "confirm_booking",
        }
        self._save_facts(outcome, facts)

        intro = (
            "Thanks — we’ve updated what we have on file for your request.\n\n"
            if updated
            else "Good news — a room is available for your request.\n\n"
        )
        req_block = "\n".join(f"- {line}" for line in summarize_meeting_requirements(facts))
        score = float((facts.get("recommended_room") or {}).get("score") or 0)
        # Low-risk path auto-books immediately — skip the confirm ask email
        if outcome.requester_email and not is_low_risk_auto_bookable(facts, score):
            name = resolve_requester_name(self.session, outcome=outcome)
            body = (
                f"Dear {name},\n\n"
                f"{intro}"
                f"Proposed room: {room.name}\n"
                f"Case: {outcome.case_reference}\n\n"
                f"Here’s what we understood as your requirements:\n{req_block}\n\n"
                "Should we confirm this booking?\n"
                'Reply "confirm" (or "yes") to lock it in.\n'
                "If you need any other facilities — AV, catering, visitors, parking, a different floor — "
                "mention them in your reply and we’ll update before confirming."
            )
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="ACTION_REQUIRED",
                body=body,
                recipients=[outcome.requester_email],
                action_label="CONFIRM BOOKING",
            )
        self._sync_conversation_facts(outcome)
        logger.info("meeting_room_proposed", outcome_id=outcome.outcome_id, room=room.name, updated=updated)

    def _execution_plan(self, facts: dict, room_name: str) -> list[str]:
        plan = [f"Reserve {room_name} with setup/cleanup buffers"]
        if catering_needed(facts):
            plan.append("Obtain catering approval and assign vendor")
        if hybrid_needed(facts) or presentation_needed(facts):
            plan.append("Reserve VC/AV resources and schedule AV test")
        if external_visitor_count(facts) > 0:
            plan.append(f"Create {external_visitor_count(facts)} visitor access requests")
        if guest_vehicle_count(facts) > 0:
            plan.append(f"Allocate {guest_vehicle_count(facts)} guest parking spaces")
        plan.extend(
            [
                "Assign setup / housekeeping / reception tasks",
                "Calculate readiness and request organiser confirmation",
                "Process invoice/payment stubs after operational close (if catering)",
            ]
        )
        return plan

    def _finalize_booking(self, outcome: Outcome, *, actor: str) -> None:
        facts = dict(outcome.facts or {})
        proposal = dict(facts.get("proposed_room") or {})
        room = None
        if proposal.get("resource_id"):
            room = self.session.get(Resource, proposal["resource_id"])
        booking = {**proposal, "pending_confirmation": False, "confirmed_by": actor, "auto": actor == "requester"}
        if room:
            room.status = "RESERVED"
            room.attributes = {**(room.attributes or {}), "booking": booking}
            self.session.add(room)
        facts["booked_room"] = booking
        facts["pending_confirmation"] = False
        facts["needs_ops"] = False
        facts["booking_confirmed"] = True
        facts["orchestration_stage"] = (
            MeetingStage.AUTO_BOOKED.value if actor == "system_low_risk" else MeetingStage.MONITORING.value
        )
        facts["last_action"] = "booked"
        facts["outbound_required"] = "booking_confirmed"
        self._save_facts(outcome, facts)

        self._complete_task(outcome, "RESERVE_ROOM", actor, f"Confirmed {booking.get('name')}")
        self._apply_applicability(outcome, facts)
        self._run_visitors(outcome, facts)
        self._run_parking(outcome, facts)
        self._run_av(outcome, facts)
        self._run_catering(outcome, facts)
        self._mark_readiness_progress(outcome)

        low_risk = bool(facts.get("auto_booked_low_risk") or actor == "system_low_risk")
        assumptions = facts.get("policy_assumptions") or []
        assumption_lines = "\n".join(
            f"- {a.get('message')}" for a in assumptions if a.get("message")
        )
        modules = []
        if catering_needed(facts):
            modules.append("catering")
        if external_visitor_count(facts) > 0:
            modules.append("visitors")
        if guest_vehicle_count(facts) > 0:
            modules.append("parking")
        if hybrid_needed(facts) or presentation_needed(facts):
            modules.append("AV/display")
        module_line = (
            f"Active preparations: {', '.join(modules)}.\n"
            if modules
            else "No visitor, parking, catering or billing modules were activated.\n"
        )
        name = resolve_requester_name(self.session, outcome=outcome)
        followups: list[str] = []
        if guest_vehicle_count(facts) > 0 and not str(facts.get("vehicle_numbers") or "").strip():
            followups.append(
                f"Please reply with the {guest_vehicle_count(facts)} guest vehicle number(s) for parking."
            )
        if catering_needed(facts) and not str(facts.get("dietary") or "").strip():
            followups.append("Please share dietary split (veg / non-veg) for catering.")
        follow_block = ("\n" + "\n".join(followups) + "\n") if followups else ""
        if low_risk:
            body = (
                f"Dear {name},\n\n"
                f"Your meeting room has been booked.\n\n"
                f"Room: {booking.get('name')}\n"
                f"Date: {booking.get('date')}\n"
                f"Time: {booking.get('start')} – {booking.get('end') or booking.get('duration_hours')}\n"
                f"Hold window: {facts.get('hold_start')} – {facts.get('hold_end')}\n"
                f"Case: {outcome.case_reference}\n\n"
                f"{module_line}"
                + (f"Assumptions:\n{assumption_lines}\n\n" if assumption_lines else "")
                + "If any detail is incorrect, reply to this email before the change cutoff.\n"
                + follow_block
                + 'After the meeting, reply "SATISFIED", "ISSUE REMAINS", or "REOPEN REQUEST".'
            )
        else:
            body = (
                f"Dear {name},\n\n"
                f"Your meeting room booking is confirmed.\n\n"
                f"Room: {booking.get('name')}\n"
                f"Case: {outcome.case_reference}\n"
                f"Hold window: {facts.get('hold_start')} – {facts.get('hold_end')}\n\n"
                f"{module_line}"
                + (f"Assumptions:\n{assumption_lines}\n\n" if assumption_lines else "")
                + follow_block
                + 'After the meeting, reply "satisfied" to close the operational outcome.'
            )
        if outcome.requester_email:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="COMPLETED",
                body=body,
                recipients=[outcome.requester_email],
                action_label="BOOKING CONFIRMED",
            )
        self._sync_conversation_facts(outcome)
        self.engine._recompute_readiness(outcome)

    def _apply_applicability(self, outcome: Outcome, facts: dict) -> None:
        reqs = {
            r.code: r
            for r in self.session.exec(
                select(Requirement).where(Requirement.outcome_id == outcome.outcome_id)
            ).all()
        }
        mapping = {
            "APPROVAL": catering_needed(facts),
            "CATERING": catering_needed(facts),
            "INVOICE": catering_needed(facts),
            "VISITORS": external_visitor_count(facts) > 0,
            "PARKING": guest_vehicle_count(facts) > 0,
            "AV": hybrid_needed(facts) or presentation_needed(facts),
        }
        for code, needed in mapping.items():
            req = reqs.get(code)
            if not req:
                continue
            req.applicability = "REQUIRED" if needed else "NOT_APPLICABLE"
            req.is_mandatory = bool(needed) if code != "READINESS" else True
            if not needed:
                req.status = "COMPLETED"
            self.session.add(req)

    def _run_visitors(self, outcome: Outcome, facts: dict) -> None:
        count = external_visitor_count(facts)
        if count <= 0:
            self._na_task(outcome, "PREPARE_VISITORS")
            return
        visitors = list(facts.get("visitors") or [])
        details = str(facts.get("visitor_details") or "")
        if not visitors:
            for i in range(count):
                visitors.append(
                    {
                        "name": f"Visitor {i + 1}",
                        "organisation": "TBC",
                        "notes": details[:200] if details else "",
                        "status": "PREPARED",
                    }
                )
        facts["visitors"] = visitors
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)
        self._complete_task(outcome, "PREPARE_VISITORS", "system", f"Prepared {count} visitor records")

    def _run_parking(self, outcome: Outcome, facts: dict) -> None:
        needed = guest_vehicle_count(facts)
        if needed <= 0:
            self._na_task(outcome, "ALLOCATE_PARKING")
            return
        slots = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "PARKING_SLOT",
                Resource.status == "AVAILABLE",
            )
        ).all()
        allocated = []
        for slot in slots[:needed]:
            slot.status = "RESERVED"
            slot.attributes = {**(slot.attributes or {}), "outcome_id": outcome.outcome_id}
            self.session.add(slot)
            allocated.append({"resource_id": slot.resource_id, "name": slot.name})
        facts["parking_allocation"] = allocated
        if len(allocated) < needed:
            shortage = needed - len(allocated)
            facts["parking_shortage"] = shortage
            self.engine.create_exception(
                outcome=outcome,
                exception_type="PARKING_SHORTAGE",
                title="Guest parking shortage",
                description=(
                    f"Need {needed} guest spaces; only {len(allocated)} available. "
                    "Options: management overflow, valet, nearby parking, or release unused reservation."
                ),
                severity="MEDIUM",
                owner_role="SECURITY",
                options=[
                    {"code": "OVERFLOW", "label": "Use management overflow"},
                    {"code": "VALET", "label": "Arrange valet"},
                    {"code": "NEARBY", "label": "Nearby parking"},
                    {"code": "RELEASE", "label": "Release unused reservation"},
                ],
            )
            # Prototype auto-resolve: create overflow slots
            for i in range(shortage):
                overflow = Resource(
                    tenant_id=self.tenant_id,
                    type="PARKING_SLOT",
                    name=f"Overflow-M-{i + 1:02d}",
                    status="RESERVED",
                    attributes={"overflow": True, "outcome_id": outcome.outcome_id},
                )
                self.session.add(overflow)
                self.session.flush()
                allocated.append({"resource_id": overflow.resource_id, "name": overflow.name, "overflow": True})
            facts["parking_allocation"] = allocated
            facts["parking_exception_resolved"] = "OVERFLOW"
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)
        self._complete_task(
            outcome,
            "ALLOCATE_PARKING",
            "system",
            f"Allocated {len(allocated)} parking space(s)",
        )

    def _run_av(self, outcome: Outcome, facts: dict) -> None:
        if not (hybrid_needed(facts) or presentation_needed(facts)):
            self._na_task(outcome, "AV_TEST")
            return
        # Demo SLA stub: mark backup activation path available
        facts["av_plan"] = {
            "platform": "Microsoft Teams" if "team" in str(facts.get("hybrid_av") or "").lower() else "Video conference",
            "test_required": True,
            "backup_available": True,
        }
        # Simulate recovery from equipment issue without failing outcome
        if (facts.get("booked_room") or {}).get("name", "").endswith("10B"):
            facts["av_incident"] = {
                "issue": "Camera fault",
                "resolution": "Temporary replacement installed",
                "sla_breach_primary": True,
                "backup_activated": True,
            }
            self.engine.create_exception(
                outcome=outcome,
                exception_type="AV_EQUIPMENT_FAULT",
                title="AV camera failure detected",
                description="Primary camera failed; backup/replacement used. Breach preserved for analytics.",
                severity="MEDIUM",
                owner_role="IT",
            )
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)
        self._complete_task(outcome, "AV_TEST", "system", "AV plan ready (prototype)")

    def _run_catering(self, outcome: Outcome, facts: dict) -> None:
        if not catering_needed(facts):
            self._na_task(outcome, "CATERING_APPROVAL")
            self._na_task(outcome, "VENDOR_CATERING")
            self._na_task(outcome, "INVOICE_VALIDATE")
            self._na_task(outcome, "INVOICE_POST")
            self._na_task(outcome, "INVOICE_PAY")
            return
        try:
            headcount = int(facts.get("attendees") or 1)
        except (TypeError, ValueError):
            headcount = 1
        rate = 450.0
        vendor = self.session.exec(
            select(Vendor).where(
                Vendor.tenant_id == self.tenant_id,
                Vendor.name == "FreshServe Catering Pvt. Ltd.",
            )
        ).first()
        amount = round(rate * headcount, 2)
        facts["catering_quote"] = {
            "vendor": vendor.name if vendor else "FreshServe Catering Pvt. Ltd.",
            "vendor_id": vendor.vendor_id if vendor else None,
            "rate": rate,
            "headcount": headcount,
            "amount_ex_tax": amount,
            "currency": "INR",
            "contract": "CAT-GGN-2026-04",
        }
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)

        # Request manager approval
        task = self.session.exec(
            select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == "CATERING_APPROVAL")
        ).first()
        approval = self.engine.request_approval(
            outcome=outcome,
            approval_type="CATERING_SPEND",
            approver_role="MANAGER",
            payload=facts["catering_quote"],
            task_id=task.task_id if task else None,
        )
        if task:
            task.status = "APPROVAL_PENDING"
            self.session.add(task)
        facts["catering_approval_id"] = approval.approval_id
        # Prototype: auto-note vendor assignment pending approval
        facts["vendor_sla"] = {
            "acceptance_minutes": 30,
            "status": "PENDING_ASSIGNMENT",
            "acceptance_breach_demo": False,
        }
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)

    def on_catering_approved(self, outcome: Outcome) -> None:
        facts = dict(outcome.facts or {})
        quote = facts.get("catering_quote") or {}
        facts["vendor_sla"] = {
            **(facts.get("vendor_sla") or {}),
            "status": "ASSIGNED",
            "assigned_at": utcnow().isoformat(),
            "acceptance_due_minutes": 30,
            # Demo learning: acceptance late but service recovered
            "acceptance_breach_demo": True,
            "accepted_late_minutes": 18,
        }
        facts["catering_assigned"] = True
        self._save_facts(outcome, facts)
        self._complete_task(outcome, "CATERING_APPROVAL", "system", "Catering spend approved")
        self._complete_task(
            outcome,
            "VENDOR_CATERING",
            "system",
            f"Assigned {quote.get('vendor')} for INR {quote.get('amount_ex_tax')}",
        )
        # Enable invoice path
        for code in ("INVOICE_VALIDATE", "INVOICE_POST", "INVOICE_PAY"):
            t = self.session.exec(
                select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == code)
            ).first()
            if t and t.status in {"NOT_STARTED", "CANCELLED"}:
                t.status = "ASSIGNED"
                self.session.add(t)
        req = self.session.exec(
            select(Requirement).where(
                Requirement.outcome_id == outcome.outcome_id, Requirement.code == "INVOICE"
            )
        ).first()
        if req:
            req.applicability = "REQUIRED"
            req.is_mandatory = True
            req.status = "ACTION_PENDING"
            self.session.add(req)

    def _maybe_start_invoice(self, outcome: Outcome) -> None:
        facts = dict(outcome.facts or {})
        if not catering_needed(facts) and not facts.get("catering_assigned"):
            self.engine.close_financial(outcome, actor="system")
            return
        facts["invoice_stub"] = {
            "invoice_number": f"FS-{outcome.case_reference}",
            "amount_ex_tax": (facts.get("catering_quote") or {}).get("amount_ex_tax"),
            "status": "RECEIVED",
        }
        self._save_facts(outcome, facts)

    def _mark_readiness_progress(self, outcome: Outcome) -> None:
        self._complete_task(outcome, "HOUSEKEEPING", "system", "Setup checklist queued/complete (prototype)")
        # READINESS requirement tracks housekeeping + overall prep
        self.engine._recompute_readiness(outcome)

    def _complete_task(self, outcome: Outcome, code: str, actor: str, resolution: str) -> None:
        task = self.session.exec(
            select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == code)
        ).first()
        if task and task.status not in {"VERIFIED", "CLOSED"}:
            self.engine.update_task_status(task, "VERIFIED", actor=actor, resolution=resolution)

    def _na_task(self, outcome: Outcome, code: str) -> None:
        task = self.session.exec(
            select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == code)
        ).first()
        if task:
            task.status = "CLOSED"
            task.resolution = "Not applicable"
            self.session.add(task)

    def _sync_conversation_facts(self, outcome: Outcome) -> None:
        if not outcome.conversation_id:
            return
        from app.models.intake import Conversation

        conv = self.session.get(Conversation, outcome.conversation_id)
        if conv:
            conv.facts = {**(conv.facts or {}), **(outcome.facts or {})}
            conv.current_outcome_id = outcome.outcome_id
            self.session.add(conv)


def confirm_meeting_room_booking(
    *,
    session: Session,
    tenant_id: str,
    engine: OutcomeEngine,
    comms: CommunicationService,
    outcome: Outcome,
    actor: str,
    room_name: Optional[str] = None,
    note: Optional[str] = None,
) -> Outcome:
    ensure_meeting_room_resources(session, tenant_id)
    orch = ClientMeetingOrchestrator(session, tenant_id, engine, comms)
    facts = dict(outcome.facts or {})
    if facts.get("booked_room"):
        raise ValueError("This booking is already confirmed")
    if room_name:
        facts["location_preference"] = room_name
    if note:
        facts["ops_note"] = note
    if not facts.get("proposed_room"):
        facts = apply_meeting_room_defaults(facts)
        facts.update(compute_hold_window(facts))
        room = orch._pick_room(facts)
        if not room and room_name:
            # Synthetic proposal
            facts["proposed_room"] = {
                "name": room_name,
                "attendees": facts.get("attendees"),
                "date": facts.get("date"),
                "fingerprint": requirement_fingerprint(facts),
            }
            outcome.facts = {**facts, "pending_confirmation": True}
            session.add(outcome)
        elif room:
            orch._propose(outcome, room, facts, updated=False)
            session.refresh(outcome)
            facts = dict(outcome.facts or {})
    facts["booking_confirmed"] = True
    outcome.facts = facts
    session.add(outcome)
    orch._finalize_booking(outcome, actor=actor)
    session.commit()
    session.refresh(outcome)
    return outcome
