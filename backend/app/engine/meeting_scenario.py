"""Client meeting outcome orchestration (prototype-fidelity full path)."""

from __future__ import annotations

import re
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
from app.services.admin_ops import AdminOpsNotifier
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
    requirement_email_sections,
)
from app.services.no_resource_flow import (
    detect_no_resource_choice,
    diagnose_no_resource,
    format_outbound_greeting,
    open_request_delta,
    search_relevant_changed,
)
from app.services.room_booking import RoomBookingService, meeting_window

logger = get_logger(__name__)


_CANCEL_RE = re.compile(
    r"\b(?:cancel(?:l?ed)?|call(?:ed)?\s+off|scrap)\s+(?:the\s+|my\s+|this\s+|our\s+)?"
    r"(?:meeting|booking|room|request|reservation|event|it)\b"
    r"|\bno\s+longer\s+need(?:ed)?\b"
    r"|\b(?:meeting|booking|event)\s+(?:is\s+|has\s+been\s+)?(?:cancel(?:l?ed)?|called\s+off)\b",
    re.I,
)


def wants_cancel(extraction: Optional[ExtractionResult], text: str) -> bool:
    """Gemini's speech act leads; phrase match only when the model gave no speech acts."""
    if extraction is not None:
        fd = extraction.fact_delta if isinstance(extraction.fact_delta, dict) else {}
        acts = [str(a).lower() for a in (fd.get("speech_acts") or [])]
        if "cancel" in acts:
            return True
        if acts:
            return False
    return bool(_CANCEL_RE.search(text or ""))


def _hold_hours_label() -> str:
    from app.core.config import get_settings

    hours = float(get_settings().proposal_hold_hours or 24)
    return f"{int(hours)} hours" if hours == int(hours) else f"{hours:g} hours"


def ai_alternative_choice(extraction: Optional[ExtractionResult]) -> Optional[str]:
    """Gemini's pick among no-room options. None = the model didn't answer (use fallback)."""
    if extraction is None:
        return None
    fd = extraction.fact_delta if isinstance(extraction.fact_delta, dict) else {}
    code = str(fd.get("alternative_choice") or "").strip().upper()
    if not code:
        return None
    return code if code in {"LARGER_VENUE", "SPLIT_ROOMS", "DIFFERENT_TIME", "REDUCE_HEADCOUNT"} else "NONE"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _capacity(room: Resource) -> int:
    return _int((room.attributes or {}).get("capacity"))


def ensure_offsite_venues(session: Session, tenant_id: str) -> None:
    """Upsert OFFSITE_VENUE resources from OFFSITE_VENUES ("Name:capacity; Name:capacity")."""
    from app.core.config import get_settings

    raw = (get_settings().offsite_venues or "").strip()
    if not raw:
        return
    existing = {
        (r.name or "").strip().lower(): r
        for r in session.exec(
            select(Resource).where(Resource.tenant_id == tenant_id, Resource.type == "OFFSITE_VENUE")
        ).all()
    }
    for chunk in re.split(r"[;\n]", raw):
        if not chunk.strip():
            continue
        name, _, cap = chunk.rpartition(":")
        if not name.strip():
            name, cap = cap, ""
        name = name.strip()
        capacity = _int(cap.strip())
        row = existing.get(name.lower())
        if row is None:
            session.add(
                Resource(
                    tenant_id=tenant_id,
                    type="OFFSITE_VENUE",
                    name=name,
                    status="AVAILABLE",
                    attributes={"capacity": capacity, "offsite": True, "video_conferencing": True,
                                "presentation_display": True, "display": True},
                )
            )
        elif capacity and _capacity(row) != capacity:
            row.attributes = {**(row.attributes or {}), "capacity": capacity}
            session.add(row)
    session.flush()


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
        self.admin_ops = AdminOpsNotifier(session, tenant_id, comms)
        self.bookings = RoomBookingService(session, tenant_id)

    def _save_facts(self, outcome: Outcome, facts: dict) -> None:
        """Persist a new facts dict so JSON mutations are not dropped on commit."""
        outcome.facts = dict(facts)
        self.session.add(outcome)
        flag_modified(outcome, "facts")

    def run(
        self,
        outcome: Outcome,
        facts: dict,
        extraction: Optional[ExtractionResult] = None,
        *,
        prior_facts: Optional[dict] = None,
    ) -> None:
        """`prior_facts` = the case before this message; callers that pre-merge facts must pass it."""
        ensure_meeting_room_resources(self.session, self.tenant_id)
        ensure_offsite_venues(self.session, self.tenant_id)
        policy = load_meeting_policy(self.session, self.tenant_id)
        ensure_meeting_policy_rule(self.session, self.tenant_id)
        prior_snapshot = dict(prior_facts if prior_facts is not None else (outcome.facts or {}))
        text_blob = ""
        if extraction:
            raw = (extraction.entities or {}).get("raw_reply") or ""
            # Prefer the actual mail — summary-only reduce drops plates / extra asks
            text_blob = f"{raw}\n{extraction.summary or ''} {extraction.reason or ''}".strip()

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
            self._save_facts(outcome, merged)
            # First touch: admin FYI for every new case (visibility, not approval)
            if not (prior_snapshot.get("admin_ops_notices") or prior_snapshot.get("registration_ack_sent")):
                self.admin_ops.fyi_case_opened(outcome, facts=merged)
                merged = dict(outcome.facts or merged)

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
            # Keep mail subjects operational — not Gemini narrative titles
            if not (outcome.title or "").startswith("Meeting for "):
                outcome.title = outcome.summary[:200]

        if wants_cancel(extraction, text_blob) and (merged.get("orchestration_stage") or "") != MeetingStage.CANCELLED.value:
            self._save_facts(outcome, merged)
            self.cancel_case(outcome, actor="requester", reason=(extraction.summary if extraction else "") or "")
            return

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
            self._handle_post_booking(outcome, merged, extraction, prior=prior_snapshot)
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
            if self._proposed_room_taken(outcome, merged):
                # Hold lapsed and someone else booked the slot — find another room
                taken = (merged.get("proposed_room") or {}).get("name")
                merged["pending_confirmation"] = False
                merged["booking_confirmed"] = False
                merged["proposed_room"] = None
                merged["last_action"] = "proposal_slot_taken"
                self._save_facts(outcome, merged)
                room = self._pick_room(merged, outcome.outcome_id)
                if room:
                    merged["replaced_room_note"] = f"{taken} was booked by someone else after the hold expired."
                    self._propose(outcome, room, merged, updated=True)
                else:
                    self._enter_no_resource(outcome, merged, prior=prior_snapshot, policy=policy)
                return
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

        # Already in NO_RESOURCE: act on choice / extras / fact change — don't blindly
        # re-mail the same options menu.
        prior_stage = (prior_snapshot.get("orchestration_stage") or "").upper()
        if prior_stage == MeetingStage.NO_RESOURCE.value:
            handled = self._handle_no_resource_reply(
                outcome,
                merged,
                prior=prior_snapshot,
                text_blob=text_blob,
                policy=policy,
                extraction=extraction,
            )
            if handled:
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
                room = self._pick_room(merged, outcome.outcome_id)
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
                        f"{format_outbound_greeting(name)}\n\n"
                        f"We still have {room_name} proposed for this request.\n\n"
                        "Reply \"confirm\" to lock it in, or tell us what to change "
                        "(time, headcount, equipment).\n\n"
                        f"Case: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="AWAITING CONFIRMATION",
                )
            return

        room = self._pick_room(merged, outcome.outcome_id)
        if not room:
            self._enter_no_resource(outcome, merged, prior=prior_snapshot, policy=policy)
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

    def _handle_no_resource_reply(
        self,
        outcome: Outcome,
        merged: dict,
        *,
        prior: dict,
        text_blob: str,
        policy: Any,
        extraction: Optional[ExtractionResult] = None,
    ) -> bool:
        """Return True if the reply was fully handled (do not re-search)."""
        alts = list(prior.get("no_resource_alternatives") or merged.get("no_resource_alternatives") or [])
        ai_code = ai_alternative_choice(extraction)
        if ai_code is None:
            choice = detect_no_resource_choice(text_blob, alts)
        elif ai_code == "NONE":
            choice = None
        else:
            label = next((a.get("label") for a in alts if a.get("code") == ai_code), None)
            choice = {"code": ai_code, "label": label or ai_code.replace("_", " ").title(), "source": "gemini"}
        facts_changed = search_relevant_changed(prior, merged)
        new_opens = open_request_delta(prior, merged)

        if facts_changed and not choice:
            # Date/time/headcount changed — fall through to re-search
            return False

        if facts_changed and choice:
            # Choice + new search facts: note choice, still re-search
            merged["no_resource_choice"] = choice
            return False

        # Stay in NO_RESOURCE
        merged["orchestration_stage"] = MeetingStage.NO_RESOURCE.value
        merged["needs_ops"] = True
        merged["auto_book_skipped"] = "no_room_available"
        merged["no_resource_alternatives"] = alts or merged.get("no_resource_alternatives")
        merged["no_resource_fingerprint"] = prior.get("no_resource_fingerprint") or requirement_fingerprint(
            merged
        )
        if prior.get("no_resource_diagnosis"):
            merged["no_resource_diagnosis"] = prior.get("no_resource_diagnosis")

        name = resolve_requester_name(self.session, outcome=outcome)
        greet = format_outbound_greeting(name)

        if choice:
            merged["no_resource_choice"] = choice
            merged["last_action"] = f"no_resource_choice:{choice['code']}"
            merged["outbound_required"] = "no_resource_ack"
            merged = append_decision_trace(
                merged,
                {
                    "at": utcnow().isoformat(),
                    "kind": "no_resource_choice",
                    "policy_version": policy.version,
                    "choice": choice.get("code"),
                    "open_requests_delta": new_opens,
                },
            )
            self._save_facts(outcome, merged)
            self._annotate_open_no_room_exception(outcome, choice=choice, extras=new_opens)
            if self._fulfil_choice(outcome, merged, choice):
                return True
            if outcome.requester_email:
                extra_lines = ""
                if new_opens:
                    bits = []
                    for item in new_opens:
                        text = item.get("text") if isinstance(item, dict) else str(item)
                        if text:
                            bits.append(f"- {text}")
                    if bits:
                        extra_lines = "\n\nAlso noted:\n" + "\n".join(bits)
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type="INFORMATION_ONLY",
                    body=(
                        f"{greet}\n\n"
                        f"Thanks — we've recorded your choice: {choice.get('label')}.\n"
                        "Our ops team will take it from here and follow up on this case."
                        f"{extra_lines}\n\n"
                        f"Case: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="CHOICE NOTED",
                    subject_hint=outcome.summary or f"Choice: {choice.get('code')}",
                    suppress_fingerprint=f"choice:{outcome.outcome_id}:{choice.get('code')}",
                )
            self.admin_ops.action_requester_choice(
                outcome,
                choice_label=str(choice.get("label") or choice.get("code")),
                facts=dict(outcome.facts or merged),
            )
            return True

        # No choice, no search change — extras only or empty/thanks
        merged["last_action"] = "no_resource_noted" if new_opens else "no_resource_idle"
        if new_opens:
            merged["outbound_required"] = "update_noted"
            self._save_facts(outcome, merged)
            if outcome.requester_email:
                bits = []
                for item in new_opens:
                    text = item.get("text") if isinstance(item, dict) else str(item)
                    if text:
                        bits.append(f"- {text}")
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type="INFORMATION_ONLY",
                    body=(
                        f"{greet}\n\n"
                        "Thanks — we've noted your additional request(s) against this case.\n"
                        + "\n".join(bits)
                        + "\n\nWe're still working the room options with ops.\n\n"
                        f"Case: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="UPDATE NOTED",
                    subject_hint=outcome.summary or "Additional requests noted",
                    suppress_fingerprint=f"extras:{outcome.outcome_id}:{len(merged.get('open_requests') or [])}",
                )
            return True

        merged["outbound_required"] = "suppressed"
        self._save_facts(outcome, merged)
        self.comms.record_suppressed(
            outcome=outcome,
            reason="no_resource_no_new_choice_or_facts",
            detail={"fingerprint": merged.get("no_resource_fingerprint")},
        )
        return True

    def _fulfil_choice(self, outcome: Outcome, merged: dict, choice: dict) -> bool:
        """Hold a concrete off-site venue / split plan right away when inventory allows it."""
        code = choice.get("code")
        facts = apply_meeting_room_defaults(dict(merged))
        facts.update(compute_hold_window(facts))
        if code == "LARGER_VENUE":
            venue = self._pick_offsite(facts, outcome.outcome_id)
            if not venue:
                return False
            self._propose(
                outcome,
                venue,
                facts,
                updated=False,
                intro_note=f"You chose a larger venue — {venue.name} (seats {_capacity(venue)}) is free at that time.",
            )
        elif code == "SPLIT_ROOMS":
            plan = self._plan_split(facts, outcome.outcome_id)
            if not plan:
                return False
            self._propose(
                outcome,
                plan[0],
                facts,
                updated=False,
                extra_rooms=plan[1:],
                intro_note="You chose to split the group — these rooms are free at the same time.",
            )
        else:
            return False
        self._resolve_no_room_exception(outcome, f"Requester chose {code}; proposal held")
        self.admin_ops.action_requester_choice(
            outcome,
            choice_label=str(choice.get("label") or code),
            facts=dict(outcome.facts or facts),
        )
        return True

    def _resolve_no_room_exception(self, outcome: Outcome, resolution: str) -> None:
        from app.models.outcome import ExceptionRecord

        for row in self.session.exec(
            select(ExceptionRecord).where(
                ExceptionRecord.outcome_id == outcome.outcome_id,
                ExceptionRecord.exception_type == "NO_MEETING_ROOM",
                ExceptionRecord.status.in_(["OPEN", "IN_PROGRESS"]),  # type: ignore[attr-defined]
            )
        ).all():
            row.status = "RESOLVED"
            row.resolution = resolution
            row.resolved_at = utcnow()
            self.session.add(row)

    def _annotate_open_no_room_exception(
        self,
        outcome: Outcome,
        *,
        choice: dict,
        extras: list | None = None,
    ) -> None:
        from app.models.outcome import ExceptionRecord

        row = self.session.exec(
            select(ExceptionRecord).where(
                ExceptionRecord.outcome_id == outcome.outcome_id,
                ExceptionRecord.exception_type == "NO_MEETING_ROOM",
                ExceptionRecord.status == "OPEN",
            )
        ).first()
        note = f"Requester chose {choice.get('code')}: {choice.get('label')}"
        if extras:
            texts = [
                (x.get("text") if isinstance(x, dict) else str(x)) for x in extras
            ]
            texts = [t for t in texts if t]
            if texts:
                note += " | extras: " + "; ".join(texts)
        if row:
            row.description = ((row.description or "") + f"\n{note}").strip()
            opts = list(row.options or [])
            opts.append({"code": "REQUESTER_CHOICE", "label": choice.get("label"), "selected": choice.get("code")})
            row.options = opts
            self.session.add(row)
        else:
            self.engine.create_exception(
                outcome=outcome,
                exception_type="NO_MEETING_ROOM",
                title="No suitable meeting room available",
                description=note,
                options=[{"code": choice.get("code"), "label": choice.get("label"), "selected": True}],
                severity="MEDIUM",
                owner_role="OPERATOR",
            )

    def _enter_no_resource(
        self,
        outcome: Outcome,
        merged: dict,
        *,
        prior: dict,
        policy: Any,
    ) -> None:
        max_cap = self._max_room_capacity()
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
        offsite = self._pick_offsite(merged, outcome.outcome_id)
        split = self._plan_split(merged, outcome.outcome_id)
        merged["offsite_option"] = (
            {"resource_id": offsite.resource_id, "name": offsite.name, "capacity": _capacity(offsite)}
            if offsite
            else None
        )
        merged["split_option"] = [
            {"resource_id": r.resource_id, "name": r.name, "capacity": _capacity(r)} for r in split
        ] or None
        for alt in alternatives:
            if alt.get("code") == "LARGER_VENUE" and offsite:
                alt["label"] = f"{alt['label']} — {offsite.name} (seats {_capacity(offsite)}) is free"
            elif alt.get("code") == "SPLIT_ROOMS" and split:
                alt["label"] = f"{alt['label']} — {' + '.join(r.name for r in split)} are free"
        fp = requirement_fingerprint(merged)
        diagnosis = diagnose_no_resource(
            attendees=merged.get("attendees"),
            max_capacity=max_cap,
            zero_scores=zero_scores,
            busy_fits=merged.get("busy_fit_rooms"),
        )
        already_mailed = (
            (prior.get("orchestration_stage") or "").upper() == MeetingStage.NO_RESOURCE.value
            and prior.get("no_resource_fingerprint") == fp
            and not merged.get("no_resource_choice")
        )

        merged["needs_ops"] = True
        merged["auto_book_skipped"] = "no_room_available"
        merged["orchestration_stage"] = MeetingStage.NO_RESOURCE.value
        merged["outbound_required"] = "suppressed" if already_mailed else "no_resource"
        merged["last_action"] = "no_resource"
        merged["inventory_max_capacity"] = max_cap
        merged["no_resource_alternatives"] = alternatives
        merged["no_resource_fingerprint"] = fp
        merged["no_resource_diagnosis"] = diagnosis
        merged = append_decision_trace(
            merged,
            {
                "at": utcnow().isoformat(),
                "kind": "no_resource",
                "policy_version": policy.version,
                "alternatives": [a["code"] for a in alternatives],
                "max_capacity": max_cap,
                "requested_attendees": merged.get("attendees"),
                "diagnosis": diagnosis.get("primary"),
                "suppressed_duplicate": already_mailed,
            },
        )
        self._save_facts(outcome, merged)

        # Upsert open exception once
        from app.models.outcome import ExceptionRecord

        existing = self.session.exec(
            select(ExceptionRecord).where(
                ExceptionRecord.outcome_id == outcome.outcome_id,
                ExceptionRecord.exception_type == "NO_MEETING_ROOM",
                ExceptionRecord.status == "OPEN",
            )
        ).first()
        if not existing:
            self.engine.create_exception(
                outcome=outcome,
                exception_type="NO_MEETING_ROOM",
                title="No suitable meeting room available",
                description=(
                    diagnosis.get("line")
                    or f"No available room met capacity/equipment for {merged.get('attendees')} attendees."
                ),
                options=[
                    {"code": a["code"], "label": a["label"]}
                    for a in alternatives
                    if a.get("code") != "REVIEW_NEAR_MISS"
                ],
                severity="MEDIUM",
                owner_role="OPERATOR",
            )

        if already_mailed:
            self.comms.record_suppressed(
                outcome=outcome,
                reason="duplicate_no_resource_fingerprint",
                detail={"fingerprint": fp, "diagnosis": diagnosis.get("primary")},
            )
            return

        if outcome.requester_email:
            name = resolve_requester_name(self.session, outcome=outcome)
            greet = format_outbound_greeting(name)
            alt_lines = "\n".join(
                f"- {a['label']}" for a in alternatives if a.get("code") != "REVIEW_NEAR_MISS"
            )
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="INFORMATION_ONLY",
                body=(
                    f"{greet}\n\n"
                    f"{diagnosis.get('line')}\n\n"
                    "Please reply with one of these options:\n"
                    f"{alt_lines}\n\n"
                    f"Case: {outcome.case_reference}"
                ),
                recipients=[outcome.requester_email],
                action_label="NO ROOM AVAILABLE",
                subject_hint=outcome.summary or "No room available",
                suppress_fingerprint=f"no_resource:{fp}",
            )
        self.admin_ops.action_no_resource(
            outcome,
            diagnosis=str(diagnosis.get("line") or ""),
            facts=dict(outcome.facts or merged),
        )

    def _handle_post_booking(
        self,
        outcome: Outcome,
        merged: dict,
        extraction: Optional[ExtractionResult],
        prior: Optional[dict] = None,
    ) -> None:
        prior = prior or {}
        if prior.get("booked_room") and search_relevant_changed(prior, merged):
            self._rebook_after_change(outcome, merged, prior)
            return
        watch = (
            "catering",
            "hybrid_av",
            "special_access",
            "location_preference",
            "meeting_type",
            "dietary",
            "guest_vehicles",
            "vehicle_numbers",
            "external_visitors",
            "visitor_details",
        )
        deltas = {}
        for key in watch:
            new = merged.get(key)
            if new in (None, ""):
                continue
            if new != prior.get(key):
                deltas[key] = new
        prior_open = prior.get("open_requests") or []
        now_open = merged.get("open_requests") or []
        if len(now_open) > len(prior_open):
            deltas["open_requests"] = now_open[len(prior_open) :]
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
                        f"{format_outbound_greeting(name)}\n\n"
                        "Thanks — we’ve noted your additional request against the confirmed booking.\n\n"
                        + "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in deltas.items())
                        + f"\n\nCase: {outcome.case_reference}"
                    ),
                    recipients=[outcome.requester_email],
                    action_label="UPDATE NOTED",
                )
            if "catering" in deltas and catering_needed(merged) and not catering_needed(prior):
                self._requote_catering(outcome)
            if deltas.get("open_requests"):
                self.admin_ops.notify(
                    outcome,
                    kind="decision",
                    headline="New asks after booking",
                    detail="; ".join(
                        (x.get("text") if isinstance(x, dict) else str(x)) for x in deltas["open_requests"]
                    ),
                    fingerprint=f"post_asks:{outcome.outcome_id}:{len(merged.get('open_requests') or [])}",
                    facts=dict(outcome.facts or merged),
                )
        else:
            merged["last_action"] = "monitoring"
            merged["outbound_required"] = "suppressed"
            self._save_facts(outcome, merged)
            self.comms.record_suppressed(outcome=outcome, reason="no_new_facts_post_booking")

    def _rebook_after_change(self, outcome: Outcome, merged: dict, prior: dict) -> None:
        """Headcount / date / time / equipment changed after booking: keep, move, or escalate."""
        merged = apply_meeting_room_defaults(merged)
        merged = apply_internal_vc_policy(merged)
        merged.update(compute_hold_window(merged))
        booked = dict(merged.get("booked_room") or {})
        window = meeting_window(merged)
        needed = _int(merged.get("attendees"))
        parts = booked.get("rooms") or ([booked] if booked.get("resource_id") else [])
        current = [self.session.get(Resource, p.get("resource_id")) for p in parts if p.get("resource_id")]
        current = [r for r in current if r is not None]

        still_fits = bool(current) and all(
            self.bookings.is_free(r, window, exclude_outcome_id=outcome.outcome_id) for r in current
        )
        if still_fits:
            if len(current) == 1:
                still_fits = score_meeting_room(current[0], merged)[0] > 0
            else:
                still_fits = sum(_capacity(r) for r in current) >= needed
        if not current and booked.get("external_venue"):
            still_fits = None  # off-site outside inventory — ops must re-confirm

        changed = {
            k: merged.get(k)
            for k in ("attendees", "date", "preferred_time", "end_time", "duration_hours", "hybrid_av",
                      "presentation_display", "location_preference")
            if merged.get(k) != prior.get(k)
        }
        change_lines = [f"- {k.replace('_', ' ')}: {v}" for k, v in changed.items()]
        history = list(merged.get("post_booking_requests") or [])
        history.append({"changed": changed, "at": utcnow().isoformat()})
        merged["post_booking_requests"] = history
        name = resolve_requester_name(self.session, outcome=outcome)
        greet = format_outbound_greeting(name)

        if still_fits:
            keep: set[str] = set()
            for r in current:
                row = self.bookings.confirm(
                    outcome_id=outcome.outcome_id, room_name=r.name, window=window,
                    resource_id=r.resource_id, attributes={"updated_after_booking": True}, keep=keep,
                )
                keep.add(row.booking_id)
            booked.update(self._slot_fields(merged))
            merged["booked_room"] = booked
            merged["last_action"] = "post_booking_updated_same_room"
            merged["orchestration_stage"] = MeetingStage.MONITORING.value
            merged["needs_ops"] = False
            self._save_facts(outcome, merged)
            self._send(outcome, "BOOKING UPDATED", "INFORMATION_ONLY", [
                f"{greet}\n\nDone — {booked.get('name')} still works for the change, so your booking is updated.",
                "\n".join(change_lines),
            ])
        else:
            room = self._pick_room(merged, outcome.outcome_id) if still_fits is False else None
            if room:
                old_name = booked.get("name")
                row = self.bookings.confirm(
                    outcome_id=outcome.outcome_id, room_name=room.name, window=window,
                    resource_id=room.resource_id, attributes={"moved_from": old_name},
                )
                booked = {
                    **booked,
                    **self._slot_fields(merged),
                    "resource_id": room.resource_id,
                    "name": room.name,
                    "capacity": _capacity(room),
                    "booking_id": row.booking_id,
                    "moved_from": old_name,
                }
                booked.pop("rooms", None)
                booked.pop("split", None)
                merged["booked_room"] = booked
                merged["last_action"] = "post_booking_moved_room"
                merged["orchestration_stage"] = MeetingStage.MONITORING.value
                merged["needs_ops"] = False
                self._save_facts(outcome, merged)
                self._send(outcome, "ROOM CHANGED", "INFORMATION_ONLY", [
                    f"{greet}\n\n{old_name} no longer fits after your change, so we moved you to {room.name} "
                    f"(seats {_capacity(room)}).",
                    "\n".join(change_lines),
                ])
                self.admin_ops.notify(
                    outcome, kind="update", headline=f"Booking moved — {old_name} → {room.name}",
                    fingerprint=f"moved:{outcome.outcome_id}:{row.booking_id}", facts=dict(outcome.facts or merged),
                )
            else:
                merged["needs_ops"] = True
                merged["last_action"] = "post_booking_change_needs_ops"
                merged["orchestration_stage"] = MeetingStage.MONITORING.value
                self._save_facts(outcome, merged)
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="POST_BOOKING_CHANGE",
                    title="Change after booking needs a new room",
                    description=f"{booked.get('name')} no longer fits: " + "; ".join(
                        f"{k}={v}" for k, v in changed.items()
                    ),
                    severity="MEDIUM",
                    owner_role="OPERATOR",
                )
                self._send(outcome, "CHANGE RECEIVED", "INFORMATION_ONLY", [
                    f"{greet}\n\nWe've got your change. {booked.get('name')} can't take it and no other room "
                    "is free for that, so our ops team is on it. Your current booking stays in place until then.",
                    "\n".join(change_lines),
                ])
                self.admin_ops.notify(
                    outcome, kind="decision", headline="Change after booking — no room fits",
                    detail="Reply with a room/venue to move them, or tell us what to offer the requester.",
                    fingerprint=f"post_change:{outcome.outcome_id}:{requirement_fingerprint(merged)}",
                    facts=dict(outcome.facts or merged),
                )

        if catering_needed(merged) and (
            merged.get("attendees") != prior.get("attendees") or not catering_needed(prior)
        ):
            self._requote_catering(outcome)
        self._sync_conversation_facts(outcome)

    def _slot_fields(self, facts: dict) -> dict:
        return {
            "attendees": facts.get("attendees"),
            "date": facts.get("date"),
            "start": facts.get("preferred_time") or facts.get("time_window"),
            "end": facts.get("end_time"),
            "duration_hours": facts.get("duration_hours"),
            "hold_start": facts.get("hold_start"),
            "hold_end": facts.get("hold_end"),
            "fingerprint": requirement_fingerprint(facts),
        }

    def _send(self, outcome: Outcome, label: str, ctype: str, blocks: list[str]) -> None:
        if not outcome.requester_email:
            return
        body = "\n\n".join(b for b in blocks if b) + f"\n\nCase: {outcome.case_reference}"
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=ctype,
            body=body,
            recipients=[outcome.requester_email],
            action_label=label,
        )

    def _requote_catering(self, outcome: Outcome) -> None:
        from app.models.outcome import Approval

        for approval in self.session.exec(
            select(Approval).where(
                Approval.outcome_id == outcome.outcome_id,
                Approval.approval_type == "CATERING_SPEND",
                Approval.decision == "PENDING",
            )
        ).all():
            approval.decision = "SUPERSEDED"
            approval.decided_at = utcnow()
            self.session.add(approval)
        facts = dict(outcome.facts or {})
        facts.pop("catering_assigned", None)
        self._save_facts(outcome, facts)
        self._run_catering(outcome, facts)

    def _maybe_auto_book_low_risk(self, outcome: Outcome) -> None:
        facts = dict(outcome.facts or {})
        score = float((facts.get("recommended_room") or {}).get("score") or 0)
        if not facts.get("pending_confirmation") or not facts.get("proposed_room"):
            return
        proposal = facts.get("proposed_room") or {}
        if proposal.get("split") or proposal.get("external_venue"):
            return
        if not is_low_risk_auto_bookable(facts, score):
            return
        facts["auto_booked_low_risk"] = True
        facts["booking_confirmed"] = True
        facts["orchestration_stage"] = MeetingStage.AUTO_BOOKED.value
        facts["last_action"] = "auto_booked"
        self._save_facts(outcome, facts)
        self._finalize_booking(outcome, actor="system_low_risk")

    def _pick_room(self, facts: dict, outcome_id: Optional[str] = None) -> Optional[Resource]:
        """Best-scoring room that is free for this meeting's time window."""
        rooms = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "MEETING_ROOM",
            )
        ).all()
        window = meeting_window(facts)
        scored = []
        busy_fits: list[str] = []
        for room in rooms:
            score, reasons = score_meeting_room(room, facts)
            if score <= 0:
                continue
            if not self.bookings.is_free(room, window, exclude_outcome_id=outcome_id):
                busy_fits.append(room.name)
                continue
            scored.append((score, room, reasons))
        facts["busy_fit_rooms"] = busy_fits
        if window:
            facts["meeting_window"] = {"start": window[0].isoformat(), "end": window[1].isoformat()}
        if not scored:
            return None
        scored.sort(key=lambda x: (-x[0], (x[1].attributes or {}).get("capacity") or 999))
        best = scored[0]
        facts["room_scores"] = [
            {"name": r.name, "score": s, "reasons": rs} for s, r, rs in scored[:5]
        ]
        facts["recommended_room"] = {"name": best[1].name, "score": best[0], "reasons": best[2]}
        return best[1]

    def _proposed_room_taken(self, outcome: Outcome, facts: dict) -> bool:
        proposal = facts.get("proposed_room") or {}
        ids = [r.get("resource_id") for r in proposal.get("rooms") or []] or [proposal.get("resource_id")]
        window = meeting_window(facts)
        for rid in ids:
            room = self.session.get(Resource, rid) if rid else None
            if room and not self.bookings.is_free(room, window, exclude_outcome_id=outcome.outcome_id):
                return True
        return False

    def _free_resources(self, rtype: str, facts: dict, outcome_id: Optional[str]) -> list[Resource]:
        rows = self.session.exec(
            select(Resource).where(Resource.tenant_id == self.tenant_id, Resource.type == rtype)
        ).all()
        return self.bookings.free_rooms(rows, meeting_window(facts), exclude_outcome_id=outcome_id)

    def _pick_offsite(self, facts: dict, outcome_id: Optional[str] = None) -> Optional[Resource]:
        """Smallest free off-site venue that seats the whole group."""
        needed = _int(facts.get("attendees"))
        fits = [r for r in self._free_resources("OFFSITE_VENUE", facts, outcome_id) if _capacity(r) >= needed]
        return min(fits, key=_capacity) if fits else None

    def _plan_split(self, facts: dict, outcome_id: Optional[str] = None, max_rooms: int = 3) -> list[Resource]:
        """Fewest free rooms (same floor preferred) whose seats add up to the headcount."""
        needed = _int(facts.get("attendees"))
        if needed <= 0:
            return []
        usable = [
            r
            for r in self._free_resources("MEETING_ROOM", facts, outcome_id)
            if _capacity(r) > 0 and score_meeting_room(r, {**facts, "attendees": _capacity(r)})[0] > 0
        ]

        def greedy(pool: list[Resource]) -> list[Resource]:
            picked: list[Resource] = []
            for room in sorted(pool, key=_capacity, reverse=True):
                if sum(_capacity(r) for r in picked) >= needed:
                    break
                picked.append(room)
            ok = len(picked) >= 2 and len(picked) <= max_rooms and sum(_capacity(r) for r in picked) >= needed
            return picked if ok else []

        floors: dict[str, list[Resource]] = {}
        for room in usable:
            floors.setdefault(str((room.attributes or {}).get("floor") or ""), []).append(room)
        options = [p for p in (greedy(pool) for pool in floors.values()) if p]
        if options:
            return min(options, key=len)
        return greedy(usable)

    def cancel_case(self, outcome: Outcome, *, actor: str, reason: str = "") -> None:
        """Release the room, stop open work, tell the requester and ops."""
        from app.audit.service import AuditService
        from app.core.enums import AuditAction, OutcomeStatus
        from app.models.outcome import Approval, ExceptionRecord

        facts = dict(outcome.facts or {})
        room_name = (facts.get("booked_room") or facts.get("proposed_room") or {}).get("name")
        released = self.bookings.release_for_outcome(outcome.outcome_id, status="CANCELLED")
        facts.update(
            {
                "orchestration_stage": MeetingStage.CANCELLED.value,
                "operational_status": "CANCELLED",
                "pending_confirmation": False,
                "needs_ops": False,
                "last_action": f"cancelled_by:{actor}",
                "cancelled_at": utcnow().isoformat(),
                "cancel_reason": (reason or "")[:300],
                "outbound_required": "cancel_ack",
            }
        )
        self._save_facts(outcome, facts)
        outcome.status = OutcomeStatus.CANCELLED.value
        self.session.add(outcome)

        for task in self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all():
            if task.status not in {"VERIFIED", "CLOSED", "CANCELLED"}:
                task.status = "CANCELLED"
                task.resolution = "Case cancelled"
                self.session.add(task)
        for approval in self.session.exec(
            select(Approval).where(Approval.outcome_id == outcome.outcome_id, Approval.decision == "PENDING")
        ).all():
            approval.decision = "CANCELLED"
            approval.decided_at = utcnow()
            self.session.add(approval)
        for exc in self.session.exec(
            select(ExceptionRecord).where(
                ExceptionRecord.outcome_id == outcome.outcome_id,
                ExceptionRecord.status == "OPEN",
            )
        ).all():
            exc.status = "RESOLVED"
            exc.resolution = f"Case cancelled by {actor}"
            exc.resolved_at = utcnow()
            self.session.add(exc)

        AuditService(self.session).record(
            tenant_id=self.tenant_id,
            actor=actor,
            action=AuditAction.OUTCOME_UPDATED,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"status": "CANCELLED", "released_bookings": released, "reason": reason[:300]},
            correlation_id=outcome.outcome_id,
        )

        if outcome.requester_email:
            name = resolve_requester_name(self.session, outcome=outcome)
            by_ops = not actor.startswith("requester")
            lines = [
                "Your meeting-room request has been cancelled"
                + (" by our ops team" if by_ops else "")
                + "."
            ]
            if by_ops and reason:
                lines.append(f"Reason: {reason}")
            if room_name:
                lines.append(f"{room_name} has been released.")
            lines.append("If you need a room again, just send a new request.")
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="INFORMATION_ONLY",
                body=f"{format_outbound_greeting(name)}\n\n" + "\n\n".join(lines) + f"\n\nCase: {outcome.case_reference}",
                recipients=[outcome.requester_email],
                action_label="CANCELLED",
                subject_hint=outcome.summary or "Request cancelled",
                suppress_fingerprint=f"cancel:{outcome.outcome_id}",
            )
        self.admin_ops.notify(
            outcome,
            kind="update",
            headline=f"Case cancelled by {'requester' if actor.startswith('requester') else 'ops'}",
            detail=(f"Released: {room_name}. " if room_name else "") + (f"Reason: {reason}" if reason else ""),
            fingerprint=f"cancelled:{outcome.outcome_id}",
            facts=dict(outcome.facts or facts),
        )
        self._sync_conversation_facts(outcome)

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
            f"{format_outbound_greeting(name)}\n\n"
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
        self.admin_ops.action_needs_review(outcome, reason=reason, facts=facts)

    def _propose(
        self,
        outcome: Outcome,
        room: Resource,
        facts: dict,
        *,
        updated: bool,
        extra_rooms: Optional[list[Resource]] = None,
        intro_note: Optional[str] = None,
    ) -> None:
        try:
            needed = int(facts.get("attendees") or 1)
        except (TypeError, ValueError):
            needed = 1
        rooms = [room, *(extra_rooms or [])]
        offsite = room.type == "OFFSITE_VENUE"
        display_name = " + ".join(r.name for r in rooms)
        proposal = {
            "resource_id": room.resource_id if len(rooms) == 1 else None,
            "name": display_name,
            "capacity": sum(_capacity(r) for r in rooms) if len(rooms) > 1 else (room.attributes or {}).get("capacity"),
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
        window = meeting_window(facts)
        holds = [
            self.bookings.hold(
                outcome_id=outcome.outcome_id,
                room_name=r.name,
                window=window,
                resource_id=r.resource_id,
                is_offsite=r.type == "OFFSITE_VENUE",
                release_prior=i == 0,
            )
            for i, r in enumerate(rooms)
        ]
        hold = holds[0]
        if len(rooms) > 1:
            proposal["split"] = True
            proposal["rooms"] = [
                {"resource_id": r.resource_id, "name": r.name, "capacity": _capacity(r), "booking_id": h.booking_id}
                for r, h in zip(rooms, holds)
            ]
        if offsite:
            proposal["external_venue"] = True
        proposal["booking_id"] = hold.booking_id
        proposal["hold_expires_at"] = hold.hold_expires_at.isoformat() if hold.hold_expires_at else None
        if hold.starts_at:
            proposal["slot_start"] = hold.starts_at.isoformat()
            proposal["slot_end"] = hold.ends_at.isoformat() if hold.ends_at else None
        facts = {
            **facts,
            "proposed_room": proposal,
            "pending_confirmation": True,
            "needs_ops": False,
            "checklist_missing": [],
            "execution_plan": self._execution_plan(facts, display_name),
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
        replaced = facts.pop("replaced_room_note", None)
        if replaced:
            intro = f"{replaced} Here’s another room that fits.\n\n"
            self._save_facts(outcome, facts)
        if intro_note:
            intro = f"{intro_note}\n\n"
        if len(rooms) > 1:
            room_line = "Proposed rooms (group split across them): " + ", ".join(
                f"{r.name} (seats {_capacity(r)})" for r in rooms
            )
        elif offsite:
            room_line = f"Proposed venue (off-site): {room.name}"
        else:
            room_line = f"Proposed room: {room.name}"
        confirmed, unconfirmed = requirement_email_sections(facts)
        req_block = "\n".join(f"- {line}" for line in confirmed) or "- (none confirmed yet)"
        unc_block = ""
        if unconfirmed:
            unc_block = "\n\nNot confirmed yet:\n" + "\n".join(f"- {line}" for line in unconfirmed)
        score = float((facts.get("recommended_room") or {}).get("score") or 0)
        # Low-risk path auto-books immediately — skip the confirm ask email
        special = len(rooms) > 1 or offsite
        if outcome.requester_email and (special or not is_low_risk_auto_bookable(facts, score)):
            name = resolve_requester_name(self.session, outcome=outcome)
            body = (
                f"{format_outbound_greeting(name)}\n\n"
                f"{intro}"
                f"{room_line}\n"
                f"Case: {outcome.case_reference}\n\n"
                f"Here’s what we have as confirmed / extracted:\n{req_block}"
                f"{unc_block}\n\n"
                "Should we confirm this booking?\n"
                'Reply "confirm" (or "yes") to lock it in.\n'
                f"We're holding the room for you for {_hold_hours_label()}; after that it's released for others.\n"
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
        self.admin_ops.fyi_proposed(outcome, room_name=display_name, facts=dict(outcome.facts or facts))
        self._sync_conversation_facts(outcome)
        logger.info("meeting_room_proposed", outcome_id=outcome.outcome_id, room=display_name, updated=updated)

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
        window = meeting_window(facts)
        parts = proposal.get("rooms") or []
        if parts:
            kept: set[str] = set()
            for part in parts:
                row = self.bookings.confirm(
                    outcome_id=outcome.outcome_id,
                    room_name=str(part.get("name")),
                    window=window,
                    resource_id=part.get("resource_id"),
                    attributes={"confirmed_by": actor, "split": True},
                    keep=kept,
                )
                kept.add(row.booking_id)
                part["booking_id"] = row.booking_id
            booking["rooms"] = parts
            booking["booking_ids"] = sorted(kept)
        else:
            row = self.bookings.confirm(
                outcome_id=outcome.outcome_id,
                room_name=str(booking.get("name") or "room"),
                window=window,
                resource_id=room.resource_id if room else None,
                is_offsite=bool(proposal.get("external_venue")) or room is None,
                attributes={"confirmed_by": actor},
            )
        booking["booking_id"] = row.booking_id
        self._resolve_no_room_exception(outcome, f"Booked {booking.get('name')} ({actor})")
        booking.pop("hold_expires_at", None)
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
                f"{format_outbound_greeting(name)}\n\n"
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
                f"{format_outbound_greeting(name)}\n\n"
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
        self.admin_ops.fyi_booked(
            outcome,
            room_name=str(booking.get("name") or "room"),
            facts=dict(outcome.facts or facts),
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
        facts["av_plan"] = {
            "platform": "Microsoft Teams" if "team" in str(facts.get("hybrid_av") or "").lower() else "Video conference",
            "test_required": True,
        }
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)
        self._complete_task(outcome, "AV_TEST", "system", "AV plan ready")

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
        from app.core.config import get_settings
        from app.services.catering import catering_quote

        quote = catering_quote(self.session, self.tenant_id, headcount)
        facts["catering_quote"] = quote
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)

        limit = float(get_settings().catering_auto_approve_limit or 0)
        amount = quote.get("amount_ex_tax")
        if limit > 0 and amount is not None and amount <= limit and quote.get("vendor"):
            facts["catering_auto_approved"] = True
            self._save_facts(outcome, {**(outcome.facts or {}), **facts})
            self.on_catering_approved(outcome)
            return

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
        facts["vendor_sla"] = {"acceptance_minutes": 30, "status": "PENDING_ASSIGNMENT"}
        outcome.facts = {**(outcome.facts or {}), **facts}
        self.session.add(outcome)
        self.admin_ops.action_approval(outcome, approval_type="CATERING_SPEND", facts=facts)

    def on_catering_approved(self, outcome: Outcome) -> None:
        facts = dict(outcome.facts or {})
        quote = facts.get("catering_quote") or {}
        facts["vendor_sla"] = {
            **(facts.get("vendor_sla") or {}),
            "status": "ASSIGNED",
            "assigned_at": utcnow().isoformat(),
            "acceptance_due_minutes": 30,
        }
        facts["catering_assigned"] = True
        self._save_facts(outcome, facts)
        self._complete_task(outcome, "CATERING_APPROVAL", "system", "Catering spend approved")
        self._complete_task(
            outcome,
            "VENDOR_CATERING",
            "system",
            f"Assigned {quote.get('vendor') or 'caterer (ops to confirm)'}"
            + (f" for {quote.get('currency') or 'INR'} {quote['amount_ex_tax']}" if quote.get("amount_ex_tax") else ""),
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
        room = orch._pick_room(facts, outcome.outcome_id)
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
