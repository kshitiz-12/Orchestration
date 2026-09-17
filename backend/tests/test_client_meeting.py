"""Client meeting outcome — threading, propose/confirm, catering, parking."""

from sqlmodel import Session, select

from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import Conversation
from app.models.org import Resource, Tenant
from app.models.outcome import Approval, Communication, Outcome, Requirement, Task
from app.schemas.ai import ExtractionResult
from app.services.meeting_room import is_new_meeting_request, meeting_room_gaps


def _tenant(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def _core(**extra):
    base = {
        "attendees": 16,
        "date": "22 September 2026",
        "preferred_time": "2:00 PM",
        "end_time": "5:00 PM",
        "duration_hours": 3.0,
        "meeting_type": "client review",
        "hybrid_av": "yes — video/AV needed",
        "presentation_display": "yes",
        "location_preference": "Corporate Office",
        "catering": "high tea",
        "dietary": "12 vegetarian, 4 non-vegetarian",
        "special_access": "required",
        "external_visitors": 6,
        "visitor_details": "6 visitors from ABC Industries",
        "guest_vehicles": 3,
        "vehicle_numbers": "DL01AB1234, HR26CD5678, UP16EF9012",
        "confidentiality": "business confidential",
    }
    base.update(extra)
    return base


def test_new_request_detection_same_thread():
    assert (
        is_new_meeting_request(
            text="Please also book another meeting",
            new_facts={"date": "24 September"},
            existing_facts={"date": "22 September", "pending_confirmation": True},
            existing_status="ACTIVE",
        )
        == "new"
    )
    assert (
        is_new_meeting_request(
            text="confirm",
            new_facts={},
            existing_facts={"date": "22 September", "pending_confirmation": True},
            existing_status="ACTIVE",
        )
        == "update"
    )


def test_conditional_gaps_for_visitors_and_dietary():
    gaps = meeting_room_gaps(
        {
            "attendees": 16,
            "date": "22 September",
            "preferred_time": "2 PM",
            "duration_hours": 3,
            "meeting_type": "client review",
            "location_preference": "Corporate Office",
            "external_visitors": 6,
            "catering": "high tea",
            "guest_vehicles": 3,
        }
    )
    fields = {g["field"] for g in gaps}
    assert "visitor_details" in fields
    assert "dietary" in fields
    assert "vehicle_numbers" in fields


def test_minimal_request_date_only_does_not_book(session: Session):
    """Date-only email → register + wait; no room booked until clarification answered."""
    from app.services.meeting_room import default_meeting_room_questions, is_low_risk_auto_bookable

    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-minimal",
        requester_email="arun.kumar@company.com",
        subject="Meeting room required for 18 September",
    )
    session.add(conv)
    session.commit()

    incomplete = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="Please book a meeting room for 18 September",
            entities={"date": "18 September 2026"},
            missing_information=[],
            confidence=0.99,
            reason="minimal",
        ),
        requester_email="arun.kumar@company.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_min_1",
        context={},
    )
    assert incomplete.facts.get("registration_ack_sent")
    assert not incomplete.facts.get("booked_room")
    assert not incomplete.facts.get("proposed_room")
    assert incomplete.facts.get("orchestration_stage") == "AWAITING_REQUIREMENTS"
    assert "attendees" in (incomplete.facts.get("checklist_missing") or [])
    qs = default_meeting_room_questions(incomplete.facts or {})
    assert any("Start time" in q for q in qs)
    assert any("participants" in q.lower() for q in qs)

    complete = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="11-12, 7 people, internal finance review",
            entities={
                **(incomplete.facts or {}),
                "date": "18 September 2026",
                "preferred_time": "11:00 AM",
                "end_time": "12:00 PM",
                "duration_hours": 1,
                "attendees": 7,
                "location_preference": "Corporate Office",
                "meeting_type": "internal finance review",
                "presentation_display": "yes",
                "external_visitors": 0,
                "catering": "none",
                "special_access": "none",
            },
            missing_information=[],
            confidence=0.95,
            reason="clarified",
        ),
        requester_email="arun.kumar@company.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_min_2",
        context={},
    )
    assert complete.facts.get("booked_room"), "low-risk internal should auto-book"
    assert complete.facts.get("auto_booked_low_risk")
    assert complete.facts.get("hybrid_av") == "no"
    assumptions = complete.facts.get("policy_assumptions") or []
    assert any(a.get("code") == "MP-INT-006" for a in assumptions)
    assert (complete.facts.get("setup_buffer_minutes") or "") == "10"
    assert is_low_risk_auto_bookable(complete.facts)
    mails = session.exec(
        select(Communication).where(Communication.outcome_id == complete.outcome_id)
    ).all()
    assert any("BOOKING CONFIRMED" in (m.subject or "") for m in mails)
    assert not complete.facts.get("visitors")
    assert not complete.facts.get("catering_quote")
    reqs = {
        r.code: r.applicability
        for r in session.exec(
            select(Requirement).where(Requirement.outcome_id == complete.outcome_id)
        ).all()
    }
    assert reqs.get("VISITORS") == "NOT_APPLICABLE"
    assert reqs.get("CATERING") == "NOT_APPLICABLE"
    assert reqs.get("PARKING") == "NOT_APPLICABLE"

def test_client_meeting_propose_confirm_and_parallel_tracks(session: Session):
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-client-mtg",
        requester_email="sales.employee@acme.demo",
        subject="Client review meeting",
    )
    session.add(conv)
    session.commit()

    outcome = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="Client review meeting 22 Sep 2-5pm",
            entities=_core(),
            missing_information=[],
            confidence=0.95,
            reason="complete",
        ),
        requester_email="sales.employee@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_mtg_1",
        context={},
    )
    assert outcome.facts.get("registration_ack_sent")
    assert outcome.facts.get("pending_confirmation")
    assert outcome.facts.get("proposed_room")
    assert outcome.facts.get("hold_start")
    mails = session.exec(
        select(Communication).where(Communication.outcome_id == outcome.outcome_id)
    ).all()
    assert any("CONFIRM BOOKING" in (c.subject or "") for c in mails)
    assert not any("REQUEST REGISTERED" in (c.subject or "") for c in mails)
    confirm = next(c for c in mails if "CONFIRM BOOKING" in (c.subject or ""))
    assert "Dear" in (confirm.body or "")
    assert "requester" not in (confirm.body or "").lower().split("dear", 1)[-1][:40]

    confirmed = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="confirm",
            entities={**outcome.facts, "booking_confirmed": True},
            missing_information=[],
            confidence=0.95,
            reason="confirm",
        ),
        requester_email="sales.employee@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_mtg_2",
        context={},
    )
    assert confirmed.facts.get("booked_room")
    assert confirmed.facts.get("visitors")
    assert len(confirmed.facts.get("parking_allocation") or []) >= 3
    assert confirmed.facts.get("catering_quote")
    assert confirmed.facts.get("execution_plan")
    approvals = session.exec(
        select(Approval).where(Approval.outcome_id == confirmed.outcome_id)
    ).all()
    assert any(a.approval_type == "CATERING_SPEND" for a in approvals)


def test_new_meeting_on_same_thread_creates_second_outcome(session: Session):
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-two-bookings",
        requester_email="employee1@acme.demo",
    )
    session.add(conv)
    session.commit()

    first = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="Room for 4 tomorrow",
            entities={
                "attendees": 4,
                "date": "22 September",
                "preferred_time": "10 am",
                "duration_hours": 2,
                "meeting_type": "workshop",
                "location_preference": "Corporate Office",
            },
            missing_information=[],
            confidence=0.9,
            reason="first",
        ),
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_a",
        context={},
    )
    # Confirm first so it's booked but still open (ops not closed)
    first = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="confirm",
            entities={**first.facts, "booking_confirmed": True},
            missing_information=[],
            confidence=0.95,
            reason="confirm",
        ),
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_b",
        context={},
    )
    second = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="new meeting on 24 September",
            entities={
                "attendees": 5,
                "date": "24 September",
                "preferred_time": "3 pm",
                "duration_hours": 1,
                "meeting_type": "workshop",
                "location_preference": "Corporate Office",
                "new_request": True,
            },
            missing_information=[],
            confidence=0.9,
            reason="new meeting",
        ),
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_c",
        context={},
    )
    outcomes = session.exec(
        select(Outcome).where(Outcome.conversation_id == conv.conversation_id)
    ).all()
    assert len(outcomes) == 2
    assert second.outcome_id != first.outcome_id
    assert second.facts.get("date") == "24 September"


def test_employee_satisfied_closes_operational(session: Session):
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-satisfied",
        requester_email="employee2@acme.demo",
    )
    session.add(conv)
    session.commit()
    o = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="simple room",
            entities={
                "attendees": 4,
                "date": "tomorrow",
                "preferred_time": "11 am",
                "duration_hours": 1,
                "meeting_type": "workshop",
                "location_preference": "Corporate Office",
                "catering": "none",
            },
            missing_information=[],
            confidence=0.9,
            reason="x",
        ),
        requester_email="employee2@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_s1",
        context={},
    )
    o = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="confirm",
            entities={**o.facts, "booking_confirmed": True},
            missing_information=[],
            confidence=0.95,
            reason="c",
        ),
        requester_email="employee2@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_s2",
        context={},
    )
    o = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="satisfied thank you",
            entities={**o.facts, "employee_satisfied": True},
            missing_information=[],
            confidence=0.95,
            reason="satisfied",
        ),
        requester_email="employee2@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_s3",
        context={},
    )
    assert (o.facts or {}).get("operational_status") == "CLOSED"


def test_oversize_headcount_is_no_resource_and_emails(session: Session):
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-no-fit",
        requester_email="big.team@company.com",
        subject="All-hands room",
    )
    session.add(conv)
    session.commit()
    outcome = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="80 people all hands",
            entities={
                "attendees": 80,
                "date": "22 September 2026",
                "preferred_time": "2:00 PM",
                "end_time": "5:00 PM",
                "duration_hours": 3.0,
                "meeting_type": "internal meeting",
                "location_preference": "Corporate Office",
                "presentation_display": "yes",
                "catering": "none",
                "external_visitors": 0,
            },
            missing_information=[],
            confidence=0.95,
            reason="complete",
        ),
        requester_email="big.team@company.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_nofit",
        context={},
    )
    assert outcome.facts.get("orchestration_stage") == "NO_RESOURCE"
    assert not outcome.facts.get("booked_room")
    assert not outcome.facts.get("proposed_room")
    assert (outcome.facts.get("inventory_max_capacity") or 0) < 80
    mails = session.exec(
        select(Communication).where(Communication.outcome_id == outcome.outcome_id)
    ).all()
    assert any("NO ROOM AVAILABLE" in (m.subject or "") for m in mails)
