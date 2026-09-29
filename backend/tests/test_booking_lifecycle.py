"""Time-slot bookings, hold expiry, cancel, post-booking changes, off-site / split,
extra-request ledger, approval routing, catering pricing and ops sender verification."""

import uuid
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.engine.pipeline import ProcessingPipeline
from app.engine.scenarios import ScenarioOrchestrator
from app.models.intake import Conversation, RawEmailEvent
from app.models.org import Contract, Resource, RoomBooking, utcnow
from app.models.outcome import Approval, Communication, Outcome
from app.schemas.ai import ExtractionResult
from app.services.communication import CommunicationService

ADMIN = "ops-desk@example.com"
REQ = "employee1@acme.demo"


def _tenant(session: Session) -> str:
    from app.models.org import Tenant

    return session.exec(select(Tenant)).first().tenant_id


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    monkeypatch.setattr("app.services.admin_commands.default_admin_interpreter", lambda: None)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _set(monkeypatch, **values) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, str(value))
    get_settings.cache_clear()


def _facts(**extra) -> dict:
    base = {
        "attendees": 5,
        "date": "15th october",
        "preferred_time": "3 pm",
        "end_time": "5pm",
        "duration_hours": 2.0,
        "meeting_type": "workshop",
        "location_preference": "Corporate Office",
        "catering": "none",
        "external_visitors": 0,
    }
    base.update(extra)
    return base


class Case:
    def __init__(self, session: Session, tid: str, thread: str, facts: dict, email: str = REQ):
        self.session, self.tid, self.email = session, tid, email
        self.orch = ScenarioOrchestrator(session, tid)
        self.conv = Conversation(tenant_id=tid, thread_id=thread, requester_email=email, subject="Room")
        session.add(self.conv)
        session.commit()
        self.n = 0
        self.outcome = self.reply(facts, summary="new request")

    def reply(self, entities: dict, *, summary: str = "reply", fact_delta: dict | None = None) -> Outcome:
        self.n += 1
        out = self.orch.orchestrate(
            extraction=ExtractionResult(
                event_type="MEETING_ROOM",
                summary=summary,
                entities=entities,
                missing_information=[],
                confidence=0.95,
                reason="test",
                fact_delta=fact_delta or {},
            ),
            requester_email=self.email,
            conversation_id=self.conv.conversation_id,
            business_event_id=f"evt_{self.conv.thread_id}_{self.n}",
            context={},
        )
        self.session.refresh(out)
        self.outcome = out
        return out

    def confirm(self) -> Outcome:
        return self.reply({**self.outcome.facts, "booking_confirmed": True}, summary="confirm")

    @property
    def facts(self) -> dict:
        return self.outcome.facts or {}

    def mails(self, to: str | None = None) -> list[Communication]:
        rows = self.session.exec(select(Communication).where(Communication.outcome_id == self.outcome.outcome_id)).all()
        return [m for m in rows if to is None or to in (m.recipients or [])]

    def bookings(self) -> list[RoomBooking]:
        return list(self.session.exec(select(RoomBooking).where(RoomBooking.outcome_id == self.outcome.outcome_id)).all())


def _room(session: Session, tid: str, name: str) -> Resource:
    return session.exec(select(Resource).where(Resource.tenant_id == tid, Resource.name == name)).first()


# ---------- 1. time-slot availability
def test_room_taken_at_that_time_is_skipped_but_free_on_another_day(session: Session, env):
    tid = _tenant(session)
    first = Case(session, tid, "t-slot-1", _facts())
    first_room = first.facts["proposed_room"]["name"]
    first.confirm()
    assert [b.status for b in first.bookings()] == ["CONFIRMED"]

    clash = Case(session, tid, "t-slot-2", _facts())
    assert clash.facts["proposed_room"]["name"] != first_room
    assert first_room in (clash.facts.get("busy_fit_rooms") or [])

    other_day = Case(session, tid, "t-slot-3", _facts(date="16th october"))
    assert other_day.facts["proposed_room"]["name"] == first_room


def test_room_status_is_never_flipped_globally(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-slot-status", _facts())
    case.confirm()
    room = session.get(Resource, case.facts["booked_room"]["resource_id"])
    assert room.status == "AVAILABLE"


# ---------- 2. hold expiry + reminders
def test_hold_reminder_then_expiry_then_confirm_rebooks(session: Session, env):
    from app.services.hold_sweeper import sweep_proposal_holds

    tid = _tenant(session)
    case = Case(session, tid, "t-hold", _facts())
    hold = case.bookings()[0]
    assert hold.status == "HELD" and hold.hold_expires_at

    comms = CommunicationService(session, tid)
    hold.created_at = utcnow() - timedelta(hours=13)
    session.add(hold)
    session.commit()
    assert sweep_proposal_holds(session, tid, comms=comms)["reminded"] == 1
    assert any("REMINDER" in (m.subject or "") for m in case.mails(REQ))

    hold.hold_expires_at = utcnow() - timedelta(minutes=1)
    session.add(hold)
    session.commit()
    assert sweep_proposal_holds(session, tid, comms=comms)["expired"] == 1
    session.refresh(hold)
    assert hold.status == "EXPIRED"
    assert any("HOLD RELEASED" in (m.subject or "") for m in case.mails(REQ))

    session.refresh(case.outcome)
    case.confirm()
    assert case.facts.get("booked_room")
    assert [b.status for b in case.bookings()] == ["CONFIRMED"]


# ---------- 3. cancel
def test_requester_cancel_releases_room(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-cancel", _facts())
    case.confirm()
    case.reply(
        {**case.facts, "raw_reply": "meeting is off, please drop it"},
        summary="cancel",
        fact_delta={"speech_acts": ["cancel"]},
    )
    assert case.outcome.status == "CANCELLED"
    assert case.facts["orchestration_stage"] == "CANCELLED"
    assert {b.status for b in case.bookings()} == {"CANCELLED"}
    assert any("CANCELLED" in (m.subject or "") for m in case.mails(REQ))


def test_admin_cancel_via_gemini(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-admin-cancel", _facts())

    class Fake:
        def interpret(self, payload):
            return {"action": "CANCEL", "reason": "Event postponed", "confidence": 0.9}, {"label": "fake"}

    env.setattr("app.services.admin_commands.default_admin_interpreter", lambda: Fake())
    ev = _admin_event(session, tid, case.outcome, "kill this one, event postponed")
    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["action"] == "CANCEL" and result["applied"] is True
    session.refresh(case.outcome)
    assert case.outcome.status == "CANCELLED"
    assert all(b.status == "CANCELLED" for b in case.bookings())


# ---------- 5. post-booking change
def test_headcount_change_after_booking_moves_room(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-post", _facts(attendees=5))
    case.confirm()
    old = case.facts["booked_room"]["name"]
    case.reply({**case.facts, "attendees": 14, "raw_reply": "we are now 14"}, summary="now 14")
    booked = case.facts["booked_room"]
    assert booked["name"] != old and booked["moved_from"] == old
    assert (session.get(Resource, booked["resource_id"]).attributes or {}).get("capacity") >= 14
    assert [b.room_name for b in case.bookings() if b.status == "CONFIRMED"] == [booked["name"]]
    assert any("ROOM CHANGED" in (m.subject or "") for m in case.mails(REQ))


def test_time_change_after_booking_keeps_room_when_free(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-post-time", _facts())
    case.confirm()
    room = case.facts["booked_room"]["name"]
    case.reply({**case.facts, "preferred_time": "11 am", "end_time": "1 pm"}, summary="move to 11")
    assert case.facts["booked_room"]["name"] == room
    row = [b for b in case.bookings() if b.status == "CONFIRMED"][0]
    assert row.starts_at.hour <= 11
    assert any("BOOKING UPDATED" in (m.subject or "") for m in case.mails(REQ))


# ---------- 6. off-site + split
def test_larger_venue_choice_holds_offsite_venue(session: Session, env):
    _set(env, OFFSITE_VENUES="Hyatt Ballroom:120")
    tid = _tenant(session)
    case = Case(session, tid, "t-offsite", _facts(attendees=80, meeting_type="internal meeting"))
    assert case.facts["orchestration_stage"] == "NO_RESOURCE"
    assert (case.facts.get("offsite_option") or {}).get("name") == "Hyatt Ballroom"

    case.reply(
        {**case.facts, "raw_reply": "sure, the hotel works"},
        fact_delta={"speech_acts": ["provide_facts"], "alternative_choice": "LARGER_VENUE"},
    )
    proposal = case.facts["proposed_room"]
    assert proposal["name"] == "Hyatt Ballroom" and proposal.get("external_venue")
    case.confirm()
    rows = [b for b in case.bookings() if b.status == "CONFIRMED"]
    assert len(rows) == 1 and rows[0].is_offsite


def test_split_choice_books_several_rooms(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-split", _facts(attendees=50, meeting_type="internal meeting"))
    assert case.facts["orchestration_stage"] == "NO_RESOURCE"
    assert case.facts.get("split_option")

    case.reply(
        {**case.facts, "raw_reply": "ok do two rooms"},
        fact_delta={"speech_acts": ["provide_facts"], "alternative_choice": "SPLIT_ROOMS"},
    )
    proposal = case.facts["proposed_room"]
    assert proposal.get("split") and len(proposal["rooms"]) >= 2
    assert sum(r["capacity"] for r in proposal["rooms"]) >= 50
    case.confirm()
    confirmed = [b for b in case.bookings() if b.status == "CONFIRMED"]
    assert len(confirmed) == len(proposal["rooms"])


def test_gemini_none_choice_overrides_regex(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-choice-none", _facts(attendees=80, meeting_type="internal meeting"))
    case.reply(
        {**case.facts, "raw_reply": "why can't you escalate for larger venue earlier?"},
        fact_delta={"speech_acts": ["provide_facts"], "alternative_choice": "NONE"},
    )
    assert not case.facts.get("no_resource_choice")


# ---------- 7. extra-request ledger
def test_every_extra_ask_is_kept():
    from app.ai.meeting_extract import refine_meeting_room_extraction

    ex = ExtractionResult(
        event_type="MEETING_ROOM",
        summary="room + extras",
        entities={"attendees": 20, "open_requests": ["photographer"]},
        open_requests=["photographer", "name tents", "translator"],
        missing_information=[],
        confidence=0.9,
        reason="gemini",
    )
    out = refine_meeting_room_extraction(
        ex,
        subject="room",
        body="need photographer, name tents and a translator",
        prior_facts={"open_requests": [{"text": "extra chairs", "status": "noted"}]},
    )
    texts = {r["text"].lower() for r in out.entities["open_requests"]}
    assert {"extra chairs", "photographer", "name tents", "translator"} <= texts


# ---------- 8. approval routing + 9. catering pricing
def test_catering_approval_goes_to_manager_with_contract_rate(session: Session, env):
    _set(env, APPROVAL_MANAGER_EMAIL="mgr@example.com", CATERING_VENDOR_NAME="FreshServe")
    tid = _tenant(session)
    case = Case(session, tid, "t-cater", _facts(attendees=6, catering="lunch", dietary="all veg"))
    contract = session.exec(select(Contract).where(Contract.name == "CAT-GGN-2026-04")).first()
    contract.rate_card = {**contract.rate_card, "unit_rate": 600.0}
    session.add(contract)
    session.commit()
    case.confirm()

    quote = case.facts["catering_quote"]
    assert quote["rate"] == 600.0 and quote["amount_ex_tax"] == 3600.0 and quote["rate_source"] == "contract"
    assert "acceptance_breach_demo" not in (case.facts.get("vendor_sla") or {})
    assert any("Approval needed" in (m.body or "") or "APPROVAL" in (m.subject or "").upper()
               for m in case.mails("mgr@example.com"))

    ev = _admin_event(session, tid, case.outcome, "approved", sender="Manager <mgr@example.com>")
    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["status"] == "admin_command" and result["applied"] is True
    session.refresh(case.outcome)
    assert case.outcome.facts.get("catering_assigned") is True
    assert "accepted_late_minutes" not in (case.outcome.facts.get("vendor_sla") or {})


def test_catering_under_limit_is_auto_approved(session: Session, env):
    _set(env, CATERING_AUTO_APPROVE_LIMIT=100000)
    tid = _tenant(session)
    case = Case(session, tid, "t-cater-auto", _facts(attendees=6, catering="lunch", dietary="all veg"))
    case.confirm()
    assert case.facts.get("catering_auto_approved") is True
    assert case.facts.get("catering_assigned") is True
    pending = session.exec(
        select(Approval).where(Approval.outcome_id == case.outcome.outcome_id, Approval.decision == "PENDING")
    ).all()
    assert not pending


# ---------- 4. ops sender verification
def _admin_event(session, tid, outcome, body, *, sender=f"Ops Desk <{ADMIN}>", headers=None) -> RawEmailEvent:
    mid = f"<{uuid.uuid4().hex}@mail>"
    ev = RawEmailEvent(
        tenant_id=tid,
        idempotency_key=mid,
        provider="CLOUDMAILIN",
        provider_message_id=mid,
        gmail_message_id=mid,
        source="CLOUDMAILIN",
        sender=sender,
        subject=f"Re: [OPS UPDATE] [{outcome.case_reference}] briefing",
        body_text=body,
        body_for_ai=body,
        headers=headers or {},
    )
    session.add(ev)
    session.commit()
    return ev


def test_spoofed_ops_mail_is_not_applied(session: Session, env):
    _set(env, ADMIN_SENDER_VERIFICATION="strict")
    tid = _tenant(session)
    case = Case(session, tid, "t-spoof", _facts())
    ev = _admin_event(session, tid, case.outcome, "book Auditorium A")
    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["status"] == "admin_unverified" and result["applied"] is False
    session.refresh(case.outcome)
    assert not case.outcome.facts.get("booked_room")
    assert any("could not be verified" in (m.body or "") for m in case.mails(ADMIN))


def test_reply_to_our_briefing_is_trusted(session: Session, env):
    _set(env, ADMIN_SENDER_VERIFICATION="strict", ADMIN_FYI_LEVEL="all")
    tid = _tenant(session)
    case = Case(session, tid, "t-verified-thread", _facts())
    briefing = case.mails(ADMIN)[-1]
    briefing.provider_message_id = "<brief-123@cloudmta.net>"
    session.add(briefing)
    session.commit()
    ev = _admin_event(session, tid, case.outcome, "book Auditorium A", headers={"In-Reply-To": "<brief-123@cloudmta.net>"})
    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["status"] == "admin_command" and result["sender_verification"] == "reply_to_our_mail"
    session.refresh(case.outcome)
    assert case.outcome.facts["booked_room"]["name"] == "Auditorium A"


def test_spf_pass_for_sender_domain_is_trusted(session: Session, env):
    _set(env, ADMIN_SENDER_VERIFICATION="strict")
    tid = _tenant(session)
    case = Case(session, tid, "t-verified-spf", _facts())
    ev = _admin_event(
        session, tid, case.outcome, "book Auditorium A",
        headers={"_envelope": {"spf": {"result": "pass", "domain": "example.com"}}},
    )
    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["status"] == "admin_command" and result["sender_verification"] == "spf_pass"


def test_booking_a_room_busy_for_another_case_is_refused(session: Session, env):
    tid = _tenant(session)
    first = Case(session, tid, "t-busy-1", _facts(attendees=30, meeting_type="internal meeting"))
    if not first.facts.get("booked_room"):
        first.confirm()
    assert first.facts["booked_room"]["name"] == "Auditorium A"
    second = Case(session, tid, "t-busy-2", _facts(attendees=4))
    ev = _admin_event(session, tid, second.outcome, "book Auditorium A")
    result = ProcessingPipeline(session, tid).process_event(ev.event_id)
    assert result["applied"] is False and "already booked" in result["summary"]
