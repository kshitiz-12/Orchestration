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
    assert humanize_email_local("anonymousxo@gmail.com") == "there"


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
