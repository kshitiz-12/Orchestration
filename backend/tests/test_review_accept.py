"""Review accept continues orchestration; thread fact merge."""

from app.ai.gemini import HeuristicProvider
from app.ai.meeting_extract import refine_meeting_room_extraction
from app.ai.messy_meeting_parse import parse_messy_meeting_signals, parse_vehicle_plates
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
        "meeting_type",
        "location_preference",
    }
    assert "duration" not in fields  # merged into preferred_time when both open
    qs = [g["question"] for g in meeting_room_gaps({})]
    time_qs = [q for q in qs if "time" in q.lower()]
    assert len(time_qs) == 1
    assert "time slot" in time_qs[0].lower()


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


def test_questions_only_ask_missing_when_facts_known():
    from app.services.meeting_room import default_meeting_room_questions

    facts = {
        "date": "25th oct",
        "preferred_time": "10am",
        "end_time": "1pm",
        "duration_hours": 3.0,
        "meeting_type": "internal meeting",
        "location_preference": "Corporate Office",
        "hybrid_av": "yes",
        "presentation_display": "yes",
        "catering": "requested",
        "dietary": "non-vegetarian",
        "external_visitors": 2,
        "external_visitors_indicated": True,
        "primary_office": "Corporate Office, Gurugram",
    }
    qs = default_meeting_room_questions(facts)
    blob = " ".join(qs).lower()
    assert "how many people" in blob
    assert "visitor" in blob
    assert "meeting type" not in blob
    assert "tea, coffee" not in blob
    assert "start time and end time" not in blob


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


def test_heuristic_reply_with_prior_facts_completes():
    svc = LLMService(provider=HeuristicProvider())
    r = svc.extract(
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


def test_heuristic_parses_typo_employees_and_visitor_names():
    from app.services.email_utils import strip_for_ai

    body = (
        "We are having internal review meet on 25th Oct and need meeting room for 12 "
        "empployee's from 10am to 1pm at Gurugram office.\n\n"
        "2 external visitors will attend - Rahul Sharma and Aman Verma.\n"
        "Pls also arrange tea coffee , non veg is fine , and display + VC.\n"
        "No guest vehicle required.\n\n"
        "Disclaimer: privileged and confidential."
    )
    clean = strip_for_ai(body)
    assert "Disclaimer" not in clean
    r = HeuristicProvider().extract(subject="req meeting room", body=clean)
    assert r.entities.get("attendees") == 12
    assert r.entities.get("external_visitors") == 2
    assert "Rahul" in (r.entities.get("visitor_details") or "")
    assert r.entities.get("dietary") == "non-vegetarian"
    assert r.entities.get("meeting_type") == "internal meeting"
    assert "attendees" not in {m.field for m in r.missing_information}
    assert "visitor_details" not in {m.field for m in r.missing_information}


def test_extraction_result_coerces_lowercase_priority():
    result = ExtractionResult.model_validate(
        {
            "event_type": "meeting_room",
            "summary": "test",
            "entities": {},
            "issues": [{"issue_type": "X", "summary": "y", "severity": "high"}],
            "missing_information": [],
            "confidence": 0.9,
            "reason": "gemini",
            "recommended_priority": "medium",
        }
    )
    assert result.event_type == "MEETING_ROOM"
    assert result.recommended_priority == "MEDIUM"
    assert result.issues[0].severity == "HIGH"


def test_gemini_failover_uses_secondary_after_model_failures():
    from app.ai.gemini import GeminiProvider

    class RecoveringGemini(GeminiProvider):
        def __init__(self):
            self.api_key = "k1"
            self.api_key_secondary = "k2"
            self.model = "gemini-3.6-flash"
            self.fallback_model = "gemini-3.7-flash"
            self._clients = {}
            self.last_endpoint = {}
            self.attempts: list[str] = []

        def _endpoints(self):
            return [
                ("primary:gemini-3.6-flash", "k1", "gemini-3.6-flash"),
                ("primary:gemini-3.7-flash", "k1", "gemini-3.7-flash"),
                ("secondary:gemini-3.6-flash", "k2", "gemini-3.6-flash"),
            ]

        def _generate_once(self, *, api_key, model, user_payload):
            self.attempts.append(f"{api_key}:{model}")
            if model == "gemini-3.6-flash" and api_key == "k1":
                raise RuntimeError("429 RESOURCE_EXHAUSTED quota")
            if api_key == "k1" and model == "gemini-3.7-flash":
                raise RuntimeError("503 UNAVAILABLE high demand")

            class Resp:
                text = (
                    '{"event_type":"MEETING_ROOM","summary":"ok","entities":{"attendees":8,'
                    '"meeting_type":"internal meeting"},"issues":[],"missing_information":[],'
                    '"confidence":0.9,"reason":"gemini","recommended_priority":"MEDIUM"}'
                )

            return Resp()

    recovering = RecoveringGemini()
    svc = LLMService(provider=recovering)
    result = svc.extract(
        subject="Re: ROOM-1",
        body="8 people, internal",
        prior_facts={"date": "tomorrow", "preferred_time": "10am", "duration_hours": 1},
    )
    assert recovering.attempts == [
        "k1:gemini-3.6-flash",
        "k1:gemini-3.7-flash",
        "k2:gemini-3.6-flash",
    ]
    assert result.entities.get("attendees") == 8
    assert "gemini:secondary:gemini-3.6-flash" in (result.reason or "")
    assert "gemini delta + reducer + heuristic fill" in (result.reason or "")
    assert str(result.entities.get("interpretation_path") or "").startswith("gemini:")


def test_gemini_fills_blanks_with_heuristic_candidates():
    """Gemini succeeds but leaves typo headcount blank — heuristic candidates fill only unknowns."""
    from app.ai.gemini import GeminiProvider

    class SparseGemini(GeminiProvider):
        def __init__(self):
            self.api_key = "k1"
            self.api_key_secondary = ""
            self.model = "gemini-3.6-flash"
            self.fallback_model = "gemini-3.7-flash"
            self._clients = {}
            self.last_endpoint = {"label": "primary:gemini-3.6-flash", "model": "gemini-3.6-flash"}

        def extract(self, **kwargs):
            return ExtractionResult(
                event_type="MEETING_ROOM",
                summary="partial",
                entities={
                    "date": "25th Oct",
                    "preferred_time": "10am",
                    "end_time": "1pm",
                    "meeting_type": "internal meeting",
                    "location_preference": "Gurugram",
                    "external_visitors": 2,
                },
                missing_information=[],
                confidence=0.9,
                reason="gemini:primary:gemini-3.6-flash",
            )

    body = (
        "We are having internal review meet on 25th Oct and need meeting room for 12 "
        "empployee's from 10am to 1pm at Gurugram office.\n\n"
        "2 external visitors will attend - Rahul Sharma and Aman Verma.\n"
        "Pls also arrange tea coffee , non veg is fine , and display + VC.\n"
        "No guest vehicle required.\n\n"
        "Disclaimer: privileged and confidential."
    )
    svc = LLMService(provider=SparseGemini())
    result = svc.extract(subject="req meeting room", body=body)
    assert result.entities.get("attendees") == 12
    assert "Rahul" in (result.entities.get("visitor_details") or "")
    assert result.entities.get("dietary") == "non-vegetarian"
    assert "attendees" not in {m.field for m in result.missing_information}
    assert "heuristic fill" in (result.reason or "")


def test_confirm_reply_parses_parking_and_dietary_split():
    from app.ai.gemini import HeuristicProvider
    from app.ai.service import LLMService

    result = LLMService(provider=HeuristicProvider()).extract(
        subject="Re: [CONFIRM BOOKING] [ROOM-1]",
        body="yes confirm also we require parking for two and two veg catering and rest non veg",
        prior_facts={
            "pending_confirmation": True,
            "proposed_room": {"name": "Focus"},
            "attendees": 12,
            "external_visitors": 2,
            "dietary": "non-vegetarian",
            "catering": "requested",
            "guest_vehicles": 0,
            "date": "25th oct",
            "preferred_time": "10am",
            "end_time": "1pm",
            "duration_hours": 3.0,
            "meeting_type": "internal meeting",
            "location_preference": "Corporate Office",
            "registration_ack_sent": True,
        },
    )
    assert result.entities.get("booking_confirmed") is True
    assert result.entities.get("guest_vehicles") == 2
    diet = (result.entities.get("dietary") or "").lower()
    assert "2 vegetarian" in diet or "2 veg" in diet
    assert "rest non-vegetarian" in diet or "non-veg" in diet


def test_display_name_from_from_header():
    from app.services.communication import display_name_from_headers, humanize_email_local

    assert display_name_from_headers({"From": '"Kapil Mantri" <kapil@example.com>'}) == "Kapil Mantri"
    assert display_name_from_headers({"from": "Aditya Test <a@example.com>"}) == "Aditya Test"
    assert humanize_email_local("anonymousxo@gmail.com") == "team"


def test_kapil_style_golden_email_remaining_only_ask():
    """Golden regression: rich informal mail → understand most facts, ask only gaps."""
    from app.services.email_utils import strip_for_ai
    from app.services.meeting_room import default_meeting_room_questions, meeting_room_gaps

    body = (
        "Hi Team,\n\n"
        "We are having internal review meet on 25th Oct and need meeting room for 12 "
        "empployee's from 10am to 1pm at Gurugram office.\n\n"
        "2 external visitors will attend - Rahul Sharma and Aman Verma.\n"
        "Pls also arrange tea coffee , non veg is fine , and display + VC for 2 "
        "remote participants.\n"
        "No guest vehicle required.\n\n"
        "Pls help in booking suitable meeting room .\n\n"
        "Aditya Test\n"
        "Sr. Associate - Administration & Infrastructure\n\n"
        "Disclaimer: The information in this e-mail is privileged and confidential."
    )
    clean = strip_for_ai(body)
    assert "Disclaimer" not in clean
    svc = LLMService(provider=HeuristicProvider())
    result = svc.extract(subject="Request for meeting room", body=body)
    ents = result.entities or {}
    assert ents.get("attendees") == 12
    assert ents.get("external_visitors") == 2
    assert "Rahul" in (ents.get("visitor_details") or "")
    assert ents.get("dietary") == "non-vegetarian"
    assert ents.get("meeting_type") == "internal meeting"
    assert ents.get("interpretation_path") == "heuristic"
    gaps = meeting_room_gaps(ents)
    qs = default_meeting_room_questions(ents)
    blob = " ".join(qs).lower()
    # Must not re-ask known fields
    assert "meeting type" not in blob
    assert "start time and end time" not in blob
    assert "tea, coffee" not in blob
    # If anything is asked, it is only remaining gaps
    for g in gaps:
        assert g["field"] not in {"attendees", "visitor_details", "dietary", "meeting_type"}


def test_gemini_endpoint_order_includes_secondary_key():
    from app.ai.gemini import GeminiProvider

    p = GeminiProvider(
        api_key="key-a",
        api_key_secondary="key-b",
        model="gemini-3.6-flash",
        fallback_model="gemini-3.7-flash",
    )
    labels = [e[0] for e in p._endpoints()]
    assert labels == [
        "primary:gemini-3.6-flash",
        "primary:gemini-3.7-flash",
        "secondary:gemini-3.6-flash",
        "secondary:gemini-3.7-flash",
    ]


def test_llm_service_falls_back_after_gemini_503_exhausted():
    from app.ai.gemini import GeminiProvider

    class DeadGemini(GeminiProvider):
        def __init__(self):
            self.calls = 0
            self.api_key = "test"
            self.api_key_secondary = ""
            self.model = "gemini-3.6-flash"
            self.fallback_model = "gemini-3.7-flash"
            self._clients = {}
            self.last_endpoint = {}

        def extract(self, **kwargs):
            self.calls += 1
            raise RuntimeError("429 RESOURCE_EXHAUSTED on all endpoints")

    dead = DeadGemini()
    svc = LLMService(provider=dead)
    result = svc.extract(
        subject="Need a meeting room",
        body="Book a room for 12 people tomorrow at 3pm for 2 hours, internal, Corporate Office",
        prior_facts={},
    )
    assert dead.calls == 1
    assert result.event_type == "MEETING_ROOM"
    assert result.entities.get("attendees") == 12
    assert "heuristic fallback" in (result.reason or "").lower() or "reducer + heuristic" in (result.reason or "")


def test_fact_delta_applied_by_refine():
    prior = {
        "date": "25th october",
        "attendees": 30,
        "preferred_time": "10am",
        "end_time": "2 pm",
        "duration_hours": 4.0,
        "location_preference": "Corporate Office, Gurugram",
        "primary_office": "Corporate Office, Gurugram",
        "registration_ack_sent": True,
        "catering": "requested",
    }
    gemini_like = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="informal reply",
        entities={},
        fact_delta={
            "set": {
                "meeting_type": "internal meeting",
                "external_visitors": 2,
                "visitor_details": "rahul and aman",
                "dietary": "non-vegetarian",
            },
            "speech_acts": ["provide_facts"],
        },
        missing_information=[],
        confidence=0.9,
        reason="gemini",
    )
    refined = refine_meeting_room_extraction(
        gemini_like,
        subject="Re: ROOM-2026-0001",
        body="Internal meeting , 2 external visitors rahul and aman , non veg",
        prior_facts=prior,
        heuristic_entities={"external_visitors": 1},
    )
    assert refined.entities.get("preferred_time") == "10am"
    assert refined.entities.get("meeting_type") == "internal meeting"
    assert refined.entities.get("visitor_details") == "rahul and aman"
    assert refined.entities.get("external_visitors") == 2
    assert refined.missing_information == []


def test_informal_reply_via_llm_service_against_snapshot():
    svc = LLMService(provider=HeuristicProvider())
    result = svc.extract(
        subject="Re: [INFORMATION REQUIRED] [ROOM-2026-0001]",
        body="Internal meeting , 2 external visitors rahul and aman , non veg",
        prior_facts={
            "date": "25th october",
            "attendees": 30,
            "preferred_time": "10am",
            "end_time": "2 pm",
            "duration_hours": 4.0,
            "location_preference": "Corporate Office, Gurugram",
            "primary_office": "Corporate Office, Gurugram",
            "registration_ack_sent": True,
            "catering": "requested",
        },
    )
    assert result.entities.get("meeting_type") == "internal meeting"
    assert result.entities.get("dietary") == "non-vegetarian"
    assert result.entities.get("visitor_details")
    assert result.entities.get("preferred_time") == "10am"
    assert meeting_room_gaps(result.entities) == []


def test_parse_messy_signals_newline_range_and_ish_time():
    body = (
        "like 12-13\nemplyees from 10 to 1ish. 2 extrnal visitors coming also - rahul sharma"
    )
    got = parse_messy_meeting_signals(body)
    assert got.get("attendees") == 13
    assert got.get("preferred_time")
    assert got.get("end_time")
    assert got.get("duration_hours") == 3.0
    assert got.get("external_visitors") == 2
    assert parse_vehicle_plates("plate HR26 AB 1234") == ["HR26 AB 1234"]
    more = parse_messy_meeting_signals("1 more visitor: Priya Nair, Infosys\nparking for 1 car plate HR26 AB 1234")
    assert more.get("external_visitors_add") == 1
    assert "Priya" in (more.get("visitor_details_append") or "")
    assert "HR26" in (more.get("vehicle_numbers") or "")


def test_heuristic_messy_mail_headcount_and_bare_time_range():
    body = (
        "hi,\n\n"
        "need mtg room asap for tomorow or 25th oct whatever is free – like 12-13\n"
        "emplyees from 10 to 1ish at gurgaon / gurugram corp office.\n\n"
        "its an internal review only. 2 extrnal visitors coming also - rahul sharma "
        "& aman verma will join.\n\n"
        "pls arrnge tea/cofee , 2 veg n rest non veg ok. need display + vc for "
        "couple remote ppl.\n\n"
        "no guest car / parking needed.\n"
    )
    r = HeuristicProvider().extract(subject="meetng room req", body=body)
    assert r.entities.get("attendees") == 13
    assert r.entities.get("preferred_time")
    assert r.entities.get("end_time") or r.entities.get("duration_hours")
    assert r.entities.get("external_visitors") == 2
    gaps = meeting_room_gaps(r.entities)
    time_qs = [g["question"] for g in gaps if "time" in (g.get("question") or "").lower()]
    assert len(time_qs) <= 1
    assert "attendees" not in {g["field"] for g in gaps}
    assert "preferred_time" not in {g["field"] for g in gaps}


def test_gemini_blank_delta_filled_by_grounded_messy_parse():
    """ROOM-2026-0003 failure mode: Gemini answers but skips headcount/time."""
    body = (
        "hi,\n\n"
        "need mtg room asap for tomorow or 25th oct whatever is free – like 12-13\n"
        "emplyees from 10 to 1ish at gurgaon / gurugram corp office.\n\n"
        "its an internal review only. 2 extrnal visitors coming also - rahul sharma "
        "& aman verma will join.\n\n"
        "pls arrnge tea/cofee , 2 veg n rest non veg ok. need display + vc for "
        "couple remote ppl.\n\n"
        "no guest car / parking needed.\n"
    )
    gemini_partial = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="Request for a meeting room at Gurgaon office",
        entities={
            "date": "25th oct",
            "meeting_type": "internal meeting",
            "location_preference": "Corporate Office",
            "hybrid_av": "yes",
            "presentation_display": "yes",
            "catering": "requested",
            "dietary": "2 veg rest non veg",
        },
        fact_delta={"set": {}, "speech_acts": ["provide_facts"]},
        missing_information=[],
        confidence=0.86,
        reason="gemini:primary:gemini-3.5-flash-lite",
    )
    heuristic = HeuristicProvider().extract(subject="meetng room req", body=body)
    refined = refine_meeting_room_extraction(
        gemini_partial,
        subject="meetng room req",
        body=body,
        prior_facts={},
        heuristic_entities=heuristic.entities,
        primary_is_heuristic=False,
    )
    assert refined.entities.get("attendees") == 13
    assert refined.entities.get("preferred_time")
    assert refined.entities.get("end_time") or refined.entities.get("duration_hours")
    assert refined.entities.get("external_visitors") == 2
    missing_fields = {m.field for m in (refined.missing_information or [])}
    assert "attendees" not in missing_fields
    assert "preferred_time" not in missing_fields
    assert "duration" not in missing_fields


def test_confirm_reply_persists_spaced_plate_and_extra_visitor():
    """ROOM-2026-0005 failure: confirm + plate + extra visitor must persist."""
    body = (
        "confirm F2-R2.\n\n"
        "Change vs last note:\n"
        "- parking needed for 1 car — plate HR26 AB 1234\n"
        "- 1 more visitor: Priya Nair, Infosys\n"
        "- catering: 2 veg, rest non-veg (not all non-veg)\n\n"
        "Rest stays same (25 Oct, 10am–1pm, display + VC)."
    )
    prior = {
        "attendees": 12,
        "external_visitors": 2,
        "visitor_details": "Rahul Sharma and Aman Verma",
        "guest_vehicles": 0,
        "dietary": "non-vegetarian",
        "catering": "requested",
        "date": "25th oct",
        "preferred_time": "10am",
        "end_time": "1pm",
        "duration_hours": 3.0,
        "meeting_type": "internal meeting",
        "location_preference": "Corporate Office",
        "pending_confirmation": True,
        "proposed_room": {"name": "Meeting Room F2-R2"},
        "registration_ack_sent": True,
    }
    gemini_partial = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="User confirmed F2-R2, added HR26 AB 1234 and Priya Nair",
        entities={"dietary": "2 vegetarian, rest non-vegetarian", "guest_vehicles": 1},
        fact_delta={"set": {"guest_vehicles": 1}, "speech_acts": ["confirm"]},
        missing_information=[],
        confidence=0.9,
        reason="gemini",
    )
    heuristic = HeuristicProvider().extract(subject="Re: [CONFIRM BOOKING] [ROOM-2026-0005]", body=body, prior_facts=prior)
    refined = refine_meeting_room_extraction(
        gemini_partial,
        subject="Re: [CONFIRM BOOKING] [ROOM-2026-0005]",
        body=body,
        prior_facts=prior,
        heuristic_entities=heuristic.entities,
        primary_is_heuristic=False,
    )
    plates = refined.entities.get("vehicle_numbers") or ""
    assert "HR26" in plates and "1234" in plates
    assert refined.entities.get("guest_vehicles") == 1
    assert refined.entities.get("external_visitors") == 3
    details = refined.entities.get("visitor_details") or ""
    assert "Priya" in details
    assert "Rahul" in details
    assert "vehicle_numbers" not in {m.field for m in (refined.missing_information or [])}

    via_service = LLMService(provider=HeuristicProvider()).extract(
        subject="Re: [CONFIRM BOOKING] [ROOM-2026-0005]",
        body=body,
        prior_facts=prior,
    )
    assert "HR26" in (via_service.entities.get("vehicle_numbers") or "")
    assert via_service.entities.get("external_visitors") == 3
    assert "Priya" in (via_service.entities.get("visitor_details") or "")


def test_unmapped_ask_is_kept_on_open_requests():
    from app.engine.outcome_reducer import reduce_meeting_facts

    merged = reduce_meeting_facts(
        {
            "date": "25th oct",
            "attendees": 12,
            "preferred_time": "10am",
            "end_time": "1pm",
            "meeting_type": "internal meeting",
            "location_preference": "Corporate Office",
        },
        primary_entities={
            "open_requests": ["photographer for the review", "extra whiteboard markers"],
            "floor_change": "move to floor 3 if possible",
        },
        source_text="also need a photographer and extra whiteboard markers. try floor 3.",
    )
    texts = [
        (x.get("text") if isinstance(x, dict) else str(x)).lower()
        for x in (merged.get("open_requests") or [])
    ]
    blob = " ".join(texts)
    assert "photographer" in blob
    assert "whiteboard" in blob or "floor" in blob


def test_expected_participants_around_n_is_attendees():
    body = (
        "Hi,\n\nWe are having internal review meet and expected participants is around 20, "
        "we will need meeting room on 26th Sep.\n\nRegards,\n"
    )
    signals = parse_messy_meeting_signals(body)
    assert signals.get("attendees") == 20
    result = LLMService(provider=HeuristicProvider()).extract(subject="meeting room", body=body)
    assert result.entities.get("attendees") == 20
    assert result.entities.get("date")
    assert not result.entities.get("booking_confirmed")


def test_yahoo_inline_answers_are_not_lost_and_not_false_confirm():
    from app.services.email_utils import strip_for_ai

    body = (
        "Hi,\n\n"
        "Pls find the same\n\n"
        "Yahoo Mail: Search, organise, conquer\n\n"
        "  On Sun, 20 Sept 2026 at 12:03 pm, orchestration@adminservices.in"
        "<orchestration@adminservices.in> wrote:   Dear kapil mantri,\n\n"
        "Your meeting-room request has been registered as ROOM-2026-0008.\n\n"
        "Here’s what we already have on file (no need to repeat these):\n\n"
        "- Date: 26th sep\n"
        "- Meeting type: internal meeting\n"
        "- Hybrid / AV: to be confirmed\n"
        "- Presentation display: yes\n"
        "- Location preference: downtown\n"
        "- Catering / amenities: yes\n"
        "- Special access / security: 5 employee\n"
        "- Confidentiality: standard\n\n"
        "We only still need:\n\n"
        "- How many people will attend in person?\n"
        "- What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)? "
        "9.30 a. M to 6 p. M\n"
        "- Which office or building is required? Your primary office is Corporate Office - "
        "down town Gurugram.\n"
    )
    clean = strip_for_ai(body)
    assert "Pls find the same" in clean
    assert "5 employee" not in clean
    assert "to be confirmed" not in clean
    assert "9.30" in clean
    assert "6 p" in clean.lower() or "6p" in clean.lower().replace(" ", "")
    signals = parse_messy_meeting_signals(clean)
    assert signals.get("preferred_time")
    assert signals.get("end_time")
    result = LLMService(provider=HeuristicProvider()).extract(
        subject="Re: [INFORMATION REQUIRED] [ROOM-2026-0008] Request registered",
        body=body,
        prior_facts={
            "date": "26th sep",
            "meeting_type": "internal meeting",
            "registration_ack_sent": True,
            "primary_office": "Corporate Office, Gurugram",
        },
    )
    assert result.entities.get("booking_confirmed") is not True
    assert result.entities.get("attendees") != 5
    start = str(result.entities.get("preferred_time") or "").lower()
    end = str(result.entities.get("end_time") or "").lower()
    assert "9" in start
    assert "6" in end
    loc = str(result.entities.get("location_preference") or "").lower()
    assert "town" in loc or "gurugram" in loc


def test_five_employee_on_special_access_does_not_replace_headcount():
    from app.ai.messy_meeting_parse import parse_messy_meeting_signals
    from app.domain.meeting import Provenance
    from app.engine.outcome_reducer import reduce_meeting_facts

    leaked = (
        "Here’s what we already have on file:\n"
        "- Date: 26th sep\n"
        "- Special access / security: 5 employee\n"
        "- Confidentiality: standard\n"
    )
    signals = parse_messy_meeting_signals(leaked)
    assert signals.get("attendees") is None

    first = (
        "We are having internal review meet and expected participants is around 20, "
        "we will need meeting room on 26th Sep."
    )
    merged = reduce_meeting_facts(
        {},
        primary_entities=parse_messy_meeting_signals(first),
        source_text=first,
    )
    assert merged.get("attendees") == 20

    reply = (
        "Pls find the same\n\n"
        "On Sun, 20 Sept wrote:\n"
        "- Special access / security: 5 employee\n"
        "- How many people will attend in person?\n"
    )
    updated = reduce_meeting_facts(
        merged,
        primary_entities={
            "attendees": 5,
            "special_access": "5 employee",
        },
        source_text=reply,
        primary_provenance=Provenance.EXTRACTED,
    )
    assert updated.get("attendees") == 20
    sa = str(updated.get("special_access") or "")
    assert "5 employee" not in sa.lower()

    result = LLMService(provider=HeuristicProvider()).extract(
        subject="Re: ROOM-2026-0008",
        body=reply,
        prior_facts={"attendees": 20, "date": "26th sep", "meeting_type": "internal meeting"},
    )
    assert result.entities.get("attendees") == 20
    assert "5 employee" not in str(result.entities.get("special_access") or "").lower()


def test_interpreter_view_keeps_quote_for_the_model():
    from app.services.email_utils import prepare_interpreter_view

    body = (
        "Hi,\n\nPls find the same. also need a photographer.\n\n"
        "Yahoo Mail: Search, organise, conquer\n\n"
        "  On Sun, 20 Sept 2026 at 12:03 pm, orchestration@adminservices.in"
        "<orchestration@adminservices.in> wrote:   Dear kapil,\n\n"
        "Here’s what we already have on file:\n"
        "- Special access / security: 5 employee\n"
        "- What time slot do you need (e.g. 10:00 AM–1:00 PM)? 9.30 a. M to 6 p. M\n"
    )
    view = prepare_interpreter_view(body)
    assert "Pls find the same" in view["this_message"]
    assert "photographer" in view["this_message"].lower()
    assert "5 employee" not in view["combined_for_parsers"]
    assert "9.30" in view["combined_for_parsers"]
    assert "5 employee" in view["quoted_thread_excerpt"]
    assert any("9.30" in a for a in view["answers_typed_on_quoted_questions"])


def test_compact_interpreter_state_drops_platform_noise():
    from app.ai.meeting_extract import compact_interpreter_state

    slim = compact_interpreter_state(
        {
            "attendees": 20,
            "date": "26th sep",
            "decision_trace": ["a", "b"],
            "execution_plan": {"steps": [1]},
            "inventory_max_capacity": 40,
            "proposed_room": {"name": "Orchid", "id": "r1", "capacity": 24, "wifi": "yes"},
            "last_outbound": {"kind": "clarification", "questions": ["How many people?"]},
        }
    )
    assert slim["attendees"] == 20
    assert "decision_trace" not in slim
    assert "execution_plan" not in slim
    assert "inventory_max_capacity" not in slim
    assert slim["proposed_room"] == {"name": "Orchid", "id": "r1", "capacity": 24}
    assert slim["last_questions_we_sent"] == ["How many people?"]


def test_gemini_reads_mail_like_chat_not_a_form():
    from app.ai.gemini import GeminiProvider

    captured: dict = {}

    class CapturingGemini(GeminiProvider):
        def __init__(self):
            self.api_key = "k1"
            self.api_key_secondary = ""
            self.model = "gemini-3.5-flash-lite"
            self.fallback_model = "gemini-3.1-flash-lite"
            self._clients = {}
            self.last_endpoint = {}

        def _endpoints(self):
            return [("primary:lite", "k1", "lite")]

        def _generate_once(self, *, api_key, model, user_payload):
            captured["payload"] = user_payload

            class Resp:
                text = (
                    '{"event_type":"MEETING_ROOM","summary":"9:30-6 downtown plus photographer",'
                    '"entities":{"preferred_time":"9:30 AM","end_time":"6:00 PM",'
                    '"location_preference":"downtown Gurugram",'
                    '"open_requests":["photographer"]},'
                    '"open_requests":["photographer"],"issues":[],"missing_information":[],'
                    '"confidence":0.9,"reason":"gemini"}'
                )

            return Resp()

    yahoo = (
        "Hi,\n\nPls find the same. also need a photographer.\n\n"
        "Yahoo Mail: Search, organise, conquer\n\n"
        "  On Sun, 20 Sept 2026 at 12:03 pm, orchestration@adminservices.in"
        "<orchestration@adminservices.in> wrote:   Dear kapil,\n\n"
        "Here’s what we already have on file:\n"
        "- Special access / security: 5 employee\n"
        "- What time slot do you need (e.g. 10:00 AM–1:00 PM)? 9.30 a. M to 6 p. M\n"
    )
    result = LLMService(provider=CapturingGemini()).extract(
        subject="Re: ROOM-2026-0008",
        body=yahoo,
        prior_facts={
            "attendees": 20,
            "date": "26th sep",
            "decision_trace": ["noise"],
            "execution_plan": {"steps": [1]},
        },
    )
    payload = captured["payload"]
    assert "prior_facts" not in payload
    assert "this_message" in payload
    assert "Pls find the same" in payload["this_message"]
    assert "photographer" in payload["this_message"].lower()
    assert "5 employee" in (payload["quoted_thread"].get("excerpt") or "")
    assert payload["already_on_file"].get("attendees") == 20
    assert "decision_trace" not in payload["already_on_file"]
    assert "execution_plan" not in payload["already_on_file"]
    texts = [
        (x.get("text") if isinstance(x, dict) else str(x)).lower()
        for x in (result.entities.get("open_requests") or [])
    ]
    assert any("photographer" in t for t in texts)
    assert result.entities.get("attendees") == 20

