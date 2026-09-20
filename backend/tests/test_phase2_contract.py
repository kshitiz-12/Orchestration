"""Phase 2: field contract, operator override, suppressed outbound."""

from app.domain.meeting import Provenance, build_field_contract
from app.engine.outcome_reducer import apply_operator_override, reduce_meeting_facts


def test_field_contract_separates_understood_assumed_missing():
    facts = reduce_meeting_facts(
        {
            "registration_ack_sent": True,
            "primary_office": "Corporate Office, Gurugram",
            "defaults_applied": ["location_preference"],
            "location_preference": "Corporate Office, Gurugram",
            "field_provenance": {
                "location_preference": Provenance.MASTER.value,
            },
        },
        primary_entities={
            "date": "25th Oct",
            "preferred_time": "10am",
            "end_time": "1pm",
            "duration_hours": 3.0,
            "meeting_type": "internal meeting",
        },
        primary_provenance=Provenance.EXTRACTED,
        source_text="internal review 25th Oct 10am to 1pm",
    )
    contract = facts.get("field_contract") or build_field_contract(facts)
    understood_fields = {r["field"] for r in contract["understood"]}
    assumed_fields = {r["field"] for r in contract["assumed"]}
    missing_fields = {r["field"] for r in contract["missing"]}
    assert "date" in understood_fields
    assert "meeting_type" in understood_fields
    assert "location_preference" in assumed_fields or "location_preference" in understood_fields
    assert "attendees" in missing_fields
    assert contract["complete"] is False
    assert facts["field_status"]["attendees"]["status"] == "blocking"


def test_operator_override_sets_user_confirmed_and_clears_gap():
    prior = reduce_meeting_facts(
        {"registration_ack_sent": True},
        primary_entities={
            "date": "25th Oct",
            "preferred_time": "10am",
            "end_time": "1pm",
            "duration_hours": 3.0,
            "meeting_type": "internal meeting",
            "location_preference": "Gurugram",
        },
        source_text="25th Oct 10am to 1pm internal Gurugram",
    )
    assert "attendees" in (prior.get("checklist_missing") or [])
    updated = apply_operator_override(prior, {"attendees": 12}, actor="ops@example.com")
    assert updated["attendees"] == 12
    assert updated["field_provenance"]["attendees"] == Provenance.USER_CONFIRMED.value
    assert "attendees" not in (updated.get("checklist_missing") or [])
    contract = updated["field_contract"]
    assert any(r["field"] == "attendees" and r["status"] == "stated" for r in contract["understood"])


def test_heuristic_fill_marked_candidate_provenance():
    merged = reduce_meeting_facts(
        {"registration_ack_sent": True},
        primary_entities={"date": "25th Oct", "meeting_type": "internal meeting"},
        candidate_entities={"attendees": 12, "preferred_time": "10am"},
        source_text="for 12 people on 25th Oct at 10am internal",
        primary_provenance=Provenance.EXTRACTED,
    )
    assert merged["attendees"] == 12
    assert merged["field_provenance"]["attendees"] == Provenance.CANDIDATE_HEURISTIC.value
    assert merged["field_provenance"]["date"] == Provenance.EXTRACTED.value


def test_record_suppressed_writes_reason_and_history(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.services import communication as comm_mod
    from app.services.communication import CommunicationService

    monkeypatch.setattr(comm_mod, "flag_modified", lambda *_a, **_k: None)

    session = MagicMock()
    outcome = SimpleNamespace(
        outcome_id="out_1",
        case_reference="ROOM-1",
        facts={},
    )
    svc = CommunicationService(session, "ten_1", email_sender=None)
    svc.audit = MagicMock()
    svc.record_suppressed(
        outcome=outcome,
        reason="duplicate_idempotency_key",
        detail={"idempotency_key": "clarify:abc:1"},
    )
    assert outcome.facts["last_outbound"]["status"] == "SUPPRESSED"
    assert outcome.facts["last_outbound"]["reason"] == "duplicate_idempotency_key"
    assert len(outcome.facts["outbound_suppressions"]) == 1
    action = svc.audit.record.call_args.kwargs["action"]
    assert getattr(action, "value", action) == "COMMUNICATION_SUPPRESSED"


def test_requirement_split_confirmed_upper_unconfirmed_lower():
    from app.services.meeting_room import apply_meeting_room_defaults, requirement_email_sections

    facts = apply_meeting_room_defaults(
        {
            "date": "26th sep",
            "meeting_type": "internal meeting",
            "field_provenance": {
                "date": "extracted",
                "meeting_type": "extracted",
            },
        }
    )
    confirmed, unconfirmed = requirement_email_sections(facts)
    upper = " ".join(confirmed).lower()
    lower = " ".join(unconfirmed).lower()
    assert "26th sep" in upper
    assert "internal meeting" in upper
    assert "to be confirmed" not in upper
    assert "presentation display" not in upper
    assert "confidentiality" not in upper
    assert "catering" not in upper
    assert any("presentation" in line.lower() or "catering" in line.lower() for line in unconfirmed)
    assert "assumed" in lower or "not answered" in lower


def test_extracted_explicit_none_stays_in_confirmed():
    from app.services.meeting_room import requirement_email_sections

    confirmed, unconfirmed = requirement_email_sections(
        {
            "date": "26th sep",
            "attendees": 20,
            "preferred_time": "9:30 AM",
            "end_time": "6:00 PM",
            "catering": "none",
            "field_provenance": {
                "date": "extracted",
                "attendees": "extracted",
                "preferred_time": "extracted",
                "end_time": "extracted",
                "catering": "extracted",
            },
        }
    )
    upper = " ".join(confirmed).lower()
    assert "20" in upper
    assert "9:30" in upper
    assert "catering" in upper
    assert not any("catering" in line.lower() for line in unconfirmed)