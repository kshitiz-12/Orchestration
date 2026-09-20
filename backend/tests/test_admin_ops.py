"""Admin ops structured briefing mail."""

from sqlmodel import Session, select

from app.core.config import get_settings
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import Conversation
from app.models.outcome import Communication, Outcome
from app.schemas.ai import ExtractionResult
from app.services.admin_ops import admin_ops_email, build_admin_briefing


def _tenant(session: Session) -> str:
    from app.models.org import Tenant

    t = session.exec(select(Tenant)).first()
    assert t
    return t.tenant_id


def test_admin_ops_email_reads_env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", "ops@adminservices.in")
    get_settings.cache_clear()
    assert admin_ops_email() == "ops@adminservices.in"
    monkeypatch.delenv("ADMIN_OPS_EMAIL", raising=False)
    get_settings.cache_clear()


def test_briefing_puts_special_requests_in_own_section():
    outcome = Outcome(
        tenant_id="t1",
        case_reference="ROOM-2026-0099",
        title="test",
        requester_email="a@b.com",
        facts={
            "attendees": 20,
            "date": "26th sep",
            "preferred_time": "9:30 AM",
            "end_time": "6:00 PM",
            "meeting_type": "internal meeting",
            "location_preference": "Downtown Gurugram",
            "orchestration_stage": "SEARCHING",
            "open_requests": [
                {"text": "photographer for the review", "status": "noted"},
                {"text": "name tents", "status": "noted"},
                {"text": "translator", "status": "noted"},
            ],
            "external_visitors": 2,
            "visitor_details": "Rahul Mehta; Priya Nair",
            "vehicle_numbers": "HR26 AB 1234",
            "guest_vehicles": 1,
        },
    )
    hint, body = build_admin_briefing(
        outcome,
        event_title="New meeting-room request opened",
        kind="update",
    )
    assert "FYI" not in hint.upper()
    assert "OPS UPDATE" in hint
    assert "SPECIAL REQUESTS" in body
    assert "photographer" in body
    assert "name tents" in body
    assert "translator" in body
    assert "MEETING DETAILS" in body
    assert "VISITORS / ACCESS / PARKING" in body
    assert "HR26" in body
    assert "YOU CAN ACT ANYTIME" in body
    assert "visibility only" not in body.lower()
    assert "No action needed" not in body
    # Specials must not only live under meeting dump as "Also requested"
    special_idx = body.index("SPECIAL REQUESTS")
    meeting_idx = body.index("MEETING DETAILS")
    assert special_idx > meeting_idx
    assert "photographer" in body[special_idx:]


def test_decision_briefing_uses_ops_decision_label():
    outcome = Outcome(
        tenant_id="t1",
        case_reference="ROOM-2026-0080",
        title="test",
        requester_email="a@b.com",
        facts={
            "attendees": 80,
            "date": "22 September",
            "orchestration_stage": "NO_RESOURCE",
            "no_resource_diagnosis": {"line": "No room fits 80 people (largest holds 40)."},
        },
    )
    hint, body = build_admin_briefing(
        outcome,
        event_title="No suitable room in inventory",
        detail="Needs ops follow-through",
        kind="decision",
    )
    assert "OPS DECISION" in hint
    assert "FYI" not in hint
    assert "OPS — WHAT YOU CAN DO" in body
    assert "CASE  ROOM-2026-0080" in body


def test_complete_fit_sends_structured_ops_update(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", "ops-desk@example.com")
    get_settings.cache_clear()
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-admin-fyi",
        requester_email="employee1@acme.demo",
        subject="Room please",
    )
    session.add(conv)
    session.commit()

    outcome = orch.orchestrate(
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
                "presentation_display": "yes",
                "catering": "none",
                "external_visitors": 0,
                "open_requests": [{"text": "extra whiteboard markers", "status": "noted"}],
            },
            missing_information=[],
            confidence=0.95,
            reason="complete",
        ),
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_admin_fyi",
        context={},
    )
    mails = session.exec(
        select(Communication).where(Communication.outcome_id == outcome.outcome_id)
    ).all()
    admin_mails = [m for m in mails if "ops-desk@example.com" in (m.recipients or [])]
    assert admin_mails
    assert any("[OPS UPDATE]" in (m.subject or "") for m in admin_mails)
    assert not any("[FYI]" in (m.subject or "") for m in admin_mails)
    body = next(m.body for m in admin_mails if "[OPS UPDATE]" in (m.subject or ""))
    assert "SPECIAL REQUESTS" in (body or "")
    assert "whiteboard" in (body or "").lower()
    assert "YOU CAN ACT ANYTIME" in (body or "")
    get_settings.cache_clear()


def test_no_resource_sends_ops_decision(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", "ops-desk@example.com")
    get_settings.cache_clear()
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-admin-action",
        requester_email="big.team@company.com",
        subject="All-hands",
    )
    session.add(conv)
    session.commit()

    outcome = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="80 people",
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
        business_event_id="evt_admin_nr",
        context={},
    )
    assert outcome.facts.get("orchestration_stage") == "NO_RESOURCE"
    mails = session.exec(
        select(Communication).where(Communication.outcome_id == outcome.outcome_id)
    ).all()
    admin_decision = [
        m
        for m in mails
        if "ops-desk@example.com" in (m.recipients or []) and "[OPS DECISION]" in (m.subject or "")
    ]
    assert admin_decision
    assert "WHAT YOU CAN DO" in (admin_decision[0].body or "")
    get_settings.cache_clear()


def test_admin_notify_disabled_when_env_blank(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", "")
    get_settings.cache_clear()
    assert admin_ops_email() is None
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-admin-off",
        requester_email="employee1@acme.demo",
    )
    session.add(conv)
    session.commit()
    outcome = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="Room for 4",
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
            reason="ok",
        ),
        requester_email="employee1@acme.demo",
        conversation_id=conv.conversation_id,
        business_event_id="evt_admin_off",
        context={},
    )
    mails = session.exec(
        select(Communication).where(Communication.outcome_id == outcome.outcome_id)
    ).all()
    assert not any("[OPS UPDATE]" in (m.subject or "") for m in mails)
    assert not any("[FYI]" in (m.subject or "") for m in mails)
    get_settings.cache_clear()
