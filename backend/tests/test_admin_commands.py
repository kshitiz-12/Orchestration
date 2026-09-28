"""Admin reply-by-mail commands."""

import uuid

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.engine.pipeline import ProcessingPipeline
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import Conversation, RawEmailEvent
from app.models.outcome import Communication, ExceptionRecord, Outcome
from app.schemas.ai import ExtractionResult
from app.services.admin_commands import admin_reply_text, parse_admin_command

ADMIN = "ops-desk@example.com"


def _tenant(session: Session) -> str:
    from app.models.org import Tenant

    t = session.exec(select(Tenant)).first()
    assert t
    return t.tenant_id


class FakeGemini:
    """Stands in for Gemini: returns a canned decision and captures the payload it was shown."""

    def __init__(self, decision=None, error: Exception | None = None):
        self.decision = decision or {}
        self.error = error
        self.payloads: list[dict] = []

    def interpret(self, payload):
        self.payloads.append(payload)
        if self.error:
            raise self.error
        return self.decision, {"label": "primary:fake", "model": "fake"}


@pytest.fixture
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    get_settings.cache_clear()
    # Default: no model available → rules fallback (tests that want Gemini override this)
    monkeypatch.setattr("app.services.admin_commands.default_admin_interpreter", lambda: None)
    yield
    get_settings.cache_clear()


def _use_gemini(monkeypatch, fake: FakeGemini) -> None:
    monkeypatch.setattr("app.services.admin_commands.default_admin_interpreter", lambda: fake)


def _no_resource_case(session: Session, tid: str, thread: str) -> Outcome:
    orch = ScenarioOrchestrator(session, tid)
    conv = Conversation(tenant_id=tid, thread_id=thread, requester_email="big.team@company.com", subject="All-hands")
    session.add(conv)
    session.commit()
    base = {
        "attendees": 80,
        "date": "22 September 2026",
        "preferred_time": "2:00 PM",
        "end_time": "5:00 PM",
        "duration_hours": 3.0,
        "meeting_type": "internal meeting",
        "location_preference": "Corporate Office",
        "presentation_display": "yes",
        "catering": "none",
        "external_visitors": 0,
    }
    outcome = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM", summary="80 people", entities=base,
            missing_information=[], confidence=0.95, reason="complete",
        ),
        requester_email="big.team@company.com",
        conversation_id=conv.conversation_id,
        business_event_id=f"evt_{thread}_1",
        context={},
    )
    outcome = orch.orchestrate(
        extraction=ExtractionResult(
            event_type="MEETING_ROOM", summary="Meeting for 80",
            entities={**base, "raw_reply": "escalate for larger venue"},
            missing_information=[], confidence=0.9, reason="choice",
        ),
        requester_email="big.team@company.com",
        conversation_id=conv.conversation_id,
        business_event_id=f"evt_{thread}_2",
        context={},
    )
    assert outcome.facts.get("orchestration_stage") == "NO_RESOURCE"
    assert (outcome.facts.get("no_resource_choice") or {}).get("code") == "LARGER_VENUE"
    return outcome


def _admin_mail(session: Session, tid: str, outcome: Outcome, body: str) -> RawEmailEvent:
    mid = f"<{uuid.uuid4().hex}@mail>"
    ev = RawEmailEvent(
        tenant_id=tid,
        idempotency_key=mid,
        provider="CLOUDMAILIN",
        provider_message_id=mid,
        gmail_message_id=mid,
        source="CLOUDMAILIN",
        sender=f"Ops Desk <{ADMIN}>",
        subject=f"Re: [OPS DECISION] [{outcome.case_reference}] OPS DECISION: Requester selected alternative",
        body_text=body,
        body_for_ai=body,
    )
    session.add(ev)
    session.commit()
    return ev


def _mails(session: Session, outcome: Outcome) -> list[Communication]:
    return list(session.exec(select(Communication).where(Communication.outcome_id == outcome.outcome_id)).all())


def test_rules_fallback_shape():
    assert parse_admin_command("Approve")["action"] == "APPROVE"
    assert parse_admin_command("ok")["action"] == "APPROVE"
    rej = parse_admin_command("Reject - budget freeze this quarter")
    assert rej["action"] == "REJECT" and "budget" in rej["reason"]
    book = parse_admin_command("book Hyatt Regency Ballroom")
    assert book["action"] == "BOOK" and book["room"] == "Hyatt Regency Ballroom"
    msg = parse_admin_command("MESSAGE: venue visit on Monday 11am")
    assert msg["action"] == "MESSAGE_REQUESTER" and "Monday" in msg["message_to_requester"]
    assert parse_admin_command("split into two rooms")["choice_code"] == "SPLIT_ROOMS"
    assert parse_admin_command("hmm let me check")["action"] == "NONE"


def test_normalize_gemini_output_is_defensive():
    from app.ai.admin_interpreter import normalize_admin_decision

    d = normalize_admin_decision(
        {
            "action": "update facts",
            "fact_updates": {"attendees": 25, "not_a_field": "x", "date": ""},
            "choice_code": "teleport",
            "confidence": "0.8",
        }
    )
    assert d["action"] == "UPDATE_FACTS"
    assert d["fact_updates"] == {"attendees": 25}
    assert d["choice_code"] is None
    assert d["confidence"] == 0.8
    assert normalize_admin_decision({"action": "launch missiles"})["action"] == "NONE"


def test_reply_text_ignores_quoted_briefing():
    body = "Approve\n\nOn Sun, 20 Sept 2026 at 8:36 pm, orchestration@x wrote:\n> REJECT this\n> BOOK F1"
    assert admin_reply_text(body).strip() == "Approve"


def test_admin_approve_on_no_resource_informs_requester(session: Session, admin_env):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-admin-approve")
    ev = _admin_mail(session, tid, outcome, "Approve\n\nOn Sun, ops wrote:\n> OPS DECISION ...")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["status"] == "admin_command"
    assert result["action"] == "APPROVE" and result["applied"] is True

    session.refresh(outcome)
    facts = outcome.facts
    assert facts["orchestration_stage"] == "NO_RESOURCE"
    assert facts["admin_decision"]["decision"] == "APPROVED"
    assert facts["last_action"] == "admin_approved:LARGER_VENUE"
    assert facts.get("raw_reply") != "Approve"

    mails = _mails(session, outcome)
    to_req = [m for m in mails if "big.team@company.com" in (m.recipients or []) and "OPS APPROVED" in (m.subject or "")]
    assert to_req and "larger venue" in (to_req[0].body or "").lower()
    acks = [m for m in mails if ADMIN in (m.recipients or []) and "OPS DONE" in (m.subject or "")]
    assert acks and "once the venue is fixed" in (acks[0].body or "")


def test_admin_book_offsite_resolves_exception(session: Session, admin_env):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-admin-book")
    ev = _admin_mail(session, tid, outcome, "book Hyatt Regency Ballroom")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["action"] == "BOOK" and result["applied"] is True

    session.refresh(outcome)
    assert (outcome.facts.get("booked_room") or {}).get("name") == "Hyatt Regency Ballroom"
    mails = _mails(session, outcome)
    assert any(
        "BOOKING CONFIRMED" in (m.subject or "") and "big.team@company.com" in (m.recipients or [])
        for m in mails
    )
    open_exc = session.exec(
        select(ExceptionRecord).where(
            ExceptionRecord.outcome_id == outcome.outcome_id,
            ExceptionRecord.exception_type == "NO_MEETING_ROOM",
            ExceptionRecord.status == "OPEN",
        )
    ).all()
    assert not open_exc


def test_admin_reject_asks_requester_for_another_option(session: Session, admin_env):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-admin-reject")
    ev = _admin_mail(session, tid, outcome, "reject - no off-site budget")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["action"] == "REJECT" and result["applied"] is True
    session.refresh(outcome)
    assert "no_resource_choice" not in outcome.facts
    to_req = [
        m for m in _mails(session, outcome)
        if "big.team@company.com" in (m.recipients or []) and "OPS UPDATE" in (m.subject or "")
    ]
    assert to_req and "no off-site budget" in (to_req[-1].body or "")


def test_admin_unknown_reply_changes_nothing(session: Session, admin_env):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-admin-unknown")
    before = outcome.facts.get("last_action")
    ev = _admin_mail(session, tid, outcome, "let me check with facilities")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["action"] == "NONE" and result["applied"] is False
    session.refresh(outcome)
    assert outcome.facts.get("last_action") == before
    acks = [m for m in _mails(session, outcome) if ADMIN in (m.recipients or []) and "OPS NOT APPLIED" in (m.subject or "")]
    assert acks and "own words" in (acks[0].body or "")


def test_gemini_reads_free_text_book_plus_message(session: Session, admin_env, monkeypatch):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-gem-book")
    fake = FakeGemini(
        {
            "action": "BOOK",
            "room": "Hyatt Regency Ballroom",
            "message_to_requester": "We have a venue walkthrough on Monday at 11am if you'd like to join.",
            "understood_as": "Book Hyatt Regency Ballroom off-site and share the Monday 11am walkthrough",
            "confidence": 0.93,
        }
    )
    _use_gemini(monkeypatch, fake)
    ev = _admin_mail(
        session, tid, outcome,
        "haan theek hai, hyatt ballroom le lo unke liye. bol dena monday 11 baje venue dekh sakte hai",
    )

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["interpretation_path"] == "gemini:primary:fake"
    assert result["action"] == "BOOK" and result["applied"] is True

    payload = fake.payloads[0]
    assert payload["admin_typed"].startswith("haan theek hai")
    assert payload["case"]["stage"] == "NO_RESOURCE"
    assert payload["case"]["requester_choice"]["code"] == "LARGER_VENUE"
    assert payload["rooms_in_inventory"]

    session.refresh(outcome)
    assert outcome.facts["booked_room"]["name"] == "Hyatt Regency Ballroom"
    to_req = [m for m in _mails(session, outcome) if "big.team@company.com" in (m.recipients or [])]
    assert any("BOOKING CONFIRMED" in (m.subject or "") for m in to_req)
    assert any("UPDATE FROM OPS" in (m.subject or "") and "Monday at 11am" in (m.body or "") for m in to_req)
    assert outcome.facts["admin_commands"][-1]["understood_as"].startswith("Book Hyatt")


def test_gemini_fact_update_reruns_search(session: Session, admin_env, monkeypatch):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-gem-facts")
    _use_gemini(
        monkeypatch,
        FakeGemini(
            {
                "action": "UPDATE_FACTS",
                "fact_updates": {"attendees": 8},
                "understood_as": "Cut headcount to 8 and re-check rooms",
                "confidence": 0.9,
            }
        ),
    )
    ev = _admin_mail(session, tid, outcome, "only 8 of them are actually coming, sort it")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["action"] == "UPDATE_FACTS" and result["applied"] is True
    session.refresh(outcome)
    assert int(outcome.facts["attendees"]) == 8
    assert outcome.facts["orchestration_stage"] != "NO_RESOURCE"
    acks = [m for m in _mails(session, outcome) if ADMIN in (m.recipients or []) and "OPS DONE" in (m.subject or "")]
    assert acks and "attendees → 8" in (acks[-1].body or "")


def test_gemini_unsure_changes_nothing(session: Session, admin_env, monkeypatch):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-gem-unsure")
    before = dict(outcome.facts)
    _use_gemini(
        monkeypatch,
        FakeGemini(
            {
                "action": "BOOK",
                "room": None,
                "confidence": 0.4,
                "needs_clarification": True,
                "clarification_question": "Which venue should I book — the Hyatt or the auditorium?",
            }
        ),
    )
    ev = _admin_mail(session, tid, outcome, "book the one we discussed")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["applied"] is False
    session.refresh(outcome)
    assert not outcome.facts.get("booked_room")
    assert outcome.facts.get("last_action") == before.get("last_action")
    acks = [m for m in _mails(session, outcome) if ADMIN in (m.recipients or []) and "OPS NOT APPLIED" in (m.subject or "")]
    assert acks and "Which venue" in (acks[-1].body or "")


def test_gemini_outage_falls_back_to_rules(session: Session, admin_env, monkeypatch):
    tid = _tenant(session)
    outcome = _no_resource_case(session, tid, "t-gem-down")
    _use_gemini(monkeypatch, FakeGemini(error=RuntimeError("503 unavailable")))
    ev = _admin_mail(session, tid, outcome, "Approve")

    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["interpretation_path"] == "rules_fallback"
    assert result["action"] == "APPROVE" and result["applied"] is True
