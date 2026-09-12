from sqlmodel import Session, select

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.engine.outcome_engine import OutcomeEngine
from app.engine.pipeline import ProcessingPipeline
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import Conversation, RawEmailEvent
from app.models.org import Invoice, Tenant
from app.models.outcome import ExceptionRecord, Outcome, Task, VendorIssue
from app.schemas.ai import ExtractionResult, ExtractedIssue, MissingInformation
from app.services.intake import IntakeService


def _tenant(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def test_incomplete_joining_email_clarification_no_duplicate(session: Session):
    tid = _tenant(session)
    intake = IntakeService(session, tid)
    r1 = intake.ingest(
        message_id="msg-join-1",
        thread_id="thread-join-1",
        sender="hr@acme.demo",
        recipients=["orchestration@prototype.local"],
        subject="New joiner starting soon",
        body_text="Please arrange workplace readiness for a new employee joining tomorrow.",
        source="API",
    )
    assert r1["status"] == "queued"
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))
    result = pipeline.process_event(r1["event_id"])
    assert result["status"] in {"clarification_sent", "orchestrated", "human_review"}
    outcomes = session.exec(select(Outcome)).all()
    assert len(outcomes) == 1
    case_id = outcomes[0].outcome_id

    # Reply in same thread with missing info
    r2 = intake.ingest(
        message_id="msg-join-2",
        thread_id="thread-join-1",
        sender="hr@acme.demo",
        recipients=["orchestration@prototype.local"],
        subject="Re: New joiner",
        body_text="Employee name is Riya Shah, department Engineering, manager Priya Manager, hybrid work model.",
        source="API",
    )
    pipeline.process_event(r2["event_id"])
    outcomes2 = session.exec(select(Outcome)).all()
    assert len(outcomes2) == 1
    assert outcomes2[0].outcome_id == case_id


def test_no_permanent_seat_blocks_only_seat_task(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="ONBOARDING",
        summary="New joiner — no permanent seat",
        entities={"employee_name": "Riya Shah", "joining_date": "2026-04-01", "permanent_seat_available": False},
        issues=[ExtractedIssue(issue_type="NO_PERMANENT_SEAT", summary="No seat", severity="HIGH")],
        missing_information=[],
        confidence=0.92,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-seat", requester_email="hr@acme.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="hr@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_test",
        context={"available_seats_count": 0},
    )
    tasks = session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
    seat = next(t for t in tasks if t.code == "SEAT_PERMANENT")
    laptop = next(t for t in tasks if t.code == "LAPTOP")
    assert seat.is_blocked is True
    assert laptop.is_blocked is False
    assert laptop.status in {"ASSIGNED", "NOT_STARTED"}
    excs = session.exec(select(ExceptionRecord).where(ExceptionRecord.outcome_id == outcome.outcome_id)).all()
    assert any(e.exception_type == "NO_PERMANENT_SEAT" for e in excs)


def test_parking_occupied(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="PARKING_CONFLICT",
        summary="My parking is occupied",
        entities={"resource_type": "PARKING_SLOT"},
        issues=[ExtractedIssue(issue_type="PARKING_OCCUPIED", summary="Occupied", severity="HIGH")],
        missing_information=[],
        confidence=0.93,
        access_control_action=True,
        human_review_required=True,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-park", requester_email="employee1@acme.demo")
    session.add(conv)
    session.commit()
    from app.models.org import Person, Resource

    person = session.exec(select(Person).where(Person.email == "employee1@acme.demo")).first()
    parking = session.exec(
        select(Resource).where(Resource.type == "PARKING_SLOT", Resource.allocated_to_person_id == person.person_id)
    ).first()
    ctx = {
        "allocated_resources": [
            {
                "resource_id": parking.resource_id,
                "type": "PARKING_SLOT",
                "name": parking.name,
                "status": parking.status,
                "location_id": parking.location_id,
            }
        ]
    }
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_park",
        context=ctx,
    )
    assert outcome.facts.get("verified_allocation")
    assert outcome.facts.get("temporary_alternative")


def test_chair_missing_separate_tasks(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="FURNITURE_ISSUE",
        summary="Chair missing",
        entities={"resource_type": "CHAIR"},
        issues=[ExtractedIssue(issue_type="CHAIR_MISSING", summary="Missing", severity="MEDIUM")],
        missing_information=[],
        confidence=0.9,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-chair", requester_email="employee2@acme.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="employee2@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_chair",
        context={},
    )
    codes = {t.code for t in session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()}
    assert "TEMP_CHAIR" in codes
    assert "ROOT_CAUSE_CHAIR" in codes


def test_vendor_escalation_unverified(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="VENDOR_ESCALATION",
        summary="Vendor substituted expired goods",
        entities={"vendor_name": "CleanSupply Partners"},
        issues=[
            ExtractedIssue(issue_type="SUBSTITUTION", summary="Substituted items", severity="HIGH"),
            ExtractedIssue(issue_type="EXPIRY", summary="Expired lot", severity="CRITICAL"),
            ExtractedIssue(issue_type="BILLING", summary="Overbilling", severity="MEDIUM"),
        ],
        missing_information=[],
        confidence=0.88,
        vendor_sanction=True,
        human_review_required=True,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-vnd", requester_email="procurement@acme.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="procurement@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_vnd",
        context={},
    )
    issues = session.exec(select(VendorIssue).where(VendorIssue.outcome_id == outcome.outcome_id)).all()
    assert len(issues) >= 3
    assert all(i.allegation_status == "UNVERIFIED" for i in issues)


def test_matched_invoice_no_auto_payment(session: Session):
    tid = _tenant(session)
    from app.models.org import PurchaseOrder

    po = session.exec(select(PurchaseOrder)).first()
    extraction = ExtractionResult(
        event_type="INVOICE",
        summary="Invoice for PO",
        entities={
            "invoice_number": "INV-TEST-001",
            "amount": po.quantity * po.unit_rate,
            "quantity": po.quantity,
            "unit_rate": po.unit_rate,
            "po_number": po.po_number,
        },
        issues=[],
        missing_information=[],
        confidence=0.9,
        financial_action=True,
        human_review_required=True,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-inv", requester_email="billing@securechips.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="billing@securechips.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_inv",
        context={},
    )
    inv = session.exec(select(Invoice).where(Invoice.outcome_id == outcome.outcome_id)).first()
    assert inv.match_status == "MATCHED"
    assert outcome.facts.get("payment_auto_approved") is False


def test_invoice_quantity_mismatch(session: Session):
    tid = _tenant(session)
    from app.models.org import PurchaseOrder

    po = session.exec(select(PurchaseOrder)).first()
    extraction = ExtractionResult(
        event_type="INVOICE",
        summary="Invoice mismatch",
        entities={
            "invoice_number": "INV-TEST-002",
            "amount": 999999,
            "quantity": po.quantity + 5,
            "unit_rate": po.unit_rate,
            "po_number": po.po_number,
        },
        issues=[],
        missing_information=[],
        confidence=0.9,
        financial_action=True,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-inv2", requester_email="billing@securechips.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="billing@securechips.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_inv2",
        context={},
    )
    inv = session.exec(select(Invoice).where(Invoice.outcome_id == outcome.outcome_id)).first()
    assert inv.match_status == "QUANTITY_MISMATCH"


def test_duplicate_invoice_blocked(session: Session):
    tid = _tenant(session)
    from app.models.org import PurchaseOrder

    po = session.exec(select(PurchaseOrder)).first()
    base = {
        "invoice_number": "INV-DUP-9",
        "amount": po.quantity * po.unit_rate,
        "quantity": po.quantity,
        "unit_rate": po.unit_rate,
        "po_number": po.po_number,
    }
    for i, thread in enumerate(["t-d1", "t-d2"]):
        extraction = ExtractionResult(
            event_type="INVOICE",
            summary="Dup invoice",
            entities=base,
            issues=[],
            missing_information=[],
            confidence=0.9,
            financial_action=True,
            reason="test",
        )
        conv = Conversation(tenant_id=tid, thread_id=thread, requester_email="billing@securechips.demo")
        session.add(conv)
        session.commit()
        ScenarioOrchestrator(session, tid).orchestrate(
            extraction=extraction,
            requester_email="billing@securechips.demo",
            conversation_id=conv.conversation_id,
            business_event_id=f"evt_d{i}",
            context={},
        )
    invoices = session.exec(select(Invoice).where(Invoice.invoice_number.contains("INV-DUP-9"))).all()  # type: ignore
    assert any(i.match_status == "DUPLICATE" for i in invoices)


def test_bank_details_change_requires_verification(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="INVOICE",
        summary="Please update bank details and pay",
        entities={
            "invoice_number": "INV-BANK-1",
            "amount": 1000,
            "bank_details_changed": True,
            "po_number": "PO-2026-101",
        },
        issues=[],
        missing_information=[],
        confidence=0.8,
        financial_action=True,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-bank", requester_email="billing@securechips.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="billing@securechips.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_bank",
        context={},
    )
    inv = session.exec(select(Invoice).where(Invoice.outcome_id == outcome.outcome_id)).first()
    assert inv.match_status == "BANK_CHANGE_FLAGGED"
    assert inv.bank_details_changed is True


def test_low_confidence_routes_to_clarification_or_review():
    llm = LLMService(HeuristicProvider())
    extraction = ExtractionResult(
        event_type="UNKNOWN",
        summary="???",
        entities={},
        issues=[],
        missing_information=[MissingInformation(field="x", question="What?", blocking=True)],
        confidence=0.4,
        reason="unclear",
    )
    route = llm.route(extraction)
    assert route.route in {"CLARIFICATION", "OPERATOR_REVIEW", "HUMAN_REQUIRED"}


def test_task_completed_without_evidence_blocked(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="FURNITURE_ISSUE",
        summary="Chair missing",
        entities={},
        issues=[],
        missing_information=[],
        confidence=0.9,
        reason="test",
    )
    conv = Conversation(tenant_id=tid, thread_id="t-ev", requester_email="employee3@acme.demo")
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="employee3@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_ev",
        context={},
    )
    task = session.exec(
        select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == "TEMP_CHAIR")
    ).first()
    engine = OutcomeEngine(session, tid)
    updated = engine.update_task_status(task, "CLOSED", actor="tester")
    assert updated.status == "COMPLETED_PENDING_EVIDENCE"


def test_duplicate_email_idempotency(session: Session):
    tid = _tenant(session)
    intake = IntakeService(session, tid)
    a = intake.ingest(
        message_id="same-msg",
        thread_id="th",
        sender="hr@acme.demo",
        recipients=["x@y.com"],
        subject="Hi",
        body_text="Hello",
        source="API",
    )
    b = intake.ingest(
        message_id="same-msg",
        thread_id="th",
        sender="hr@acme.demo",
        recipients=["x@y.com"],
        subject="Hi",
        body_text="Hello",
        source="API",
    )
    assert a["status"] == "queued"
    assert b["status"] == "deduplicated"
    assert a["event_id"] == b["event_id"]
    assert session.exec(select(RawEmailEvent)).all().__len__() == 1


def test_api_login_and_kpis(client, auth_headers):
    resp = client.get("/api/v1/dashboard/kpis", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "outcomes_active" in data


def test_meeting_room_auto_books_when_available(session: Session):
    from app.models.org import Resource

    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="Meeting room for 5 on 15th october at 3 pm",
        entities={
            "attendees": 5,
            "date": "15th october",
            "preferred_time": "3 pm",
            "end_time": "7pm",
            "duration_hours": 4.0,
        },
        missing_information=[],
        confidence=0.95,
        recommended_next_action="route_to_outcome_engine",
        reason="complete",
    )
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-room-auto",
        requester_email="employee1@acme.demo",
        subject="Need room",
    )
    session.add(conv)
    session.commit()

    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_room_auto",
        context={},
    )
    session.refresh(outcome)
    assert outcome.facts.get("booked_room")
    assert outcome.facts["booked_room"]["assigned_to_email"] == "employee1@acme.demo"
    assert outcome.status in {"CLOSED", "VERIFIED", "ACTIVE"}
    task = session.exec(
        select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == "RESERVE_ROOM")
    ).first()
    assert task.status == "VERIFIED"
    room = session.get(Resource, outcome.facts["booked_room"]["resource_id"])
    assert room is not None
    assert room.status == "RESERVED"


def test_meeting_room_extraordinary_stays_with_ops(session: Session):
    tid = _tenant(session)
    extraction = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="Need boardroom with catering for VIP client visit",
        entities={
            "attendees": 4,
            "date": "tomorrow",
            "preferred_time": "10 am",
            "duration_hours": 2,
            "special_requests": "catering for VIP",
        },
        missing_information=[],
        confidence=0.9,
        reason="special",
    )
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-room-vip",
        requester_email="employee2@acme.demo",
    )
    session.add(conv)
    session.commit()
    outcome = ScenarioOrchestrator(session, tid).orchestrate(
        extraction=extraction,
        requester_email="employee2@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_room_vip",
        context={},
    )
    assert not outcome.facts.get("booked_room")
    assert outcome.facts.get("needs_ops") is True
    task = session.exec(
        select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == "RESERVE_ROOM")
    ).first()
    assert task.status == "ASSIGNED"
