"""Blueprint controls: evidence-based closure, no-guess answers, human approval classes, learning, emergency stop."""

from datetime import timedelta

from sqlmodel import Session, select

from app.agent.learning import automation_kpis, similar_verified
from app.agent.lifecycle import sweep_desk_cases
from app.agent.playbooks import decision_class
from app.models.company import LearningRecord
from app.models.org import utcnow
from app.models.outcome import Approval, Evidence, Outcome
from app.services.approval_actions import apply_decision
from test_admin_desk import ADMIN, REQ, FakeGemini, _mail, _mails_to, _run, _tid, env  # noqa: F401
from test_admin_desk_scenarios import _decision, _set_dept_email

TEAM = "facilities@acme-real.com"


def _repair(session: Session, tid: str, thread: str = "t-rep") -> tuple[Outcome, str]:
    _set_dept_email(session, "FACILITIES", TEAM)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "furniture", "summary": "Chair wheel broken",
         "details": {"location": "cabin 4", "issue": "chair wheel broken"}},
    ))
    _run(session, tid, _mail(session, tid, "chair wheel broken in cabin 4", subject="chair", thread=thread), fake)
    case = session.exec(select(Outcome).where(Outcome.title == "Chair wheel broken")).one()
    return case, _mails_to(session, TEAM)[-1].subject


def _team(session, tid, text, subject):
    return _run(session, tid, _mail(session, tid, text, sender=TEAM, subject=f"Re: {subject}"))


def test_bare_done_asks_for_proof_and_proof_makes_closure_verified(session: Session, env):
    tid = _tid(session)
    case, subject = _repair(session, tid)
    assert "only marked verified" in _mails_to(session, TEAM)[-1].body

    _team(session, tid, "done", subject)
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED" and case.facts["evidence_status"] == "missing"
    assert any("Completion note needed" in m.subject or "PROOF NEEDED" in m.subject for m in _mails_to(session, TEAM))

    _team(session, tid, "replaced the broken wheel with a new castor", subject)
    session.refresh(case)
    assert case.facts["evidence_status"] == "provided"
    assert session.exec(select(Evidence).where(Evidence.outcome_id == case.outcome_id)).all()

    sweep_desk_cases(session, tid, now=utcnow() + timedelta(hours=73))
    session.refresh(case)
    assert case.status == "CLOSED" and case.facts["closure_type"] == "verified_evidence" and case.facts["verified"] is True
    record = session.exec(select(LearningRecord).where(LearningRecord.outcome_id == case.outcome_id)).one()
    assert record.learning_eligible and record.category == "furniture"


def test_no_evidence_closes_honestly_and_is_not_learned_from(session: Session, env):
    tid = _tid(session)
    case, subject = _repair(session, tid)
    _team(session, tid, "done", subject)
    sweep_desk_cases(session, tid, now=utcnow() + timedelta(hours=73))
    session.refresh(case)
    assert case.facts["closure_type"] == "closed_without_evidence" and case.facts["verified"] is False
    record = session.exec(select(LearningRecord).where(LearningRecord.outcome_id == case.outcome_id)).one()
    assert record.learning_eligible is False


def test_photo_attachment_counts_as_evidence(session: Session, env):
    from app.agent.desk import AdminDesk
    from app.services.approval_actions import default_comms

    tid = _tid(session)
    case, _ = _repair(session, tid)
    desk = AdminDesk(session, tid, default_comms(session, tid))
    assert desk.apply_team_reply(case, "done", TEAM, attachments=["after.jpg"])["evidence"] == "provided"


def test_requester_confirmation_is_a_verified_closure(session: Session, env):
    tid = _tid(session)
    case, subject = _repair(session, tid, thread="t-conf")
    _team(session, tid, "done", subject)
    thanks = FakeGemini(_decision({"type": "update_case", "case_reference": case.case_reference, "category": "furniture"}))
    _run(session, tid, _mail(session, tid, "thanks, all good now", subject="Re: chair", thread="t-conf"), thanks)
    session.refresh(case)
    assert case.facts["closure_type"] == "verified_by_requester"


def test_unverified_question_goes_to_a_person_instead_of_a_guess(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "question", "category": "general", "summary": "Paternity leave days", "answer_verified": False},
        reply="Hi Arjun,\n\nPaternity leave is 10 days.\n\nWorkplace Team",
    ))
    _run(session, tid, _mail(session, tid, "how many days of paternity leave do we get?", subject="leave"), fake)
    case = session.exec(select(Outcome)).one()
    assert case.facts["knowledge_gap"] is True
    reply = _mails_to(session, REQ)[-1].body
    assert "10 days" not in reply and "rather than guess" in reply and case.case_reference in reply
    order = [m for m in _mails_to(session, ADMIN) if "verified answer" in m.subject.lower() or "verified answer" in m.body.lower()][-1]

    _run(session, tid, _mail(session, tid, "tell requester: it is 15 working days, see HR policy 4.2",
                             sender=ADMIN, subject=f"Re: {order.subject}"))
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED"
    assert "15 working days" in _mails_to(session, REQ)[-1].body


def test_model_admitting_it_does_not_know_is_also_routed(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "question", "category": "general", "summary": "Gym timings"},
        reply="Hi Arjun,\n\nI'm not sure about the gym timings - let me check with the team.\n\nWorkplace Team",
    ))
    _run(session, tid, _mail(session, tid, "what are the gym timings?"), fake)
    assert session.exec(select(Outcome)).one().facts["knowledge_gap"] is True


def test_flight_booking_needs_approval_but_a_cab_to_the_airport_does_not(session: Session, env):
    tid = _tid(session)
    flight = FakeGemini(_decision(
        {"type": "new_request", "category": "travel", "summary": "Flight to Mumbai",
         "details": {"travel_date": "Friday 9 Oct", "from": "Delhi", "to": "Mumbai"}},
    ))
    _run(session, tid, _mail(session, tid, "please book a flight Delhi to Mumbai on Friday"), flight)
    cab = FakeGemini(_decision(
        {"type": "new_request", "category": "travel", "summary": "Cab to airport",
         "details": {"travel_date": "Friday 6 AM", "pickup": "Office", "destination": "IGI T3"}},
    ))
    _run(session, tid, _mail(session, tid, "need a cab from office to airport friday 6 am, I have a flight"), cab)
    cases = {c.title: c for c in session.exec(select(Outcome)).all()}
    assert cases["Flight to Mumbai"].facts["agent_stage"] == "AWAITING_APPROVAL"
    assert cases["Flight to Mumbai"].facts["decision_class"] == "C"
    assert cases["Cab to airport"].facts["agent_stage"] == "DISPATCHED"


def test_catering_without_a_cost_and_weekend_access_need_sign_off(session: Session, env):
    tid = _tid(session)
    food = FakeGemini(_decision(
        {"type": "new_request", "category": "catering", "summary": "Lunch for 20",
         "details": {"date": "Monday 1 PM", "headcount": 20}},
    ))
    _run(session, tid, _mail(session, tid, "lunch for 20 people on monday 1pm for the client team"), food)
    access = FakeGemini(_decision(
        {"type": "new_request", "category": "hvac", "summary": "AC vendor weekend work",
         "details": {"location": "3rd floor", "issue": "AC servicing"}},
    ))
    _run(session, tid, _mail(session, tid, "AC vendor needs weekend access to the 3rd floor for servicing"), access)
    cases = {c.title: c for c in session.exec(select(Outcome)).all()}
    assert "catering" in cases["Lunch for 20"].facts["decision_reason"]
    assert "after-hours" in cases["AC vendor weekend work"].facts["decision_reason"]


def test_decision_classes():
    assert decision_class("vendor", True) == "D"
    assert decision_class("access_card", True) == "C"
    assert decision_class("visitor", False) == "B"
    assert decision_class("maintenance", False) == "A"


def test_overdue_approval_puts_case_at_risk_until_decided(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "access_card", "summary": "Server room access", "details": {"area": "server room"}},
    ))
    _run(session, tid, _mail(session, tid, "Need server room access"), fake)
    case = session.exec(select(Outcome)).one()
    sweep_desk_cases(session, tid, now=utcnow() + timedelta(hours=9))
    session.refresh(case)
    assert case.status == "AT_RISK"
    approval = session.exec(select(Approval).where(Approval.outcome_id == case.outcome_id)).one()
    apply_decision(session, tid, approval, approved=True, actor=ADMIN, via="dashboard")
    session.commit()
    session.refresh(case)
    assert case.status == "ACTIVE" and case.facts["agent_stage"] == "DISPATCHED"


def test_emergency_stop_skips_ai_but_keeps_safety_path(session: Session, env):
    env.setenv("AI_EMERGENCY_STOP", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    tid = _tid(session)
    unused = FakeGemini(_decision({"type": "new_request", "category": "general", "summary": "should not be used"}))
    _run(session, tid, _mail(session, tid, "Fan not working in cabin 12", subject="fan"), unused)
    assert unused.payloads == [], "the model is not called during an emergency stop"
    fan = session.exec(select(Outcome)).one()
    assert fan.facts["agent_stage"] == "AWAITING_APPROVAL" and "paused" in fan.facts["decision_reason"]

    _run(session, tid, _mail(session, tid, "socket sparking near desk 4, smoke coming", subject="sparks"))
    spark = [c for c in session.exec(select(Outcome)).all() if c.outcome_id != fan.outcome_id][0]
    assert spark.priority == "URGENT" and spark.facts["agent_stage"] == "DISPATCHED"


def test_verified_cases_become_precedent_and_corrections_lower_automation(session: Session, env):
    tid = _tid(session)
    case, subject = _repair(session, tid, thread="t-l1")
    _run(session, tid, _mail(session, tid, "change location to cabin 5", sender=ADMIN, subject=f"Re: {subject}"))
    _team(session, tid, "done, replaced the wheel castor", subject)
    sweep_desk_cases(session, tid, now=utcnow() + timedelta(hours=73))
    session.refresh(case)
    assert case.facts["corrections"][0]["kind"] == "detail_changed"

    similar = similar_verified(session, tid, "chair wheel broken again in cabin 9")
    assert similar and similar[0]["category"] == "furniture"
    assert "detail_changed" in similar[0]["corrected_by_humans"]

    nxt = FakeGemini(_decision(
        {"type": "new_request", "category": "furniture", "summary": "Another chair",
         "details": {"location": "cabin 9", "issue": "chair wheel broken"}},
    ))
    _run(session, tid, _mail(session, tid, "chair wheel broken in cabin 9", subject="chair 2", thread="t-l2"), nxt)
    assert nxt.payloads[0]["SIMILAR_VERIFIED_CASES"]

    kpis = automation_kpis(session, tid)
    assert kpis["automation_rate_pct"] is not None and kpis["automation_rate_pct"] < 100


def test_dashboard_kpis_expose_automation(client, session: Session, env, auth_headers):
    res = client.get("/api/v1/dashboard/kpis", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "automation_rate_pct" in body and "ai_emergency_stop" in body
