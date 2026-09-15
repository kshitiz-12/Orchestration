"""Reducer + informal-reply snapshot tests for meeting interpretation."""

from app.domain.meeting import MeetingStage, Provenance, state_from_facts
from app.engine.outcome_reducer import reduce_meeting_facts
from app.services.meeting_room import meeting_room_gaps


def _prior_schedule():
    return {
        "date": "25th october",
        "attendees": 30,
        "preferred_time": "10am",
        "end_time": "2 pm",
        "duration_hours": 4.0,
        "location_preference": "Corporate Office, Gurugram",
        "primary_office": "Corporate Office, Gurugram",
        "registration_ack_sent": True,
        "catering": "requested",
        "field_provenance": {
            "date": Provenance.EXTRACTED.value,
            "attendees": Provenance.EXTRACTED.value,
            "preferred_time": Provenance.EXTRACTED.value,
            "end_time": Provenance.EXTRACTED.value,
            "duration_hours": Provenance.EXTRACTED.value,
            "location_preference": Provenance.MASTER.value,
        },
    }


def test_informal_reply_completes_against_prior_snapshot():
    prior = _prior_schedule()
    body = "Internal meeting , 2 external visitors rahul and aman , non veg"
    # Simulate heuristic/interpreter entities from this reply only
    primary = {
        "meeting_type": "internal meeting",
        "external_visitors": 2,
        "external_visitors_indicated": True,
        "visitor_details": "rahul and aman",
        "dietary": "non-vegetarian",
    }
    merged = reduce_meeting_facts(
        prior,
        primary_entities=primary,
        source_text=body,
        primary_provenance=Provenance.EXTRACTED,
    )
    assert merged["preferred_time"] == "10am"
    assert merged["attendees"] == 30
    assert merged["meeting_type"] == "internal meeting"
    assert merged["visitor_details"] == "rahul and aman"
    assert merged["dietary"] == "non-vegetarian"
    gaps = meeting_room_gaps(merged)
    assert gaps == []
    assert merged["orchestration_stage"] == MeetingStage.SEARCHING.value
    assert "preferred_time" not in (merged.get("checklist_missing") or [])


def test_reducer_does_not_blank_prior_time():
    prior = _prior_schedule()
    merged = reduce_meeting_facts(
        prior,
        primary_entities={"dietary": "non-vegetarian", "visitor_details": "rahul and aman"},
        candidate_entities={"preferred_time": "", "meeting_type": "internal meeting"},
        source_text="rahul and aman , non veg",
    )
    assert merged["preferred_time"] == "10am"
    assert merged["end_time"] == "2 pm"
    assert merged["meeting_type"] == "internal meeting"


def test_heuristic_does_not_invent_one_visitor():
    prior = {"date": "25th october", "registration_ack_sent": True}
    merged = reduce_meeting_facts(
        prior,
        primary_entities={"external_visitors_indicated": True},
        candidate_entities={"external_visitors": 1, "attendees": 30},
        source_text="yes external visitors will attend , 30 people",
        primary_provenance=Provenance.EXTRACTED,
    )
    assert merged.get("external_visitors") in (None, "", 0)
    assert merged.get("external_visitors_indicated") is True
    assert merged.get("attendees") == 30
    fields = {g["field"] for g in meeting_room_gaps(merged)}
    assert "external_visitors" in fields


def test_stale_checklist_cleared_after_reduce():
    prior = {
        **_prior_schedule(),
        "checklist_missing": ["preferred_time", "duration", "location_preference", "meeting_type"],
        "meeting_type": "internal meeting",
        "visitor_details": "rahul and aman",
        "external_visitors": 2,
        "dietary": "non-vegetarian",
        "catering": "requested",
    }
    merged = reduce_meeting_facts(prior, primary_entities={}, source_text="please continue")
    assert merged["checklist_missing"] == []
    assert state_from_facts(merged).is_complete()
