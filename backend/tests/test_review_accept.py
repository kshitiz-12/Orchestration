"""Review accept continues orchestration; thread fact merge."""

from app.ai.gemini import HeuristicProvider
from app.ai.meeting_extract import refine_meeting_room_extraction
from app.ai.service import LLMService
from app.core.enums import ConfidenceRoute
from app.schemas.ai import ExtractionResult, MissingInformation
from app.services.thread_facts import meeting_room_gaps


def test_meeting_room_gaps_complete():
    gaps = meeting_room_gaps(
        {
            "attendees": 20,
            "date": "15th october",
            "preferred_time": "3 pm",
            "duration_hours": 3,
            "meeting_type": "workshop",
            "location_preference": "Corporate Office",
        }
    )
    assert gaps == []


def test_meeting_room_gaps_missing_date():
    gaps = meeting_room_gaps(
        {
            "attendees": 20,
            "preferred_time": "3 pm",
            "end_time": "6 pm",
            "meeting_type": "workshop",
            "location_preference": "Corporate Office",
        }
    )
    assert any(g["field"] == "date" for g in gaps)


def test_meeting_room_gaps_only_core_blocks():
    gaps = meeting_room_gaps(
        {
            "attendees": 4,
            "date": "tomorrow",
            "preferred_time": "10am",
            "duration_hours": 2,
            "meeting_type": "workshop",
            "location_preference": "Corporate Office",
        }
    )
    assert gaps == []
    fields = {g["field"] for g in meeting_room_gaps({})}
    assert fields == {
        "attendees",
        "date",
        "preferred_time",
        "duration",
        "meeting_type",
        "location_preference",
    }
    assert "hybrid_av" not in fields


def test_route_sensitive_not_overwritten_by_low_confidence():
    svc = LLMService(provider=HeuristicProvider())
    extraction = ExtractionResult(
        event_type="INVOICE",
        confidence=0.4,
        financial_action=True,
        human_review_required=True,
        missing_information=[MissingInformation(field="x", question="y", blocking=True)],
    )
    routed = svc.route(extraction)
    assert routed.route == ConfidenceRoute.HUMAN_REQUIRED.value


def test_heuristic_parses_participants_and_not_false_confirm():
    from app.services.meeting_room import is_booking_confirmation

    body = (
        "2 pm to 8 pm , 30 participants , confidential , yes external visitors will "
        "attend , 2 special seatings , whiteboard , microphone , vc , catering is "
        "required , digital board ,"
    )
    assert not is_booking_confirmation(body)
    r = HeuristicProvider().extract(
        subject="Re: [INFORMATION REQUIRED] [ROOM-2026-0005] Additional details needed",
        body=body,
        prior_facts={
            "date": "25th october",
            "primary_office": "Corporate Office, Gurugram",
            "registration_ack_sent": True,
        },
    )
    assert r.event_type == "MEETING_ROOM"
    assert r.entities.get("attendees") == 30
    assert r.entities.get("preferred_time")
    assert r.entities.get("meeting_type") == "confidential"
    assert r.entities.get("location_preference")
    assert r.entities.get("hybrid_av")
    assert r.entities.get("presentation_display") == "yes"
    assert not r.entities.get("booking_confirmed")
    missing = {m.field for m in r.missing_information}
    assert "attendees" not in missing
    assert "meeting_type" not in missing
    assert "location_preference" not in missing
    assert "dietary" in missing
    assert r.entities.get("external_visitors_indicated") is True
    assert r.entities.get("external_visitors") in (None, "", 0)
    assert "external_visitors" in missing


def test_llm_service_refine_does_not_invent_visitor_count():
    svc = LLMService(provider=HeuristicProvider())
    body = (
        "2 pm to 8 pm , 30 participants , confidential , yes external visitors will "
        "attend , catering is required"
    )
    result = svc.extract(
        subject="Re: [INFORMATION REQUIRED] [ROOM-2026-0005] Additional details needed",
        body=body,
        prior_facts={
            "date": "25th october",
            "primary_office": "Corporate Office, Gurugram",
            "registration_ack_sent": True,
        },
    )
    assert result.event_type == "MEETING_ROOM"
    assert result.entities.get("attendees") == 30
    assert result.entities.get("external_visitors") in (None, "", 0)
    assert result.entities.get("external_visitors_indicated") is True
    assert result.human_review_required is False
    missing = {m.field for m in result.missing_information}
    assert "external_visitors" in missing
    assert "dietary" in missing
    routed = svc.route(result)
    assert routed.route == ConfidenceRoute.CLARIFICATION.value


def test_refine_prefers_gemini_entities_over_heuristic_guesses():
    gemini_like = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="clarification reply",
        entities={
            "attendees": 30,
            "external_visitors_indicated": True,
            "meeting_type": "confidential",
            "catering": "requested",
        },
        missing_information=[],
        confidence=0.88,
        reason="gemini",
    )
    refined = refine_meeting_room_extraction(
        gemini_like,
        subject="Re: ROOM-2026-0005",
        body="30 participants, yes external visitors, catering required",
        prior_facts={
            "date": "25th october",
            "preferred_time": "2 pm",
            "end_time": "8 pm",
            "primary_office": "Corporate Office, Gurugram",
        },
        heuristic_entities={
            "attendees": 30,
            "external_visitors": 1,
            "booking_confirmed": True,
            "catering": "requested",
        },
    )
    assert refined.entities.get("external_visitors") in (None, "", 0)
    assert refined.entities.get("external_visitors_indicated") is True
    assert not refined.entities.get("booking_confirmed")
    fields = {m.field for m in refined.missing_information}
    assert "external_visitors" in fields
    assert "dietary" in fields


def test_bare_internal_maps_to_meeting_type():
    r = HeuristicProvider().extract(
        subject="Re: ROOM-2026-0001",
        body="10am to 2 pm , 30 people , internal , yes external visitors will attend , catering required",
        prior_facts={"date": "25th october", "primary_office": "Corporate Office, Gurugram"},
    )
    assert r.entities.get("meeting_type") == "internal meeting"
    assert r.entities.get("attendees") == 30
    assert "meeting_type" not in {m.field for m in r.missing_information}
