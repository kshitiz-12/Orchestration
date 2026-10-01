"""Office-admin lifecycle for every request type: priority, routing, team verbs, reopen, SLA sweeps."""

from datetime import timedelta

from sqlmodel import Session, select

from app.agent.directory import department_for
from app.agent.lifecycle import sweep_desk_cases
from app.agent.playbooks import assess_risk, label_for
from app.agent.priority import infer_priority, sla_hours_for
from app.models.company import ServiceTicket
from app.models.org import utcnow
from app.models.outcome import Approval, Outcome
from app.services.approval_actions import apply_decision
from test_admin_desk import ADMIN, REQ, FakeGemini, _mail, _mails_to, _run, _tid, env  # noqa: F401
from test_admin_desk_scenarios import _decision, _set_dept_email


def _one_case(session: Session) -> Outcome:
    return session.exec(select(Outcome)).one()


def test_priority_rules_raise_for_safety_and_lower_for_no_rush():
    assert infer_priority("There is smoke coming from the server room", None).priority == "URGENT"
    assert infer_priority("Lift stuck between floors with people inside", "LOW").priority == "URGENT"
    assert infer_priority("Internet down for the whole floor", None).priority == "HIGH"
    assert infer_priority("Need a stapler, no rush", None).priority == "LOW"
    assert infer_priority("hello, can you look at the team calendar", "HIGH").priority == "HIGH"
    assert infer_priority("Need a stapler", None).priority == "MEDIUM"


def test_sla_is_the_tighter_of_department_and_priority():
    assert sla_hours_for("URGENT", 24) == 4
    assert sla_hours_for("MEDIUM", 24) == 24
    assert sla_hours_for("HIGH", 4) == 4
    assert sla_hours_for("LOW", 24) >= 24


def test_new_request_types_route_to_their_owning_team(session: Session):
    from app.models.company import Department

    tid = _tid(session)
    # Older tenants were seeded before these types existed: the playbook still knows the owner.
    for dept in session.exec(select(Department)).all():
        dept.categories = [c for c in (dept.categories or []) if c not in {"pest_control", "material_gate_pass", "employee_transport"}]
        session.add(dept)
    session.commit()

    def code(category: str) -> str:
        dept = department_for(session, tid, category)
        return getattr(dept, "code", dept)

    assert code("pest_control") == "FACILITIES"
    assert code("material_gate_pass") == "SECURITY"
    assert code("employee_transport") == "TRAVEL"
    assert code("something_brand_new") == "ADMIN"
    assert label_for("material_gate_pass") != "material_gate_pass"


def test_non_returnable_gate_pass_needs_sign_off():
    def verdict(details):
        return assess_risk(category="material_gate_pass", text="gate pass", details=details, agent_flag=False)

    assert verdict({"items": "old monitors", "returnable": "no"}).needs_admin
    assert not verdict({"items": "projector", "returnable": "yes"}).needs_admin


def test_urgent_safety_issue_is_dispatched_at_once_and_admin_alerted(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "FACILITIES", "facilities@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "electrical", "summary": "Sparking socket",
         "details": {"issue": "socket sparking and smoke"}},
    ))
    _run(session, tid, _mail(session, tid, "socket near my desk is sparking, there is smoke!", subject="urgent"), fake)
    case = _one_case(session)
    assert case.priority == "URGENT"
    assert case.facts["agent_stage"] == "DISPATCHED", "safety work must not wait for missing details"
    assert _mails_to(session, "facilities@acme-real.com")
    assert any("URGENT" in m.subject for m in _mails_to(session, ADMIN))
    ticket = session.exec(select(ServiceTicket)).one()
    assert ticket.sla_due_at is not None and ticket.sla_due_at - utcnow() <= timedelta(hours=4, minutes=5)


def _dispatched_repair(session: Session, tid: str) -> tuple[Outcome, str]:
    _set_dept_email(session, "FACILITIES", "facilities@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "maintenance", "summary": "Chair broken",
         "details": {"location": "cabin 4", "issue": "chair wheel broken"}},
    ))
    _run(session, tid, _mail(session, tid, "chair wheel broken in cabin 4", subject="chair", thread="t-ch"), fake)
    order = _mails_to(session, "facilities@acme-real.com")[-1]
    case = session.exec(select(Outcome).where(Outcome.title == "Chair broken")).one()
    return case, order.subject


def _team_says(session, tid, text, subject):
    return _run(session, tid, _mail(session, tid, text, sender="facilities@acme-real.com", subject=f"Re: {subject}"))


def test_team_verbs_move_the_case_without_false_completion(session: Session, env):
    tid = _tid(session)
    case, subject = _dispatched_repair(session, tid)

    _team_says(session, tid, "on it, technician coming in 30 mins", subject)
    session.refresh(case)
    assert case.facts["agent_stage"] == "IN_PROGRESS"

    _team_says(session, tid, "will be done tomorrow", subject)
    session.refresh(case)
    assert case.facts["agent_stage"] != "RESOLVED"

    _team_says(session, tid, "issue: spare wheel not in stock, need vendor", subject)
    session.refresh(case)
    assert case.facts["agent_stage"] == "BLOCKED" and case.status == "AT_RISK"
    assert any("reports a problem" in m.body for m in _mails_to(session, ADMIN))

    _team_says(session, tid, "done, wheel replaced", subject)
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED"
    assert "not fixed" in _mails_to(session, REQ)[-1].body.lower()


def test_requester_not_fixed_reopens_and_thanks_closes(session: Session, env):
    tid = _tid(session)
    case, subject = _dispatched_repair(session, tid)
    _team_says(session, tid, "done", subject)
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED"

    reopen = FakeGemini(_decision(
        {"type": "update_case", "case_reference": case.case_reference, "category": "maintenance", "details": {}},
    ))
    _run(session, tid, _mail(session, tid, "still not working, the wheel came off again", subject="Re: chair", thread="t-ch"), reopen)
    session.refresh(case)
    assert case.facts["agent_stage"] == "DISPATCHED" and case.facts["reopen_count"] == 1
    assert len(_mails_to(session, "facilities@acme-real.com")) >= 2, "team gets a fresh work order"

    _team_says(session, tid, "done, fixed properly now", subject)
    thanks = FakeGemini(_decision(
        {"type": "update_case", "case_reference": case.case_reference, "category": "maintenance", "details": {}},
    ))
    _run(session, tid, _mail(session, tid, "thanks, all good now", subject="Re: chair", thread="t-ch"), thanks)
    session.refresh(case)
    assert case.status == "CLOSED"


def test_dashboard_approval_dispatches_a_desk_case(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "access_card", "summary": "Server room access",
         "details": {"area": "server room"}},
    ))
    _run(session, tid, _mail(session, tid, "Need server room access"), fake)
    case = _one_case(session)
    assert case.facts["agent_stage"] == "AWAITING_APPROVAL"
    approval = session.exec(select(Approval).where(Approval.outcome_id == case.outcome_id)).one()
    apply_decision(session, tid, approval, approved=True, actor="admin@prototype.local", via="dashboard")
    session.commit()
    session.refresh(case)
    assert case.facts["agent_stage"] == "DISPATCHED"
    assert "approved" in _mails_to(session, REQ)[-1].body


def test_sweep_reminds_then_escalates_once(session: Session, env):
    tid = _tid(session)
    case, _ = _dispatched_repair(session, tid)
    start = utcnow()
    sent_before = len(_mails_to(session, "facilities@acme-real.com"))
    hours = (case.due_at - start).total_seconds() / 3600

    counts = sweep_desk_cases(session, tid, now=start + timedelta(hours=hours * 0.8))
    assert counts["reminded"] == 1
    assert len(_mails_to(session, "facilities@acme-real.com")) == sent_before + 1
    assert sweep_desk_cases(session, tid, now=start + timedelta(hours=hours * 0.9))["reminded"] == 0

    counts = sweep_desk_cases(session, tid, now=case.due_at + timedelta(hours=1))
    assert counts["escalated"] == 1
    session.refresh(case)
    assert case.status == "AT_RISK" and case.facts["sla_breached"] is True
    assert any("ESCALATION" in m.subject for m in _mails_to(session, ADMIN))
    assert sweep_desk_cases(session, tid, now=case.due_at + timedelta(hours=2))["escalated"] == 0


def test_sweep_nudges_requester_then_closes_politely(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "cab", "summary": "Cab to airport", "details": {"destination": "Airport"}},
    ))
    _run(session, tid, _mail(session, tid, "need a cab to airport"), fake)
    case = _one_case(session)
    assert case.facts["agent_stage"] == "AWAITING_INFO"
    now = utcnow()
    assert sweep_desk_cases(session, tid, now=now + timedelta(hours=25))["nudged"] == 1
    assert "Just checking in" in _mails_to(session, REQ)[-1].body
    assert sweep_desk_cases(session, tid, now=now + timedelta(hours=100))["closed_no_reply"] == 1
    session.refresh(case)
    assert case.facts["agent_stage"] == "CLOSED_NO_REPLY" and case.status == "CANCELLED"


def test_sweep_reminds_approver_and_auto_closes_resolved(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "access_card", "summary": "Server room access", "details": {"area": "server room"}},
    ))
    _run(session, tid, _mail(session, tid, "Need server room access"), fake)
    now = utcnow()
    assert sweep_desk_cases(session, tid, now=now + timedelta(hours=9))["approval_reminders"] == 1
    assert sweep_desk_cases(session, tid, now=now + timedelta(hours=10))["approval_reminders"] == 0

    repair, subject = _dispatched_repair(session, tid)
    _team_says(session, tid, "done", subject)
    assert sweep_desk_cases(session, tid, now=utcnow() + timedelta(hours=73))["auto_closed"] == 1
    session.refresh(repair)
    assert repair.status == "CLOSED"


def test_email_dropped_mid_processing_is_picked_up_again_once(session: Session, env):
    from app.models.intake import RawEmailEvent
    from app.services.hold_sweeper import recover_stuck_emails

    tid = _tid(session)
    ev = _mail(session, tid, "Hi", sender="stuck.user@acme.demo", subject="hi")
    ev.processing_stage = "AI_INTERPRETATION"
    ev.created_at = utcnow() - timedelta(minutes=10)
    session.add(ev)
    session.commit()
    fresh = _mail(session, tid, "Hi again", sender="fresh.user@acme.demo", subject="hi")
    fresh.processing_stage = "AI_INTERPRETATION"
    session.add(fresh)
    session.commit()

    assert recover_stuck_emails(session, tid) == [ev.event_id], "only mail stuck for a while is retried"
    assert session.get(RawEmailEvent, ev.event_id).processing_stage == "COMPLETED"
    assert len(_mails_to(session, "stuck.user@acme.demo")) == 1
    assert recover_stuck_emails(session, tid) == []
    assert len(_mails_to(session, "stuck.user@acme.demo")) == 1


def test_times_keep_their_minutes():
    from datetime import datetime

    from app.engine.event_services import fmt_local

    assert fmt_local(datetime(2026, 10, 2, 10, 6)) == "2 Oct, 10:06 AM"
    assert fmt_local(datetime(2026, 10, 12, 9, 30)) == "12 Oct, 9:30 AM"


def test_kpis_and_list_are_type_neutral(client, session: Session, env, auth_headers):
    tid = _tid(session)
    _dispatched_repair(session, tid)
    res = client.get("/api/v1/outcomes", headers=auth_headers)
    assert res.status_code == 200
    rows = res.json()
    assert rows and rows[0]["type_label"] and rows[0]["department"]
