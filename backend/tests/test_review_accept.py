"""Review accept continues orchestration; thread fact merge."""

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.core.enums import ConfidenceRoute
from app.schemas.ai import ExtractionResult, MissingInformation
from app.services.thread_facts import meeting_room_gaps, merge_thread_prior_facts


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
    # Facilities are NOT blocking — silence defaults later; type/location are mandatory
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
    from app.ai.gemini import HeuristicProvider
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
    assert "dietary" in missing  # catering still needs dietary


def test_heuristic_reply_with_prior_facts_completes():
    p = HeuristicProvider()
    r = p.extract(
        subject="Re: [INFORMATION REQUIRED] [ROOM-2026-0001] Additional details needed",
        body="15th October 2026",
        prior_facts={
            "attendees": 20,
            "preferred_time": "3 pm",
            "end_time": "6 pm",
            "duration_hours": 3.0,
            "meeting_type": "workshop",
            "location_preference": "Corporate Office",
        },
    )
    assert r.event_type == "MEETING_ROOM"
    assert r.entities.get("date")
    assert r.entities.get("attendees") == 20
    gaps = meeting_room_gaps(r.entities)
    assert gaps == []
