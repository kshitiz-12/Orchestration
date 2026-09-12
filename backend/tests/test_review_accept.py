"""Review accept continues orchestration; thread fact merge."""

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.core.enums import ConfidenceRoute
from app.schemas.ai import ExtractionResult, MissingInformation
from app.services.thread_facts import meeting_room_gaps, merge_thread_prior_facts


def test_meeting_room_gaps_complete():
    gaps = meeting_room_gaps(
        {"attendees": 20, "date": "15th october", "preferred_time": "3 pm", "duration_hours": 3}
    )
    assert gaps == []


def test_meeting_room_gaps_missing_date():
    gaps = meeting_room_gaps({"attendees": 20, "preferred_time": "3 pm", "end_time": "6 pm"})
    assert any(g["field"] == "date" for g in gaps)


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
        prior_facts={"attendees": 20, "preferred_time": "3 pm", "end_time": "6 pm", "duration_hours": 3.0},
    )
    assert r.event_type == "MEETING_ROOM"
    assert r.entities.get("date")
    assert r.entities.get("attendees") == 20
    gaps = meeting_room_gaps(r.entities)
    assert gaps == []
