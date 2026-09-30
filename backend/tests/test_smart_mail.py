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


_HELD = {
    "date": "2026-10-25",
    "preferred_time": "10am",
    "pending_confirmation": True,
    "proposed_room": {"name": "Auditorium A", "date": "2026-10-25", "start": "10am"},
}


def test_addon_reply_with_stale_new_request_flag_updates_same_case():
    from app.services.meeting_room import is_new_meeting_request

    decision = is_new_meeting_request(
        text="Requester needs parking for 2 guest vehicles and a bouquet",
        new_facts={"date": "25th Oct", "preferred_time": "10:00 AM", "new_request": True},
        existing_facts=_HELD,
        existing_status="ACTIVE",
    )
    assert decision == "update"


def test_new_request_flag_on_different_day_spawns_case():
    from app.services.meeting_room import is_new_meeting_request

    decision = is_new_meeting_request(
        text="Also a room on Friday",
        new_facts={"date": "2026-10-30", "new_request": True},
        existing_facts=_HELD,
        existing_status="ACTIVE",
    )
    assert decision == "new"


def test_per_message_flags_do_not_carry_over_from_prior_facts():
    from app.ai.meeting_extract import refine_meeting_room_extraction
    from app.schemas.ai import ExtractionResult

    prior = {**_HELD, "attendees": 12, "new_request": True}
    extraction = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="needs parking",
        entities={"guest_vehicles": 2},
        missing_information=[],
        confidence=0.9,
        reason="addon",
    )
    out = refine_meeting_room_extraction(
        extraction, subject="Re: [ROOM-2026-0001]", body="need parking for 2 cars", prior_facts=prior
    )
    assert "new_request" not in out.entities


_BOOKED_FACTS = {
    "requester_name": "Aditya Test",
    "attendees": 12,
    "external_visitors": 2,
    "visitor_details": "Rahul Sharma and Aman Verma",
    "date": "2026-10-25",
    "preferred_time": "10am",
    "end_time": "1pm",
    "location_preference": "Gurugram office",
    "hybrid_av": "yes — for 2 remote participants",
    "presentation_display": "yes",
    "catering": "coffee for 6, tea for the rest, mid-meeting",
    "dietary": "4 veg, rest non-veg",
    "guest_vehicles": 2,
    "vehicle_numbers": "KA53EB8527, JH06AB3031",
    "special_access": "none",
    "confidentiality": "standard",
    "setup_buffer_minutes": 30,
    "open_requests": [{"text": "bouquet at start of meeting", "status": "noted"}],
    "booked_room": {"name": "Auditorium A", "capacity": 40},
}


def test_booked_briefing_is_a_short_work_order():
    outcome = Outcome(
        tenant_id="t", case_reference="ROOM-2026-0001", requester_email="anonymousxo1204@gmail.com", facts={}
    )
    _, body = build_admin_briefing(
        outcome, event_title="Booking confirmed — Auditorium A", facts=_BOOKED_FACTS
    )
    assert "Room: Auditorium A (40 seats), setup 30 min before" in body
    assert "People: 12 + 2 visitors (Rahul Sharma and Aman Verma) → 14 seats" in body
    for item in (
        "- Video call (for 2 remote participants) + display",
        "- Coffee for 6, tea for the rest, mid-meeting — 4 veg, rest non-veg",
        "- Visitor passes for 2: Rahul Sharma and Aman Verma",
        "- Parking for 2: KA53EB8527, JH06AB3031",
        "- Bouquet at start of meeting",
    ):
        assert item in body
    assert "Also asked" not in body and "Needs:" not in body


def test_booked_briefing_uses_latest_counted_catering_and_real_visitor_names():
    facts = {
        **_BOOKED_FACTS,
        "external_visitors": 12,
        "visitor_details": "Rahul Sharma and Aman Verma and 10 additional external visitors",
        "catering": "tea, coffee",
        "dietary": "12 vegetarian, rest non-vegetarian",
        "catering_notes": [
            "tea coffee, non veg is fine",
            "12 veg, rest non veg, 3 tea, 4 soft drinks rest coffee",
        ],
    }
    outcome = Outcome(tenant_id="t", case_reference="ROOM-2026-0002", requester_email="a@b.com", facts={})
    _, body = build_admin_briefing(outcome, event_title="Booking confirmed — Auditorium A", facts=facts)
    assert '- Catering, as the requester asked: "12 veg, rest non veg, 3 tea, 4 soft drinks rest coffee"' in body
    assert "tea coffee, non veg is fine" not in body
    assert "- Visitor passes for 12: Rahul Sharma and Aman Verma + 10 names to come" in body


def test_visitor_addition_marker_is_short():
    from app.ai.messy_meeting_parse import parse_messy_meeting_signals

    out = parse_messy_meeting_signals(
        "10 more external visitors will join, and for the catering 12 veg, rest non veg, 3 tea, 4 soft drinks rest coffee"
    )
    assert out["external_visitors_add"] == 10
    assert out["external_visitors_add_phrase"] == "10 more external visitors"


_PASTED_FORM_REPLY = (
    "Hi,\r\n\r\nPls find the  same\r\n\r\nTo lock in a room I just need:\r\n"
    "- How many people will attend in person? 20\r\n"
    "- Which date do you need the room? 7th Oct\r\n"
    "- How long do you need the room (end time or duration)?10 A.M to 3 P.M\r\n"
    "- Meeting type: internal, client/vendor, interview, training, confidential, or other? Internal\r\n\r\n"
    "Also worth a quick check:\r\n"
    "- Hybrid / AV: not answered - yes required\r\n"
    "- Presentation display: not answered yes Required\r\n"
    "- Catering / amenities: not answered - 10 veg and 10 Non Veg , 2 times tea/coffee\r\n"
    "- Special access / security: not answered -no\r\n"
    "- Confidentiality: not answered\r\n\r\n"
    "<Hero-FinCorp-New-Logo.jpg>\u00c2\u00a0<Screenshot 2024-04-02 140213.png>\r\n\r\n"
    "Kapil Mantri\r\nSr. Associate - Administration & Infrastructure\r\n"
)


def test_pasted_back_form_reads_as_answers_only():
    from app.ai.gemini import HeuristicProvider
    from app.ai.messy_meeting_parse import catering_phrases
    from app.services.email_utils import strip_for_ai

    cleaned = strip_for_ai(_PASTED_FORM_REPLY)
    assert "confidential" not in cleaned.lower()
    assert "not answered" not in cleaned.lower()
    assert "Kapil" not in cleaned and ".jpg" not in cleaned
    for line in ("Attendees in person: 20", "Date: 7th Oct", "Meeting type: Internal", "Hybrid / AV: yes required"):
        assert line in cleaned
    facts = HeuristicProvider().extract(subject="RE: [ROOM-2026-0003]", body=cleaned).entities
    assert not facts.get("confidentiality")
    said = catering_phrases(cleaned)
    assert "10 veg" in said and "tea/coffee" in said and "quick check" not in said


def test_room_fit_note_explains_oversized_room_and_missing_vc():
    from app.engine.meeting_scenario import _room_fit_note

    facts = {
        "attendees": 12,
        "external_visitors": 2,
        "hybrid_av": "yes — 2 remote",
        "room_scores": [
            {"name": "Auditorium A", "capacity": 40, "reasons": ["VC available"]},
            {"name": "Meeting Room F2-R3", "capacity": 16, "reasons": ["VC missing"]},
        ],
    }
    big = SimpleNamespace(name="Auditorium A", attributes={"capacity": 40, "video_conferencing": True, "display": True})
    small = SimpleNamespace(name="Meeting Room F2-R3", attributes={"capacity": 16, "display": True})
    assert "smaller free rooms don't have video-call" in _room_fit_note(big, facts)
    assert "no built-in video-call setup" in _room_fit_note(small, facts)


_ADDON_REPLY = (
    "Few more requests I want 6 non veg and rest veg and 2 tea rest coffee and\r\n"
    "one more visitor will join us"
)
_OFFER_SUBJECT = "Re: [CONFIRM BOOKING] [ROOM-2026-0001] Meeting for 12 on 25th oct at 10am–1pm (3.0h)"


def test_catering_counts_survive_in_requesters_words():
    from app.ai.meeting_extract import refine_meeting_room_extraction
    from app.ai.messy_meeting_parse import catering_phrases
    from app.schemas.ai import ExtractionResult

    assert catering_phrases(_ADDON_REPLY) == "6 non veg, rest veg, 2 tea rest coffee"
    assert catering_phrases("coffe for 6 and rest tea mid meeting") == "coffe for 6, rest tea mid meeting"
    assert catering_phrases("confirm") == ""

    prior = {**_HELD, "attendees": 12, "catering": "tea/coffee", "catering_notes": ["tea coffee, non veg is fine"]}
    extraction = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="more requests",
        entities={"catering": "tea, coffee, non-veg and veg meals"},
        missing_information=[],
        confidence=0.9,
        reason="addon",
    )
    out = refine_meeting_room_extraction(extraction, subject=_OFFER_SUBJECT, body=_ADDON_REPLY, prior_facts=prior)
    assert out.entities["catering_notes"] == ["tea coffee, non veg is fine", "6 non veg, rest veg, 2 tea rest coffee"]

    booked = {**_BOOKED_FACTS, "catering_notes": out.entities["catering_notes"]}
    outcome = Outcome(tenant_id="t", case_reference="ROOM-2026-0001", requester_email="a@b.com", facts={})
    _, body = build_admin_briefing(outcome, event_title="Booking confirmed — Auditorium A", facts=booked)
    assert '"6 non veg, rest veg, 2 tea rest coffee"' in body


def test_live_reply_six_more_visitors_and_diet_split():
    from app.ai.gemini import HeuristicProvider
    from app.ai.meeting_extract import refine_meeting_room_extraction
    from app.engine.outcome_reducer import reduce_meeting_facts
    from app.schemas.ai import ExtractionResult

    body = (
        "few more requests i need veg for two and non veg for rest and tea for 6 and\r\n"
        "coffee for rest ,also 6 more external visitors will join us ,"
    )
    subject = "Re: [CONFIRM BOOKING] [ROOM-2026-0001] Meeting for 12 on 2025-10-25 at 10am–1pm (3.0h)"
    prior = {
        **_HELD,
        "date": "2025-10-25",
        "attendees": 12,
        "external_visitors": 2,
        "visitor_details": "Rahul Sharma and Aman Verma",
        "catering": "tea coffee",
        "dietary": "non-vegetarian",
        "field_provenance": {"dietary": "extracted", "catering": "extracted"},
    }
    extraction = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="more requests",
        entities={"dietary": "2 veg, rest non-veg", "catering": "tea for 6, coffee for rest", "external_visitors": 8},
        missing_information=[],
        confidence=0.9,
        reason="addon",
    )
    heuristic = HeuristicProvider().extract(subject=subject, body=body).entities
    facts = refine_meeting_room_extraction(
        extraction, subject=subject, body=body, prior_facts=prior, heuristic_entities=heuristic
    ).entities
    assert facts["external_visitors"] == 8
    assert facts["visitor_details"] == "Rahul Sharma and Aman Verma"
    assert facts["dietary"] == "2 veg, rest non-veg"
    assert facts["date"].startswith("2026-10-25") or facts["date"] >= "2026-10-25"
    # Reducing the same mail again (orchestrator pass) must not add the 6 a second time.
    assert reduce_meeting_facts(facts, primary_entities={}, source_text=body)["external_visitors"] == 8


def test_our_subject_tag_is_not_the_requesters_confirm():
    from app.services.meeting_room import is_booking_confirmation

    assert not is_booking_confirmation(f"{_OFFER_SUBJECT}\n{_ADDON_REPLY}")
    assert is_booking_confirmation(f"{_OFFER_SUBJECT}\nconfirm")
    assert is_booking_confirmation(f"{_OFFER_SUBJECT}\nlooks good, go ahead")


def test_addon_reply_to_offer_is_not_booked_even_if_model_says_confirm():
    from app.ai.meeting_extract import refine_meeting_room_extraction
    from app.schemas.ai import ExtractionResult

    prior = {
        **_HELD,
        "attendees": 12,
        "external_visitors": 2,
        "visitor_details": "Rahul Sharma and Aman Verma",
        "dietary": "non-vegetarian",
    }
    extraction = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="more requests",
        entities={"dietary": "6 non-veg, rest veg", "external_visitors": 3, "visitor_details": "us"},
        fact_delta={"set": {}, "speech_acts": ["confirm"]},
        missing_information=[],
        confidence=0.9,
        reason="addon",
    )
    out = refine_meeting_room_extraction(extraction, subject=_OFFER_SUBJECT, body=_ADDON_REPLY, prior_facts=prior)
    assert not out.entities.get("booking_confirmed")
    assert out.entities["external_visitors"] == 3
    assert out.entities["visitor_details"] == "Rahul Sharma and Aman Verma"


def test_platform_bookkeeping_never_becomes_an_open_request():
    from app.domain.open_requests import merge_open_requests

    asks = merge_open_requests(
        {},
        {
            "open_requests": ["bouquet at start of meeting"],
            "busy_fit_rooms": ["Auditorium A"],
            "meeting_window": {"start": "2026-10-25T09:30:00"},
            "spawned_from_outcome_id": "out_x",
        },
    )
    assert [a["text"] for a in asks] == ["bouquet at start of meeting"]
