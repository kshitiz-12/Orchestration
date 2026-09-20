"""NO_RESOURCE choice detection, diagnosis, and reply handling."""

from sqlmodel import Session, select

from app.ai.messy_meeting_parse import parse_messy_meeting_signals
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import Conversation
from app.models.outcome import Communication, ExceptionRecord
from app.schemas.ai import ExtractionResult
from app.services.no_resource_flow import (
    detect_no_resource_choice,
    diagnose_no_resource,
    format_outbound_greeting,
    open_request_delta,
    short_case_subject,
)


def _tenant(session: Session) -> str:
    from app.models.org import Tenant

    t = session.exec(select(Tenant)).first()
    assert t
    return t.tenant_id


def _complete_entities(**extra):
    base = {
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
    }
    base.update(extra)
    return base


def test_detect_larger_venue_choice():
    alts = [
        {"code": "DIFFERENT_TIME", "label": "Try a different date or start time"},
        {"code": "LARGER_VENUE", "label": "Escalate for a larger venue / off-site option"},
        {"code": "SPLIT_ROOMS", "label": "Split into two rooms (~10 + 10)"},
    ]
    choice = detect_no_resource_choice(
        "escalate for a larger venue\npls find the same\nalso need name tents",
        alts,
    )
    assert choice and choice["code"] == "LARGER_VENUE"


def test_detect_split_and_different_time():
    assert detect_no_resource_choice("please split into two rooms")["code"] == "SPLIT_ROOMS"
    assert detect_no_resource_choice("try a different date")["code"] == "DIFFERENT_TIME"


def test_greeting_never_dear_there():
    assert format_outbound_greeting("there") == "Hello,"
    assert format_outbound_greeting("team") == "Hello,"
    assert format_outbound_greeting("Kapil") == "Dear Kapil,"


def test_short_subject_drops_gemini_narrative():
    subj = short_case_subject(
        case_reference="ROOM-2026-0009",
        action_label="NO ROOM AVAILABLE",
        summary="Meeting for 20 on 26th sep at 9:30 AM–6:00 PM",
        title="The user is requesting an escalation for a larger venue for 20 participants",
    )
    assert "ROOM-2026-0009" in subj
    assert "NO ROOM AVAILABLE" in subj
    assert "The user is requesting" not in subj
    assert "Meeting for 20" in subj


def test_diagnose_equipment_not_fake_capacity():
    d = diagnose_no_resource(
        attendees=20,
        max_capacity=40,
        zero_scores=[
            {"name": "R1", "score": 0, "reasons": ["display missing"]},
            {"name": "R2", "score": 0, "reasons": ["display missing"]},
        ],
    )
    assert d["primary"] == "equipment"
    assert "40" not in d["line"] or "display" in d["line"].lower()
    assert "display" in d["line"].lower()


def test_diagnose_true_capacity():
    d = diagnose_no_resource(
        attendees=80,
        max_capacity=40,
        zero_scores=[{"name": "R1", "score": 0, "reasons": ["insufficient capacity"]}],
    )
    assert d["primary"] == "capacity"
    assert "40" in d["line"]


def test_open_request_delta():
    prior = {"open_requests": [{"text": "photographer", "status": "noted"}]}
    now = {
        "open_requests": [
            {"text": "photographer", "status": "noted"},
            {"text": "name tents", "status": "noted"},
        ]
    }
    delta = open_request_delta(prior, now)
    assert len(delta) == 1
    assert "tents" in str(delta[0].get("text") or "").lower()


def test_visitor_names_with_emdash_and_no_bare_special_access():
    body = (
        "2 extrnal visitors will join — Rahul Mehta (Infosys) and Priya Nair.\n"
        "pls arrange visitor parking , plate HR26 AB 1234."
    )
    signals = parse_messy_meeting_signals(body)
    assert signals.get("external_visitors") == 2
    details = str(signals.get("visitor_details") or "")
    assert "Rahul" in details
    assert "Priya" in details
    assert signals.get("special_access") != "required"
    assert "HR26" in str(signals.get("vehicle_numbers") or "")


def test_no_resource_choice_acks_without_resending_menu(session: Session):
    tid = _tenant(session)
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(
        tenant_id=tid,
        thread_id="t-nr-choice",
        requester_email="ops.lead@company.com",
        subject="All-hands room",
    )
    session.add(conv)
    session.commit()

    first = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="80 people all hands",
            entities=_complete_entities(),
            missing_information=[],
            confidence=0.95,
            reason="complete",
        ),
        requester_email="ops.lead@company.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_nr1",
        context={},
    )
    assert first.facts.get("orchestration_stage") == "NO_RESOURCE"
    mails1 = session.exec(
        select(Communication).where(Communication.outcome_id == first.outcome_id)
    ).all()
    assert any("NO ROOM AVAILABLE" in (m.subject or "") for m in mails1)
    assert all("Dear there" not in (m.body or "") for m in mails1)

    # Requester picks LARGER_VENUE + extras (same conversation → same outcome)
    second = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="Meeting for 80 on 22 September 2026",
            entities={
                "attendees": 80,
                "date": "22 September 2026",
                "preferred_time": "2:00 PM",
                "end_time": "5:00 PM",
                "duration_hours": 3.0,
                "meeting_type": "internal meeting",
                "location_preference": "Corporate Office",
                "presentation_display": "yes",
                "raw_reply": (
                    "escalate for a larger venue\npls find the same\n"
                    "also need name tents and a translator"
                ),
                "open_requests": [
                    {"text": "name tents", "status": "noted", "source": "extracted"},
                    {"text": "translator", "status": "noted", "source": "extracted"},
                ],
            },
            missing_information=[],
            confidence=0.9,
            reason="choice",
            open_requests=["name tents", "translator"],
        ),
        requester_email="ops.lead@company.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_nr2",
        context={},
    )
    assert second.outcome_id == first.outcome_id
    assert second.facts.get("orchestration_stage") == "NO_RESOURCE"
    assert (second.facts.get("no_resource_choice") or {}).get("code") == "LARGER_VENUE"
    mails2 = session.exec(
        select(Communication).where(Communication.outcome_id == second.outcome_id)
    ).all()
    no_room = [m for m in mails2 if "NO ROOM AVAILABLE" in (m.subject or "")]
    choice_mails = [m for m in mails2 if "CHOICE NOTED" in (m.subject or "")]
    assert len(no_room) == 1
    assert len(choice_mails) >= 1
    assert "recorded your choice" in (choice_mails[-1].body or "").lower()
    assert "Please reply with one of these options" not in (choice_mails[-1].body or "")

    third = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM",
            summary="Meeting for 80 on 22 September 2026",
            entities={
                "attendees": 80,
                "date": "22 September 2026",
                "preferred_time": "2:00 PM",
                "end_time": "5:00 PM",
                "duration_hours": 3.0,
                "meeting_type": "internal meeting",
                "location_preference": "Corporate Office",
                "presentation_display": "yes",
                "raw_reply": "ok thanks",
            },
            missing_information=[],
            confidence=0.8,
            reason="idle",
        ),
        requester_email="ops.lead@company.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_nr3",
        context={},
    )
    assert third.facts.get("last_action") in {"no_resource_idle", "no_resource_noted"}
    mails3 = session.exec(
        select(Communication).where(Communication.outcome_id == third.outcome_id)
    ).all()
    assert len([m for m in mails3 if "NO ROOM AVAILABLE" in (m.subject or "")]) == 1

    open_exc = session.exec(
        select(ExceptionRecord).where(
            ExceptionRecord.outcome_id == first.outcome_id,
            ExceptionRecord.exception_type == "NO_MEETING_ROOM",
            ExceptionRecord.status == "OPEN",
        )
    ).all()
    assert len(open_exc) == 1
    assert "LARGER_VENUE" in (open_exc[0].description or "")
