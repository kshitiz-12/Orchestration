"""AI admin desk: any request type, multi-request mails, sensitive approvals, team replies, trail."""

import uuid

import pytest
from sqlmodel import Session, select

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.core.config import get_settings
from app.engine.pipeline import ProcessingPipeline
from app.models.company import Department, ServiceTicket, VisitorPass
from app.models.intake import RawEmailEvent
from app.models.org import Tenant
from app.models.outcome import Approval, Communication, Outcome

ADMIN = "ops-desk@example.com"
REQ = "arjun.singh@acme.demo"


class FakeGemini:
    """Stands in for Gemini: returns scripted decisions and records what it was shown."""

    def __init__(self, *decisions: dict):
        self.decisions = list(decisions)
        self.payloads: list[dict] = []

    def generate_json(self, *, system_instruction: str, payload: dict, temperature: float = 0.2):
        self.payloads.append(payload)
        return self.decisions.pop(0), {"label": "fake", "model": "fake"}

    def extract(self, **kwargs):  # legacy flows fall back to heuristics in these tests
        return HeuristicProvider().extract(**kwargs)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _tid(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def _mail(session, tid, body, *, sender=REQ, subject="Request", thread=None) -> RawEmailEvent:
    mid = f"<{uuid.uuid4().hex}@mail>"
    ev = RawEmailEvent(
        tenant_id=tid,
        idempotency_key=mid,
        provider="CLOUDMAILIN",
        provider_message_id=mid,
        provider_conversation_id=thread or mid,
        gmail_message_id=mid,
        gmail_thread_id=thread or mid,
        source="CLOUDMAILIN",
        sender=sender,
        subject=subject,
        body_text=body,
        body_for_ai=body,
        headers={},
    )
    session.add(ev)
    session.commit()
    return ev


def _run(session, tid, ev, provider=None):
    llm = LLMService(provider or HeuristicProvider())
    return ProcessingPipeline(session, tid, llm=llm).process_event(ev.event_id)


def _mails_to(session, addr):
    return [m for m in session.exec(select(Communication)).all() if addr in (m.recipients or [])]


def test_hi_gets_a_helpful_reply_and_no_case(session: Session, env):
    tid = _tid(session)
    ev = _mail(session, tid, "Hi\n\n[Hero-Logo.jpg]\n\nKapil Mantri\nSr. Associate", sender="kapil.mantri@herofincorp.com", subject="hi")
    result = _run(session, tid, ev)
    assert result["status"] == "agent_handled"
    assert session.exec(select(Outcome)).all() == []
    reply = _mails_to(session, "kapil.mantri@herofincorp.com")[-1]
    assert "How can I help" in reply.body and "meeting rooms" in reply.body


def test_empty_mail_asks_to_resend(session: Session, env):
    tid = _tid(session)
    ev = _mail(session, tid, "<Logo.jpg>\n\nKapil Mantri\nSr. Associate", sender="kapil.mantri@herofincorp.com", subject="RE: request")
    _run(session, tid, ev)
    assert "come through empty" in _mails_to(session, "kapil.mantri@herofincorp.com")[-1].body
    assert session.exec(select(Outcome)).all() == []


def test_rules_fallback_logs_a_repair_without_gemini(session: Session, env):
    tid = _tid(session)
    ev = _mail(session, tid, "AC not working in 4th floor bay near pantry, very hot", subject="AC issue")
    result = _run(session, tid, ev)
    assert result["status"] == "agent_handled"
    ticket = session.exec(select(ServiceTicket)).one()
    assert ticket.category == "hvac" and ticket.department_code == "FACILITIES" and ticket.status == "ASSIGNED"
    reply = _mails_to(session, REQ)[-1]
    assert ticket.reference in reply.body and ticket.reference in reply.subject
    work_order = _mails_to(session, ADMIN)[-1]
    assert "No Facilities & Maintenance contact set yet" in work_order.body


def test_one_mail_two_requests_become_two_cases(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(
        {
            "intents": [
                {"type": "new_request", "category": "maintenance", "summary": "Leaking tap in 3rd floor washroom",
                 "details": {"location": "3rd floor washroom", "issue": "tap leaking"}},
                {"type": "new_request", "category": "visitor", "summary": "Visitors on Friday",
                 "details": {"visitors": [{"name": "Rahul Sharma", "company": "Infosys"}, {"name": "Aman Verma", "company": "TCS"}],
                             "visit_date": "Friday 9 Oct", "visit_time": "11 AM"}},
            ],
            "reply_to_requester": "Hi Arjun,\n\nI've logged the leaking tap as [[REF1]] and registered your visitors under [[REF2]].\n\nWorkplace Team",
            "confidence": 0.9,
        }
    )
    ev = _mail(session, tid, "tap leaking in 3rd floor washroom. also 2 visitors friday 11am Rahul Sharma (Infosys), Aman Verma (TCS)")
    result = _run(session, tid, ev, fake)
    assert result["status"] == "agent_handled"
    cases = session.exec(select(Outcome).order_by(Outcome.created_at)).all()
    assert {c.facts["agent_category"] for c in cases} == {"maintenance", "visitor"}
    passes = session.exec(select(VisitorPass)).all()
    assert sorted(p.visitor_name for p in passes) == ["Aman Verma", "Rahul Sharma"]
    reply = _mails_to(session, REQ)[-1]
    assert all(c.case_reference in reply.body for c in cases) and "[[REF" not in reply.body
    trail = fake.payloads[0]
    assert trail["requester"]["name"] == "Arjun Singh" and trail["OFFICE_KNOWLEDGE"]


def test_sensitive_request_waits_for_admin_then_proceeds(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(
        {
            "intents": [{"type": "new_request", "category": "access_card", "summary": "Server room access for Arjun",
                         "details": {"area": "server room"}}],
            "reply_to_requester": "Hi Arjun,\n\nI've logged this as [[REF1]] and it's with the admin for approval.\n\nWorkplace Team",
            "confidence": 0.9,
        }
    )
    ev = _mail(session, tid, "Need access to the server room from Monday")
    _run(session, tid, ev, fake)
    case = session.exec(select(Outcome)).one()
    assert case.facts["agent_stage"] == "AWAITING_APPROVAL"
    assert session.exec(select(Approval).where(Approval.outcome_id == case.outcome_id)).one().decision == "PENDING"
    decision_mail = [m for m in _mails_to(session, ADMIN) if "OPS DECISION" in m.subject][-1]
    assert 'Reply "approve"' in decision_mail.body

    reply = _mail(session, tid, "approve", sender=f"Ops <{ADMIN}>", subject=f"Re: {decision_mail.subject}")
    result = _run(session, tid, reply)
    assert result["status"] == "admin_command" and result["action"] == "approve"
    session.refresh(case)
    assert case.facts["agent_stage"] == "DISPATCHED"
    assert "is approved" in _mails_to(session, REQ)[-1].body


def test_department_done_closes_loop_with_requester(session: Session, env):
    tid = _tid(session)
    dept = session.exec(select(Department).where(Department.code == "HOUSEKEEPING")).one()
    dept.primary_email = "housekeeping@acme-real.com"
    session.add(dept)
    session.commit()
    ev = _mail(session, tid, "Washroom on 2nd floor needs cleaning urgently", subject="cleaning")
    _run(session, tid, ev)
    case = session.exec(select(Outcome)).one()
    order = _mails_to(session, "housekeeping@acme-real.com")[-1]
    assert "WORK ORDER" in order.subject and "No Housekeeping contact" not in order.body

    done = _mail(session, tid, "done, cleaned and restocked", sender="housekeeping@acme-real.com", subject=f"Re: {order.subject}")
    result = _run(session, tid, done)
    assert result["action"] == "done"
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED"
    assert "taken care of" in _mails_to(session, REQ)[-1].body
    assert any("Completed by" in m.body for m in _mails_to(session, ADMIN))


def test_status_question_answers_from_case_state(session: Session, env):
    tid = _tid(session)
    first = _mail(session, tid, "Printer on 1st floor not working", subject="printer", thread="t-status")
    _run(session, tid, first)
    case = session.exec(select(Outcome)).one()
    fake = FakeGemini(
        {
            "intents": [{"type": "status", "case_reference": case.case_reference}],
            "reply_to_requester": f"Hi Arjun,\n\n{case.case_reference} is with IT Support.\n\nWorkplace Team",
            "confidence": 0.9,
        }
    )
    follow = _mail(session, tid, "any update?", subject="Re: printer", thread="t-status")
    _run(session, tid, follow, fake)
    assert fake.payloads[0]["this_thread_case"] == case.case_reference
    assert any(t["from"] == "admin_desk" for t in fake.payloads[0]["trail_oldest_first"])
    assert len(session.exec(select(Outcome)).all()) == 1


def test_meeting_room_request_goes_to_room_flow(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(
        {"intents": [{"type": "new_request", "category": "meeting_room", "summary": "Room for 8"}],
         "reply_to_requester": "ignored", "confidence": 0.9}
    )
    ev = _mail(session, tid, "Need a meeting room for 8 people tomorrow 3-5pm at Corporate Office, internal review")
    result = _run(session, tid, ev, fake)
    assert result["status"] != "agent_handled"
    case = session.exec(select(Outcome)).one()
    assert case.category == "MEETING_ROOM" and case.template_code != "SERVICE_REQUEST"
