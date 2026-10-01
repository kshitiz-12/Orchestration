"""Spec scenarios: chargeable-only approval, per-owner task lists, READY / COMPLETED, one reminder then one
escalation, service entry + invoice matching, training (multi-day) events and signed approval links."""

import re
import uuid
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.engine.event_services import build_package_items
from app.engine.meeting_scenario import ClientMeetingOrchestrator
from app.engine.outcome_engine import OutcomeEngine
from app.engine.pipeline import ProcessingPipeline
from app.engine.scenarios import ScenarioOrchestrator
from app.models.company import Department
from app.models.intake import Conversation, RawEmailEvent
from app.models.org import RoomBooking, utcnow
from app.models.outcome import Approval, Communication, Outcome, Requirement
from app.schemas.ai import ExtractionResult
from app.services.approval_links import approval_link, verify
from app.services.communication import CommunicationService

ADMIN = "ops-desk@example.com"
REQ = "employee1@acme.demo"
CAFE = "cafe@example.com"


def _tenant(session: Session) -> str:
    from app.models.org import Tenant

    return session.exec(select(Tenant)).first().tenant_id


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    monkeypatch.setenv("APPROVAL_MANAGER_EMAIL", "mgr@example.com")
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
        "attendees": 6,
        "date": "15th october",
        "preferred_time": "3 pm",
        "end_time": "5pm",
        "duration_hours": 2.0,
        "meeting_type": "team review",
        "location_preference": "Corporate Office",
        "catering": "none",
        "external_visitors": 0,
        "hybrid_av": "no",
        "dietary": "all veg",
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

    def reply(self, entities: dict, *, summary: str = "reply") -> Outcome:
        self.n += 1
        out = self.orch.orchestrate(
            extraction=ExtractionResult(
                event_type="MEETING_ROOM",
                summary=summary,
                entities=entities,
                missing_information=[],
                confidence=0.95,
                reason="test",
            ),
            requester_email=self.email,
            conversation_id=self.conv.conversation_id,
            business_event_id=f"evt_{self.conv.thread_id}_{self.n}",
            context={},
        )
        self.session.refresh(out)
        self.outcome = out
        return out

    def say(self, text: str) -> Outcome:
        return self.reply({"raw_reply": text}, summary=text)

    def confirm(self) -> Outcome:
        if self.facts.get("booked_room"):
            return self.outcome
        return self.reply({**self.outcome.facts, "booking_confirmed": True}, summary="confirm")

    @property
    def facts(self) -> dict:
        return self.outcome.facts or {}

    def mails(self, to: str | None = None) -> list[Communication]:
        rows = self.session.exec(select(Communication).where(Communication.outcome_id == self.outcome.outcome_id)).all()
        return [m for m in rows if to is None or to in (m.recipients or [])]

    def subjects(self, to: str | None = None) -> list[str]:
        return [m.subject or "" for m in self.mails(to)]

    def orchestrator(self) -> ClientMeetingOrchestrator:
        return ClientMeetingOrchestrator(
            self.session, self.tid, OutcomeEngine(self.session, self.tid), CommunicationService(self.session, self.tid)
        )


def _event(session, tid, outcome, body, *, sender) -> RawEmailEvent:
    mid = f"<{uuid.uuid4().hex}@mail>"
    ev = RawEmailEvent(
        tenant_id=tid,
        idempotency_key=mid,
        provider="CLOUDMAILIN",
        provider_message_id=mid,
        gmail_message_id=mid,
        source="CLOUDMAILIN",
        sender=sender,
        subject=f"Re: [ACTION REQUIRED] [{outcome.case_reference}] tasks",
        body_text=body,
        body_for_ai=body,
        headers={},
    )
    session.add(ev)
    session.commit()
    return ev


def _real_cafeteria(session: Session, tid: str) -> None:
    for dept in session.exec(select(Department).where(Department.tenant_id == tid)).all():
        if "catering" in (dept.categories or []):
            dept.categories = [c for c in dept.categories if c != "catering"]
            session.add(dept)
    session.add(Department(tenant_id=tid, code="CAFE_TEST", name="Cafeteria", categories=["catering"], primary_email=CAFE))
    session.commit()


# ---------- chargeable-only approval
def test_included_services_need_no_approval_and_close_financially(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-incl", _facts(catering="tea and coffee", presentation_display="yes"))
    case.confirm()
    plan = case.facts["cost_plan"]
    assert plan["chargeable"] == [] and "Tea / coffee (vending and pantry)" in plan["included"]
    assert not session.exec(select(Approval).where(Approval.outcome_id == case.outcome.outcome_id)).all()
    invoice = session.exec(
        select(Requirement).where(Requirement.outcome_id == case.outcome.outcome_id, Requirement.code == "INVOICE")
    ).first()
    assert invoice.applicability == "NOT_APPLICABLE"
    confirmed = next(m for m in case.mails(REQ) if "BOOKING CONFIRMED" in (m.subject or ""))
    assert "No separate approval is needed" in confirmed.body

    case.say("all good, satisfied")
    assert case.facts["operational_status"] == "CLOSED" and case.facts["financial_status"] == "CLOSED"


def test_approval_covers_only_the_chargeable_part(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-charge", _facts(catering="high tea and coffee", attendees=10))
    case.confirm()
    plan = case.facts["cost_plan"]
    assert plan["chargeable"] == ["High tea / snacks (special menu)"]
    assert "Tea / coffee (vending and pantry)" in plan["included"]
    approval = session.exec(select(Approval).where(Approval.outcome_id == case.outcome.outcome_id)).first()
    assert approval.approval_type == "CATERING_SPEND" and approval.decision == "PENDING"
    mail = next(m for m in case.mails("mgr@example.com") if "[APPROVAL REQUIRED]" in (m.subject or ""))
    assert "only for the chargeable part" in mail.body and "Included at no incremental charge" in mail.body


# ---------- per-owner task lists, READY
def test_real_department_gets_its_list_and_done_marks_ready(session: Session, env):
    _set(env, CATERING_AUTO_APPROVE_LIMIT=100000)
    tid = _tenant(session)
    _real_cafeteria(session, tid)
    case = Case(session, tid, "t-pkg", _facts(catering="lunch", dietary="all veg"))
    case.confirm()

    packages = {p["owner"]: p for p in case.facts["task_packages"]}
    assert packages["CAFETERIA"]["recipients"] == [CAFE] and not packages["CAFETERIA"]["redirected"]
    assert packages["ADMIN"]["redirected"]
    cafe_mail = [m for m in case.mails(CAFE) if "[ACTION REQUIRED]" in (m.subject or "")]
    assert len(cafe_mail) == 1 and "Working lunch" in cafe_mail[0].body and "Ready by:" in cafe_mail[0].body
    admin_mails = [m for m in case.mails(ADMIN) if "Booking confirmed" in (m.body or "")]
    assert admin_mails and "Task lists by owner:" in admin_mails[-1].body

    result = ProcessingPipeline(session, tid).process_event(_event(session, tid, case.outcome, "done", sender=CAFE).event_id)
    assert result["action"] == "PACKAGE_DONE"
    session.refresh(case.outcome)
    assert {p["owner"]: p for p in case.facts["task_packages"]}["CAFETERIA"]["status"] == "DONE"
    assert not any("[READY]" in s for s in case.subjects(REQ))

    ProcessingPipeline(session, tid).process_event(_event(session, tid, case.outcome, "done", sender=ADMIN).event_id)
    session.refresh(case.outcome)
    assert case.facts["orchestration_stage"] == "READY"
    assert any("[READY]" in s for s in case.subjects(REQ))


def test_department_issue_raises_at_risk(session: Session, env):
    _set(env, CATERING_AUTO_APPROVE_LIMIT=100000)
    tid = _tenant(session)
    _real_cafeteria(session, tid)
    case = Case(session, tid, "t-pkg-issue", _facts(catering="lunch", dietary="all veg"))
    case.confirm()
    body = "Sorry, we are short of staff that day and can't serve lunch"
    result = ProcessingPipeline(session, tid).process_event(_event(session, tid, case.outcome, body, sender=CAFE).event_id)
    assert result["action"] == "PACKAGE_ISSUE"
    assert any("[AT RISK]" in (m.subject or "") for m in case.mails(ADMIN))


def test_admin_reject_is_not_read_as_a_package_issue(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-pkg-cmd", _facts(catering="high tea", attendees=10))
    case.confirm()
    ProcessingPipeline(session, tid).process_event(
        _event(session, tid, case.outcome, "reject, we can't fund snacks this month", sender=ADMIN).event_id
    )
    session.refresh(case.outcome)
    assert case.facts.get("cost_rejected") is True
    assert all(p.get("status") != "ISSUE" for p in case.facts.get("task_packages") or [])


# ---------- one reminder, then one escalation
def test_pending_approval_gets_one_reminder_then_one_escalation(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-follow", _facts(catering="high tea", attendees=10))
    case.confirm()
    orch = case.orchestrator()
    start = utcnow()
    assert orch.run_followups(case.outcome, now=start + timedelta(hours=1)) == {"reminders": 0, "escalations": 0}
    assert orch.run_followups(case.outcome, now=start + timedelta(hours=9))["reminders"] == 1
    assert orch.run_followups(case.outcome, now=start + timedelta(hours=12)) == {"reminders": 0, "escalations": 0}
    assert orch.run_followups(case.outcome, now=start + timedelta(hours=25))["escalations"] == 1
    assert orch.run_followups(case.outcome, now=start + timedelta(hours=30)) == {"reminders": 0, "escalations": 0}
    session.commit()
    assert sum("[AT RISK]" in (m.subject or "") for m in case.mails(ADMIN)) == 1


# ---------- after the meeting: COMPLETED, service entry, invoice
def _completed_lunch_case(session: Session, tid: str, thread: str) -> Case:
    case = Case(session, tid, thread, _facts(catering="lunch", dietary="all veg"))
    case.confirm()
    orch = case.orchestrator()
    assert orch.request_completion(case.outcome, now=utcnow() + timedelta(days=400))
    session.commit()
    assert any("[COMPLETED]" in s for s in case.subjects(REQ))
    case.say("Fully delivered, all good - satisfied")
    assert case.facts["operational_status"] == "CLOSED"
    assert case.facts["financial_status"] == "SERVICE_ENTRY_PENDING"
    return case


def test_service_entry_then_matching_invoice_closes_financially(session: Session, env):
    _set(env, CATERING_AUTO_APPROVE_LIMIT=100000)
    tid = _tenant(session)
    case = _completed_lunch_case(session, tid, "t-entry-ok")
    case.say("confirmed")
    assert case.facts["financial_status"] == "FINANCIAL_CLOSURE_PENDING"
    total = case.facts["service_entry_total"]
    match = case.orchestrator().match_event_invoice(case.outcome, invoice_number="FS-1001", amount=total, actor="test")
    session.commit()
    session.refresh(case.outcome)
    assert match["status"] == "MATCHED" and case.facts["financial_status"] == "CLOSED"


def test_service_entry_variance_and_invoice_mismatch_are_billing_exceptions(session: Session, env):
    _set(env, CATERING_AUTO_APPROVE_LIMIT=100000)
    tid = _tenant(session)
    case = _completed_lunch_case(session, tid, "t-entry-var")
    case.say("only lunch 4 were served")
    assert case.facts["financial_status"] == "BILLING_EXCEPTION"
    assert any("[BILLING EXCEPTION]" in (m.subject or "") for m in case.mails(ADMIN))
    entry = case.facts["service_entries"][0]
    assert entry["actual_qty"] == 4 and entry["status"] == "VARIANCE"
    match = case.orchestrator().match_event_invoice(case.outcome, invoice_number="FS-2", amount=99999, actor="test")
    assert match["status"] == "MISMATCH"


def test_invoice_mail_quoting_the_case_is_matched(session: Session, env):
    _set(env, CATERING_AUTO_APPROVE_LIMIT=100000)
    tid = _tenant(session)
    case = _completed_lunch_case(session, tid, "t-invoice-mail")
    case.say("confirmed")
    total = case.facts["service_entry_total"]
    conv = Conversation(tenant_id=tid, thread_id="t-inv-vendor", requester_email="billing@vendor.com",
                        subject=f"Invoice for {case.outcome.case_reference}")
    session.add(conv)
    session.commit()
    ScenarioOrchestrator(session, tid).orchestrate(
        extraction=ExtractionResult(
            event_type="INVOICE",
            summary=f"Invoice INV-77 for {case.outcome.case_reference}",
            entities={"invoice_number": "INV-77", "amount": total},
            missing_information=[],
            confidence=0.9,
            reason="test",
        ),
        requester_email="billing@vendor.com",
        conversation_id=conv.conversation_id,
        business_event_id="evt_inv_77",
        context={},
    )
    session.refresh(case.outcome)
    assert case.facts["financial_status"] == "CLOSED"


# ---------- training: TRG reference, per-type buffers, every day booked, trainer travel
def test_two_day_training_books_both_days_and_plans_travel(session: Session, env):
    tid = _tenant(session)
    raw = (
        "We are running a two-day sales training on 20-21 October for 18 participants, classroom layout. "
        "One external trainer from Mumbai needs a hotel and an airport pickup."
    )
    case = Case(session, tid, "t-trg", _facts(attendees=18, date="20 october", preferred_time="9:30 am",
                                              end_time="5:30 pm", duration_hours=8, meeting_type="sales training",
                                              raw_reply=raw))
    assert case.outcome.case_reference.startswith("TRG-")
    assert case.facts["event_dates"][0].endswith("-10-20") and len(case.facts["event_dates"]) == 2
    assert str(case.facts.get("setup_buffer_minutes")) == "60"
    assert case.facts["proposed_room"]["name"] == "Learning Studio A"
    case.confirm()

    rows = session.exec(
        select(RoomBooking).where(RoomBooking.outcome_id == case.outcome.outcome_id, RoomBooking.status == "CONFIRMED")
    ).all()
    assert len(rows) == 2 and {r.starts_at.date().day for r in rows} == {20, 21}
    plan = case.facts["cost_plan"]
    assert "Hotel (empanelled)" in plan["chargeable"] and "Airport / station transfer" in plan["chargeable"]
    assert "Meeting room" in plan["included"]
    approval = session.exec(select(Approval).where(Approval.outcome_id == case.outcome.outcome_id)).first()
    assert approval.approval_type == "EVENT_COST"
    items = build_package_items(case.facts)
    assert items["TRAVEL"] and any("classroom" in i for i in items["ADMIN"])
    assert any("Trainer laptop" in i for i in items["IT"])


def test_training_room_is_kept_for_training(session: Session, env):
    tid = _tenant(session)
    case = Case(session, tid, "t-not-trg", _facts(attendees=25, meeting_type="internal meeting"))
    assert case.facts["proposed_room"]["name"] != "Learning Studio A"


# ---------- provisional hold while non-blocking questions are open
def test_room_is_held_while_details_are_pending_and_lapses_quietly(session: Session, env):
    from app.services.hold_sweeper import sweep_proposal_holds

    tid = _tenant(session)
    case = Case(session, tid, "t-prov", _facts(catering="lunch", dietary=None))
    assert case.facts["checklist_missing"] == ["dietary"]
    hold = case.facts["provisional_hold"]
    row = session.get(RoomBooking, hold["booking_id"])
    assert row.status == "HELD" and row.room_name == hold["room"]
    assert "Cost approval will cover only" in case.facts["cost_preview"]

    before = len(case.mails(REQ))
    sweep_proposal_holds(session, tid, now=utcnow() + timedelta(days=3), comms=CommunicationService(session, tid))
    session.refresh(row)
    session.refresh(case.outcome)
    assert row.status == "EXPIRED" and "provisional_hold" not in case.facts
    assert len(case.mails(REQ)) == before


def test_day_of_month_is_not_taken_as_a_start_time():
    from app.engine.meeting_scenario import _plausible_clock

    for bad in ("7", 7, "", None, "7th"):
        assert not _plausible_clock(bad)
    for good in ("10 AM", "2pm", "14:00", "10-12", "10 to 1 pm", "afternoon", "1400"):
        assert _plausible_clock(good)


# ---------- setup: catalogue + cost centres
def test_setup_site_services_and_cost_centres(client, auth_headers):
    rows = client.get("/api/v1/setup/site-services", headers=auth_headers).json()
    assert any(r["code"] == "high_tea" and r["delivery_model"] == "CHARGEABLE" for r in rows)
    resp = client.put("/api/v1/setup/site-services", headers=auth_headers,
                      json={"code": "high_tea", "delivery_model": "INCLUDED"})
    assert resp.status_code == 200 and resp.json()["delivery_model"] == "INCLUDED"
    assert client.put("/api/v1/setup/site-services", headers=auth_headers,
                      json={"code": "high_tea", "delivery_model": "FREE"}).status_code == 422

    ccs = client.get("/api/v1/setup/cost-centres", headers=auth_headers).json()
    assert any(c["code"] == "SL-1101" and c["needs_setup"] for c in ccs)
    ok = client.put("/api/v1/setup/cost-centres", headers=auth_headers,
                    json={"code": "SL-1101", "approver_email": "sales.head@example.com"})
    assert ok.status_code == 200
    ccs = client.get("/api/v1/setup/cost-centres", headers=auth_headers).json()
    assert next(c for c in ccs if c["code"] == "SL-1101")["approver_email"] == "sales.head@example.com"
    assert "delivery_model" in client.get("/api/v1/setup/templates/site_services", headers=auth_headers).text


# ---------- signed approve / reject links
def test_signed_link_approves_once(client, session: Session, env):
    _set(env, PUBLIC_BASE_URL="https://ops.example.com")
    tid = _tenant(session)
    case = Case(session, tid, "t-link", _facts(catering="high tea", attendees=10))
    case.confirm()
    mail = next(m for m in case.mails("mgr@example.com") if "[APPROVAL REQUIRED]" in (m.subject or ""))
    link = re.search(r"Approve: (\S+)", mail.body).group(1)
    parsed = urlparse(link)
    assert parsed.netloc == "ops.example.com"
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert verify(parsed.path.split("/")[-2], "approve", int(q["exp"]), q["sig"])

    path = parsed.path + "?" + parsed.query
    assert client.get(path).status_code == 200
    bad = path.replace(q["sig"], "0" * len(q["sig"]))
    assert client.post(bad).status_code == 403
    resp = client.post(path)
    assert resp.status_code == 200 and "Approved" in resp.text
    assert "Already approved" in client.post(path).text

    session.expire_all()
    outcome = session.get(Outcome, case.outcome.outcome_id)
    assert outcome.facts.get("cost_approved") is True and outcome.facts.get("catering_assigned") is True


def test_reject_link_cannot_be_reused_for_approve(session: Session, env):
    _set(env, PUBLIC_BASE_URL="https://ops.example.com")
    link = approval_link("apr_x", "reject")
    q = {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}
    assert verify("apr_x", "reject", int(q["exp"]), q["sig"])
    assert not verify("apr_x", "approve", int(q["exp"]), q["sig"])
