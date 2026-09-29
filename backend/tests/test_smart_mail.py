"""Seats incl. visitors, requester name from signature, briefing hygiene, AI mail writer guards."""

from types import SimpleNamespace

from app.ai.mail_writer import must_keep_tokens, write_requester_mail
from app.models.outcome import Outcome
from app.services.admin_ops import build_admin_briefing
from app.services.meeting_room import score_meeting_room, seats_needed, summarize_meeting_requirements


def _room(cap: int, **attrs):
    return SimpleNamespace(name=f"Room {cap}", attributes={"capacity": cap, **attrs})


def test_seats_include_in_person_visitors():
    assert seats_needed({"attendees": 12, "external_visitors": 2}) == 14
    assert seats_needed({"attendees": 15, "external_visitors": 2, "visitors_counted_in_attendees": True}) == 15
    assert seats_needed({"attendees": 12}) == 12
    assert seats_needed({"external_visitors": 3}) == 3


def test_twelve_seat_room_rejected_for_twelve_plus_two_visitors():
    facts = {"attendees": 12, "external_visitors": 2}
    assert score_meeting_room(_room(12), facts)[0] == 0
    assert score_meeting_room(_room(14), facts)[0] > 0


def test_summary_merges_visitors_and_drops_noise():
    facts = {
        "attendees": 12,
        "external_visitors": 2,
        "visitor_details": "Rahul Sharma and Aman Verma",
        "special_access": "none",
        "field_provenance": {
            "attendees": "extracted",
            "external_visitors": "extracted",
            "visitor_details": "extracted",
            "special_access": "extracted",
        },
    }
    lines = summarize_meeting_requirements(facts)
    assert lines[0] == "Attendees: 12 + 2 visitors (Rahul Sharma and Aman Verma) — 14 seats"
    assert not any(line.startswith("Visitor names") for line in lines)
    assert not any("Special access" in line for line in lines)


def test_briefing_shows_signed_name_and_no_duplicate_lines():
    outcome = Outcome(
        tenant_id="t1",
        case_reference="ROOM-2026-0100",
        title="t",
        requester_email="anonymousxo1204@gmail.com",
        facts={
            "attendees": 12,
            "external_visitors": 2,
            "date": "25th oct",
            "meeting_type": "internal meeting",
            "location_preference": "Corporate Office",
            "requester_name": "Aditya Test",
            "orchestration_stage": "PROPOSED",
        },
    )
    _, body = build_admin_briefing(outcome, event_title="Room proposed")
    assert "Requester: Aditya Test <anonymousxo1204@gmail.com>" in body
    assert "When: Sun 25 Oct 2026 · Corporate Office" in body
    assert "People: 12 + 2 visitors → 14 seats" in body


def test_gemini_schema_declares_fact_fields():
    from app.ai.gemini import EXTRACTION_SCHEMA_HINT

    ents = EXTRACTION_SCHEMA_HINT["properties"]["entities"]["properties"]
    delta = EXTRACTION_SCHEMA_HINT["properties"]["fact_delta"]["properties"]["set"]["properties"]
    for key in ("attendees", "date", "guest_vehicles", "requester_name", "visitors_counted_in_attendees"):
        assert key in ents and key in delta


def test_hybrid_reads_free_text():
    from app.services.meeting_room import hybrid_needed

    assert hybrid_needed({"hybrid_av": "yes — VC for 2 remote participants"})
    assert hybrid_needed({"hybrid_av": "VC for 2 remote participants"})
    assert not hybrid_needed({"hybrid_av": "no VC needed"})
    assert not hybrid_needed({"hybrid_av": "no"})


def test_new_fact_keys_are_not_open_requests():
    from app.domain.open_requests import merge_open_requests

    asks = merge_open_requests({}, {"requester_name": "Aditya Test", "visitors_counted_in_attendees": False})
    assert asks == []


class _FakeProvider:
    def __init__(self, body):
        self.body = body
        self.payload = None

    def generate_json(self, *, system_instruction, payload, temperature):
        self.payload = payload
        return {"body": self.body}, {"label": "fake"}


_DRAFT = (
    "Hello,\n\nGood news.\n\nRoom: Meeting Room F2-R3 (seats 14)\n\n"
    'Reply "confirm" to lock it in.\n\nCase: ROOM-2026-0001'
)
_FACTS = {"proposed_room": {"name": "Meeting Room F2-R3", "capacity": 14}, "attendees": 12, "external_visitors": 2}


def test_must_keep_tokens_cover_case_room_and_reply_word():
    tokens = must_keep_tokens(_DRAFT, "ROOM-2026-0001", _FACTS)
    assert tokens == ["ROOM-2026-0001", "Meeting Room F2-R3", "confirm"]


def test_mail_writer_accepts_faithful_rewrite():
    good = (
        "Hi Aditya,\n\nMeeting Room F2-R3 is yours if you want it — it seats all 14 of you. "
        'Reply "confirm" and I\'ll lock it in.\n\nCase ROOM-2026-0001\nWorkplace Team'
    )
    provider = _FakeProvider(good)
    out = write_requester_mail(
        draft=_DRAFT,
        purpose="CONFIRM BOOKING",
        facts=_FACTS,
        requester_name="Aditya Test",
        case_reference="ROOM-2026-0001",
        provider=provider,
    )
    assert out == good
    assert provider.payload["requester_name"] == "Aditya"
    assert provider.payload["request"]["seats_needed_in_room"] == 14


def test_mail_writer_rejects_rewrite_that_drops_room():
    bad = "Hi,\n\nWe found you a room. Reply confirm.\n\nCase ROOM-2026-0001"
    out = write_requester_mail(
        draft=_DRAFT,
        purpose="CONFIRM BOOKING",
        facts=_FACTS,
        requester_name=None,
        case_reference="ROOM-2026-0001",
        provider=_FakeProvider(bad),
    )
    assert out is None
