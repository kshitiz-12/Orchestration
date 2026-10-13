"""Ops ledger + resolution agent: writers, admin Q&A, duplicate link, Gemini-off fallback."""

import uuid

import pytest
from sqlmodel import Session, select

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.core.config import get_settings
from app.engine.pipeline import ProcessingPipeline
from app.models.intake import RawEmailEvent
from app.models.ops_ledger import OpsLedgerEvent
from app.models.org import Tenant, Vendor
from app.models.outcome import Communication, Outcome
from app.services.ops_ledger import record, spend_summary

ADMIN = "ops-desk@example.com"
REQ = "arjun.singh@acme.demo"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    monkeypatch.setenv("GEMINI_API_KEY", "")
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


def _ledger_types(session, tid):
    rows = session.exec(
        select(OpsLedgerEvent).where(OpsLedgerEvent.tenant_id == tid).order_by(OpsLedgerEvent.occurred_at)
    ).all()
    return [r.event_type for r in rows]


def test_ac_case_writes_ledger_and_plan_without_gemini(session: Session, env):
    tid = _tid(session)
    ev = _mail(session, tid, "AC not working in 4th floor bay near pantry, very hot", subject="AC issue")
    result = _run(session, tid, ev)
    assert result["status"] == "agent_handled"
    case = session.exec(select(Outcome)).one()
    assert case.facts.get("agent_category") == "hvac"
    assert case.facts.get("resolution_plan")
    types = _ledger_types(session, tid)
    assert "CASE_OPENED" in types
    assert "PLAN_PROPOSED" in types
    assert "WORK_ORDER_SENT" in types


class FakeGemini:
    def __init__(self, *decisions: dict):
        self.decisions = list(decisions)

    def generate_json(self, *, system_instruction: str, payload: dict, temperature: float = 0.2):
        return self.decisions.pop(0), {"label": "fake", "model": "fake"}

    def extract(self, **kwargs):
        return HeuristicProvider().extract(**kwargs)


def test_team_done_with_amount_records_spend(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(
        {
            "intents": [
                {
                    "type": "new_request",
                    "category": "hvac",
                    "summary": "AC not cooling in bay 4",
                    "details": {"location": "4th floor bay", "issue": "AC not cooling"},
                }
            ],
            "reply_to_requester": "Logged as [[REF1]].",
            "confidence": 0.9,
        }
    )
    ev = _mail(session, tid, "AC not cooling in 4th floor bay", subject="AC")
    _run(session, tid, ev, fake)
    case = session.exec(select(Outcome)).one()
    order = [m for m in _mails_to(session, ADMIN) if "WORK ORDER" in (m.subject or "")][-1]
    done = _mail(
        session,
        tid,
        "done, compressor replaced, INR 12500",
        sender=f"Ops <{ADMIN}>",
        subject=f"Re: {order.subject}",
    )
    result = _run(session, tid, done)
    assert result.get("applied") is True
    session.refresh(case)
    assert case.facts.get("agent_stage") == "RESOLVED"
    types = _ledger_types(session, tid)
    assert "TEAM_DONE" in types
    assert "SPEND_RECORDED" in types
    spend = spend_summary(session, tid, days=7)
    assert spend["total"] >= 12500


def test_admin_spend_question_answers_from_ledger(session: Session, env):
    tid = _tid(session)
    record(
        session,
        tid,
        event_type="SPEND_RECORDED",
        summary="HVAC parts for FAC-2026-0001",
        department_code="FACILITIES",
        category="hvac",
        case_reference="FAC-2026-0001",
        amount=4200.0,
        actor_email=ADMIN,
        actor_role="team",
    )
    session.commit()
    ev = _mail(
        session,
        tid,
        "How much did FACILITIES spend in the last 30 days?",
        sender=ADMIN,
        subject="Spend question",
    )
    result = _run(session, tid, ev)
    assert result["status"] == "ops_analytics"
    assert session.exec(select(Outcome)).all() == []
    reply = _mails_to(session, ADMIN)[-1]
    assert "4200" in reply.body.replace(",", "") or "4,200" in reply.body


def test_duplicate_open_ac_links_instead_of_second_dispatch(session: Session, env):
    tid = _tid(session)
    session.add(
        Vendor(
            tenant_id=tid,
            name="CoolAir HVAC",
            category="hvac",
            contact_email="coolair@vendor.example",
            status="ACTIVE",
            approved_services=["hvac", "ac repair"],
        )
    )
    session.commit()
    first_fake = FakeGemini(
        {
            "intents": [
                {
                    "type": "new_request",
                    "category": "hvac",
                    "summary": "AC not working in 4th floor bay near pantry",
                    "details": {"location": "4th floor bay near pantry", "issue": "AC not working"},
                }
            ],
            "reply_to_requester": "Logged [[REF1]].",
            "confidence": 0.9,
        }
    )
    first = _mail(session, tid, "AC not working in 4th floor bay near pantry", subject="AC bay")
    _run(session, tid, first, first_fake)
    open_case = session.exec(select(Outcome)).one()
    assert open_case.facts.get("agent_stage") == "DISPATCHED"

    # Different requester + forced new_request so desk opens a second case that the agent can link.
    second_fake = FakeGemini(
        {
            "intents": [
                {
                    "type": "new_request",
                    "category": "hvac",
                    "summary": "AC not working in 4th floor bay near pantry",
                    "details": {"location": "4th floor bay near pantry", "issue": "AC not working"},
                }
            ],
            "reply_to_requester": "I'll look into this.",
            "confidence": 0.9,
        }
    )
    second = _mail(
        session,
        tid,
        "AC not working in 4th floor bay near pantry, very hot",
        sender="priya.sharma@acme.demo",
        subject="AC bay again",
        thread=f"<{uuid.uuid4().hex}@mail>",
    )
    result = _run(session, tid, second, second_fake)
    assert result["status"] == "agent_handled"
    cases = session.exec(select(Outcome).order_by(Outcome.created_at)).all()
    assert len(cases) == 2
    linked = next(c for c in cases if c.outcome_id != open_case.outcome_id)
    assert linked.facts.get("agent_stage") == "LINKED"
    assert linked.facts.get("linked_case_ref") == open_case.case_reference
    reply = _mails_to(session, "priya.sharma@acme.demo")[-1]
    assert open_case.case_reference in reply.body


def test_resolution_heuristic_fallback_when_gemini_off(session: Session, env):
    from app.agent.resolution_agent import ResolutionPlan, investigate
    from app.models.outcome import Outcome as Out

    tid = _tid(session)
    outcome = Out(
        tenant_id=tid,
        case_reference="FAC-2099-0999",
        template_code="SERVICE_REQUEST",
        category="HVAC",
        title="AC failure",
        summary="AC failure",
        requester_email=REQ,
        status="ACTIVE",
        priority="MEDIUM",
        facts={"agent_case": True, "agent_category": "hvac", "details": {}, "raw_request": "urgent AC for client meeting tomorrow"},
    )
    session.add(outcome)
    session.flush()
    plan = investigate(session, tid, outcome=outcome, text="urgent AC for client meeting tomorrow")
    assert isinstance(plan, ResolutionPlan)
    assert plan.create_new is True
    assert plan.priority in {"HIGH", "URGENT", None} or plan.priority == "URGENT"
    assert "dispatch_work_order" in plan.recommended_actions
