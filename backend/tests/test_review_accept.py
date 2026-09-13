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
