"""Varied, messy mails across request types: the desk must understand intent, not match examples."""

from sqlmodel import Session, select

from app.agent.digest import send_admin_digest
from app.agent.tools import legacy_categories, tool_catalogue
from app.models.company import Department, ServiceTicket, VisitorPass
from app.models.outcome import Approval, Outcome
from test_admin_desk import ADMIN, REQ, FakeGemini, _mail, _mails_to, _run, _tid, env  # noqa: F401


def _decision(*intents: dict, reply: str = "", confidence: float = 0.9) -> dict:
    return {"intents": list(intents), "reply_to_requester": reply, "confidence": confidence}


def _set_dept_email(session: Session, code: str, email: str) -> None:
    dept = session.exec(select(Department).where(Department.code == code)).one()
    dept.primary_email = email
    session.add(dept)
    session.commit()


def test_hinglish_typos_become_a_facilities_ticket(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "ac", "summary": "AC not cooling on 4th floor",
         "details": {"location": "4th floor, near pantry", "issue": "AC not cooling"}},
        reply="Hi Arjun,\n\nNoted - logged as [[REF1]] and passed to Facilities.\n\nWorkplace Team",
    ))
    ev = _mail(session, tid, "bhai 4th flr pe AC kaam nhi kr rha, bahut garmi h plz dekh lo", subject="ac")
    _run(session, tid, ev, fake)
    ticket = session.exec(select(ServiceTicket)).one()
    assert ticket.category == "hvac" and ticket.department_code == "FACILITIES"
    reply = _mails_to(session, REQ)[-1]
    assert ticket.reference in reply.body and "[[REF" not in reply.body


def test_pasted_back_questions_answer_the_open_case(session: Session, env):
    tid = _tid(session)
    first = FakeGemini(_decision(
        {"type": "new_request", "category": "visitor", "summary": "Visitor tomorrow",
         "details": {"visitor_names": ["Neha Kapoor (Deloitte)"]}},
    ))
    _run(session, tid, _mail(session, tid, "a visitor coming, Neha Kapoor from Deloitte", subject="visitor", thread="t-vis"), first)
    case = session.exec(select(Outcome)).one()
    assert case.facts["agent_stage"] == "AWAITING_INFO"
    asked = _mails_to(session, REQ)[-1]
    assert "Which date and time is the visit?" in asked.body

    second = FakeGemini(_decision(
        {"type": "update_case", "case_reference": case.case_reference, "category": "visitor",
         "details": {"visit_date": "Thursday 8 Oct", "visit_time": "3 PM"}},
    ))
    pasted = (
        "Pls find the same\n\n"
        "- Which date and time is the visit?  Thursday 8 Oct, 3 PM\n\n"
        "On Tue, Workplace Team wrote:\n> Which date and time is the visit?"
    )
    _run(session, tid, _mail(session, tid, pasted, subject="Re: visitor", thread="t-vis"), second)
    turns = second.payloads[0]["trail_oldest_first"]
    assert any(t["from"] == "admin_desk" and "Which date" in t["text"] for t in turns)
    assert all(t["from"] != "requester" or "Which date" not in t["text"] for t in turns)
    session.refresh(case)
    assert case.facts["agent_stage"] == "COMPLETED"
    assert len(session.exec(select(Outcome)).all()) == 1
    assert session.exec(select(VisitorPass)).one().visit_date == "Thursday 8 Oct"


def test_status_question_without_gemini_uses_case_state(session: Session, env):
    tid = _tid(session)
    _run(session, tid, _mail(session, tid, "Printer on 2nd floor not working", subject="printer", thread="t-st"))
    case = session.exec(select(Outcome)).one()
    _run(session, tid, _mail(session, tid, "any update on this?", subject="Re: printer", thread="t-st"))
    assert len(session.exec(select(Outcome)).all()) == 1
    reply = _mails_to(session, REQ)[-1]
    assert case.case_reference in reply.body and "dispatched" in reply.body


def test_auto_replies_and_no_reply_senders_are_not_answered(session: Session, env):
    tid = _tid(session)
    ooo = _mail(session, tid, "I am out of office till Monday.", subject="Automatic reply: Your request")
    assert _run(session, tid, ooo)["status"] == "agent_ignored"
    bot = _mail(session, tid, "Your order has shipped", sender="no-reply@shop.example.com", subject="Order update")
    assert _run(session, tid, bot)["status"] == "agent_ignored"
    headers = _mail(session, tid, "Thanks for your mail", subject="Re: hi")
    headers.headers = {"Auto-Submitted": "auto-replied"}
    session.add(headers)
    session.commit()
    assert _run(session, tid, headers)["status"] == "agent_ignored"
    assert _mails_to(session, REQ) == [] and session.exec(select(Outcome)).all() == []


def test_supplies_within_limit_go_ahead_above_limit_need_approval(session: Session, env):
    tid = _tid(session)
    small = FakeGemini(_decision(
        {"type": "new_request", "category": "stationery", "summary": "Notebooks and pens",
         "details": {"items": "10 notebooks, 20 pens", "amount": 1800}},
    ))
    _run(session, tid, _mail(session, tid, "need 10 notebooks and 20 pens for the team, approx Rs 1800"), small)
    big = FakeGemini(_decision(
        {"type": "new_request", "category": "supplies", "summary": "Ergonomic chairs",
         "details": {"items": "6 ergonomic chairs", "amount": 54000}},
    ))
    _run(session, tid, _mail(session, tid, "please order 6 ergonomic chairs, quote is INR 54,000"), big)
    cases = {c.title: c for c in session.exec(select(Outcome)).all()}
    assert cases["Notebooks and pens"].facts["agent_stage"] == "DISPATCHED"
    chairs = cases["Ergonomic chairs"]
    assert chairs.facts["agent_stage"] == "AWAITING_APPROVAL"
    assert "54,000" in chairs.facts["decision_reason"]


def test_onboarding_fans_out_and_sends_day_one_note(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "IT", "it-helpdesk@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "new_joiner", "summary": "Onboarding - Sneha Iyer",
         "details": {"employee_name": "Sneha Iyer", "joining_date": "Monday 12 Oct", "location": "Corporate Office Gurugram"}},
    ))
    _run(session, tid, _mail(session, tid, "Sneha Iyer joins on 12 Oct in Gurugram, pls arrange everything", sender="hr.lead@acme.demo"), fake)
    case = session.exec(select(Outcome)).one()
    assert case.case_reference.startswith("ONB-")
    assert _mails_to(session, "it-helpdesk@acme-real.com"), "IT gets its own work order"
    admin_orders = [m for m in _mails_to(session, ADMIN) if "WORK ORDER" in m.subject]
    assert len(admin_orders) == 1, "teams without a mailbox are merged into one admin mail"
    reply = _mails_to(session, "hr.lead@acme.demo")[-1]
    assert "Day-1 note for Sneha Iyer" in reply.body and "Monday 12 Oct" in reply.body


_PRIYA = """Hi Admin team,

Please note that Priya Sharma has joined us today.

Details:
- Name: Priya Sharma
- Employee ID: EMP-2041
- Location: 3rd floor, Bengaluru office

Could you please arrange the following:
1. Laptop, company email ID and system access
2. A desk/workstation near the marketing team
3. ID and access card for the office and 3rd floor

Thanks,
HR Team"""


def _priya_case(session, tid, tasks):
    _set_dept_email(session, "HR", "hr.lead@acme-real.com")
    _set_dept_email(session, "IT", "it-helpdesk@acme-real.com")
    _set_dept_email(session, "FACILITIES", "facilities@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding for Priya Sharma", "tasks": tasks,
         "details": {"employee_name": "Priya Sharma", "joining_date": "2026-10-01", "location": "3rd floor, Bengaluru"}},
    ))
    _run(session, tid, _mail(session, tid, _PRIYA, subject="New Joining - Priya Sharma", sender="hr.lead@acme-real.com"), fake)
    return session.exec(select(Outcome)).one()


def test_each_team_gets_only_its_own_tasks_and_the_raising_team_gets_none(session: Session, env):
    tid = _tid(session)
    case = _priya_case(session, tid, [
        "Set up Windows laptop with marketing software", "Create company email ID",
        "Allocate desk near the Marketing team, 3rd floor", "Issue ID and access card for office and 3rd floor",
    ])
    it = _mails_to(session, "it-helpdesk@acme-real.com")[-1].body
    assert "YOUR TASKS:" in it and "1. Set up Windows laptop" in it and "2. Create company email ID" in it
    assert "desk" not in it.split("Requester:")[0].lower()
    fac = [m.body for m in _mails_to(session, "facilities@acme-real.com") if "WORK ORDER" in m.subject]
    assert len(fac) == 1 and "Allocate desk near the Marketing team" in fac[0]
    assert "access card" not in fac[0].split("Requester:")[0]
    assert "3. Issue ID and access card" in it, "access cards are an IT category here, so they join IT's list"
    assert not [m for m in _mails_to(session, "hr.lead@acme-real.com") if "WORK ORDER" in (m.subject or "")], \
        "HR raised it, so HR gets no work order"
    hr = next(g for g in case.facts["team_groups"] if g["label"] == "People / HR")
    assert hr["done"] and hr["raised_by_team"]

    it_order = _mails_to(session, "it-helpdesk@acme-real.com")[-1]
    _run(session, tid, _mail(session, tid, "on it, laptop being imaged", sender="it-helpdesk@acme-real.com",
                             subject=f"Re: {it_order.subject}"))
    assert "from IT Support: on it, laptop being imaged" in _mails_to(session, "hr.lead@acme-real.com")[-1].body
    assert any("IT Support update" in (m.body or "") for m in _mails_to(session, ADMIN))
    _run(session, tid, _mail(session, tid, "done, laptop and email handed over", sender="it-helpdesk@acme-real.com",
                             subject=f"Re: {it_order.subject}"))
    hr_update = _mails_to(session, "hr.lead@acme-real.com")[-1].body
    assert "IT Support has finished their part" in hr_update and "- Set up Windows laptop" in hr_update
    assert "Still in progress: Facilities & Maintenance" in hr_update
    assert any("IT Support done - still waiting on Facilities" in (m.body or "") for m in _mails_to(session, ADMIN))
    fac_order = [m for m in _mails_to(session, "facilities@acme-real.com") if "WORK ORDER" in m.subject][-1]
    _run(session, tid, _mail(session, tid, "done, desk 3F-12 allocated", sender="facilities@acme-real.com",
                             subject=f"Re: {fac_order.subject}"))
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED"
    assert "Good news" in _mails_to(session, "hr.lead@acme-real.com")[-1].body
    assert any("Completed - Facilities & Maintenance finished the last part" in (m.body or "")
               for m in _mails_to(session, ADMIN))


def test_admin_standing_in_for_a_team_only_finishes_that_team(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "HR", "hr.lead@acme-real.com")
    _set_dept_email(session, "FACILITIES", "facilities@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding for Naman Kumar",
         "details": {"employee_name": "Naman Kumar", "joining_date": "2026-10-02"}},
    ))
    _run(session, tid, _mail(session, tid, _PRIYA, subject="New Joining - Naman", sender="hr.lead@acme-real.com"), fake)
    case = session.exec(select(Outcome)).one()
    it_order = [m for m in _mails_to(session, ADMIN) if "WORK ORDER" in m.subject][-1]
    _run(session, tid, _mail(session, tid, "i have arranged everything, will hand over when he arrives",
                             sender=ADMIN, subject=f"Re: {it_order.subject}"))
    session.refresh(case)
    assert case.facts["agent_stage"] != "RESOLVED", "Facilities hasn't finished yet"
    assert "Still in progress: Facilities" in _mails_to(session, "hr.lead@acme-real.com")[-1].body

    _run(session, tid, _mail(session, tid, "i have arranged everything again", sender=ADMIN, subject=f"Re: {it_order.subject}"))
    session.refresh(case)
    assert case.facts["agent_stage"] != "RESOLVED", "a repeat reply from a finished team doesn't close the case"

    fac_order = [m for m in _mails_to(session, "facilities@acme-real.com") if "WORK ORDER" in m.subject][-1]
    _run(session, tid, _mail(session, tid, "desk is ready", sender="facilities@acme-real.com",
                             subject=f"Re: {fac_order.subject}"))
    session.refresh(case)
    assert case.facts["agent_stage"] == "RESOLVED"
    assert "Good news" in _mails_to(session, "hr.lead@acme-real.com")[-1].body


def test_team_replies_are_read_by_the_ai_not_keywords(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "HR", "hr.lead@acme-real.com")
    _set_dept_email(session, "IT", "it-helpdesk@acme-real.com")
    _set_dept_email(session, "FACILITIES", "facilities@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding for Naman Kumar",
         "details": {"employee_name": "Naman Kumar", "joining_date": "2026-10-02"}},
    ))
    _run(session, tid, _mail(session, tid, _PRIYA, subject="New Joining - Naman", sender="hr.lead@acme-real.com"), fake)
    case = session.exec(select(Outcome)).one()
    fac_order = [m for m in _mails_to(session, "facilities@acme-real.com") if "WORK ORDER" in m.subject][-1]

    reader = FakeGemini({"action": "done", "note": "Workstation 3F-12 is good to go", "confidence": 0.95})
    _run(session, tid, _mail(session, tid, "the workstation is good to go, 3F-12", sender="facilities@acme-real.com",
                             subject=f"Re: {fac_order.subject}"), reader)
    assert reader.payloads and reader.payloads[0]["YOUR_TASKS"] == ["A desk/workstation near the marketing team"]
    session.refresh(case)
    fac = next(g for g in case.facts["team_groups"] if g["label"].startswith("Facilities"))
    assert fac["done"] and fac["note"] == "Workstation 3F-12 is good to go"
    assert "Facilities & Maintenance has finished their part" in _mails_to(session, "hr.lead@acme-real.com")[-1].body

    it_order = _mails_to(session, "it-helpdesk@acme-real.com")[-1]
    reader = FakeGemini({"action": "blocked", "note": "Waiting for laptop stock from the vendor", "confidence": 0.9})
    _run(session, tid, _mail(session, tid, "laptops are out of stock, vendor delivery friday", sender="it-helpdesk@acme-real.com",
                             subject=f"Re: {it_order.subject}"), reader)
    session.refresh(case)
    assert case.facts["agent_stage"] == "BLOCKED"
    assert "Waiting for laptop stock from the vendor" in _mails_to(session, "hr.lead@acme-real.com")[-1].body


def test_done_phrasings():
    from app.agent.desk import _is_done_reply

    for text in ("desk is ready", "laptop handed over", "email id created", "access card issued", "all set up"):
        assert _is_done_reply(text), text
    for text in ("will be ready by 4", "not ready yet", "almost ready"):
        assert not _is_done_reply(text), text


def test_tasks_are_read_from_the_email_list_when_the_ai_gives_none(session: Session, env):
    tid = _tid(session)
    _priya_case(session, tid, [])
    it = _mails_to(session, "it-helpdesk@acme-real.com")[-1].body
    assert "1. Laptop, company email ID and system access" in it
    fac = [m.body for m in _mails_to(session, "facilities@acme-real.com") if "WORK ORDER" in m.subject][0]
    assert "A desk/workstation near the marketing team" in fac
    assert "2. ID and access card for the office" in it
    assert "Name: Priya Sharma" not in fac.split("Requester:")[0], "'Key: value' facts are not tasks"


def test_name_given_in_the_email_is_never_asked_for_again(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "IT", "it-helpdesk@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding logistics for Priya Sharma",
         "details": {"on_behalf_of": "Priya Sharma", "employee_id": "EMP-2041", "location": "3rd floor, Bengaluru"}},
    ))
    _run(session, tid, _mail(session, tid, _PRIYA.replace("- Name: Priya Sharma", "- Name: Priya Sharma\n- Joining date: 1 October 2026"),
                             subject="New Joining - Priya Sharma", sender="hr.lead@acme.demo"), fake)
    case = session.exec(select(Outcome)).one()
    assert case.facts["agent_stage"] == "DISPATCHED", case.facts.get("missing")
    assert case.facts["details"]["employee_name"] == "Priya Sharma"
    assert case.facts["details"]["joining_date"] == "1 October 2026"
    reply = _mails_to(session, "hr.lead@acme.demo")[-1].body
    assert "name?" not in reply


def test_new_email_about_another_joiner_is_a_new_case_not_an_update(session: Session, env):
    tid = _tid(session)
    first = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding for Priya Sharma",
         "details": {"employee_name": "Priya Sharma", "employee_id": "EMP-2041"}},
    ))
    _run(session, tid, _mail(session, tid, "Priya Sharma joins, EMP-2041, please set up", subject="New Joining - Priya",
                             sender="hr.lead@acme.demo", thread="t-priya"), first)
    priya = session.exec(select(Outcome)).one()
    assert priya.facts["agent_stage"] == "AWAITING_INFO"

    linked = FakeGemini(_decision(
        {"type": "update_case", "category": "onboarding", "case_reference": priya.case_reference,
         "details": {"employee_name": "Amit Kumar", "employee_id": "EMP-2046", "joining_date": "2026-10-01"}},
    ))
    _run(session, tid, _mail(session, tid, "Details:\n- Name: Amit Kumar\n- Employee ID: EMP-2046\n- Joining date: 1 Oct",
                             subject="New Joining - Amit Kumar", sender="hr.lead@acme.demo", thread="t-amit"), linked)
    cases = {c.title: c for c in session.exec(select(Outcome)).all()}
    assert len(cases) == 2, "Amit gets his own case"
    session.refresh(priya)
    assert priya.facts["details"]["employee_name"] == "Priya Sharma", "Priya's case is untouched"


def test_reply_in_the_case_thread_still_updates_it(session: Session, env):
    tid = _tid(session)
    first = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding",
         "details": {"employee_id": "EMP-2041"}},
    ))
    _run(session, tid, _mail(session, tid, "new joiner EMP-2041, please set up", sender="hr.lead@acme.demo", thread="t-x"), first)
    case = session.exec(select(Outcome)).one()
    answer = FakeGemini(_decision(
        {"type": "update_case", "category": "onboarding", "case_reference": case.case_reference,
         "details": {"employee_name": "Priya Sharma", "joining_date": "2026-10-01"}},
    ))
    _run(session, tid, _mail(session, tid, "Her name is Priya Sharma, joining 1 Oct", sender="hr.lead@acme.demo", thread="t-x"), answer)
    assert len(session.exec(select(Outcome)).all()) == 1
    session.refresh(case)
    assert case.facts["details"]["employee_name"] == "Priya Sharma"


def test_fill_required_reads_label_lines():
    from app.agent.playbooks import fill_required, missing_questions

    filled = fill_required("onboarding", {}, "Details:\n- Name: Ravi Kumar\n- Date of joining: 12 Oct")
    assert filled["employee_name"] == "Ravi Kumar" and filled["joining_date"] == "12 Oct"
    assert missing_questions("onboarding", filled) == []


def test_split_tasks_defaults_and_unmatched():
    from app.agent.playbooks import split_tasks

    out = split_tasks("onboarding", ["Arrange a welcome lunch with the team"],
                      ["onboarding", "it_support", "maintenance", "access_card"], {"employee_name": "Ravi", "joining_date": "12 Oct"})
    assert out["onboarding"] == ["Arrange a welcome lunch with the team"]
    assert out["it_support"] == ["Laptop, company email ID and system logins ready for Ravi by 12 Oct"]
    assert out["access_card"] == ["Issue ID and access card for Ravi"]


def test_onboarding_for_someone_who_already_joined_skips_report_on_wording(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "onboarding", "summary": "Onboarding for Priya Sharma",
         "details": {"employee_name": "Priya Sharma", "joining_date": "2020-01-15", "location": "Bengaluru office"}},
    ))
    _run(session, tid, _mail(session, tid, "Priya Sharma joined today, please set her up", sender="hr.lead@acme.demo"), fake)
    reply = _mails_to(session, "hr.lead@acme.demo")[-1]
    assert "First-days note for Priya Sharma" in reply.body and "Report on" not in reply.body
    assert reply.body.count("note for Priya Sharma") == 1


def test_travel_asks_only_for_what_is_missing(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "cab", "summary": "Cab to airport", "details": {"destination": "IGI Airport T3"}},
    ))
    _run(session, tid, _mail(session, tid, "need a cab to airport"), fake)
    case = session.exec(select(Outcome)).one()
    assert case.facts["agent_stage"] == "AWAITING_INFO"
    assert case.facts["missing"] == ["When do you need to travel (date and time)?"]


def test_unknown_work_with_no_team_goes_to_admin(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "event_planning", "summary": "Diwali party for 80 people",
         "details": {"headcount": 80}},
    ))
    _run(session, tid, _mail(session, tid, "can admin organise the diwali party for 80 ppl"), fake)
    case = session.exec(select(Outcome)).one()
    assert case.facts["agent_stage"] == "AWAITING_APPROVAL"
    assert "no team is set up" in case.facts["decision_reason"]
    assert session.exec(select(Approval)).one().decision == "PENDING"


def test_ungrounded_draft_is_replaced_by_the_truth(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "plumbing", "summary": "Blocked drain", "details": {"location": "pantry"}},
        reply="Hi Arjun,\n\nThe drain has been fixed! [[REF1]]\n\nWorkplace Team",
    ))
    _run(session, tid, _mail(session, tid, "pantry drain blocked"), fake)
    reply = _mails_to(session, REQ)[-1]
    assert "has been fixed" not in reply.body and "assigned it to" in reply.body


def test_question_is_answered_without_opening_a_case(session: Session, env):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "question", "category": "general", "summary": "Wi-Fi password"},
        reply="Hi Arjun,\n\nThe guest Wi-Fi details are at reception.\n\nWorkplace Team",
    ))
    result = _run(session, tid, _mail(session, tid, "whats the wifi pwd for guests?"), fake)
    assert result["status"] == "agent_handled" and result["case_reference"] is None
    assert session.exec(select(Outcome)).all() == []
    assert "Wi-Fi" in _mails_to(session, REQ)[-1].body


def test_admin_can_change_details_and_close_any_case(session: Session, env):
    tid = _tid(session)
    _run(session, tid, _mail(session, tid, "Fan not working in cabin 12", subject="fan"))
    case = session.exec(select(Outcome)).one()
    order = [m for m in _mails_to(session, ADMIN) if "WORK ORDER" in m.subject][-1]
    assert '"change <detail> to <value>"' in order.body

    result = _run(session, tid, _mail(session, tid, "change visit slot to Friday 4 PM", sender=ADMIN, subject=f"Re: {order.subject}"))
    assert result["action"] == "change"
    session.refresh(case)
    assert case.facts["details"]["visit_slot"] == "Friday 4 PM"
    assert "visit slot is now Friday 4 PM" in _mails_to(session, REQ)[-1].body

    result = _run(session, tid, _mail(session, tid, "close", sender=ADMIN, subject=f"Re: {order.subject}"))
    assert result["action"] == "close"
    session.refresh(case)
    assert case.status == "CLOSED"


def test_digest_mode_batches_completion_notes(session: Session, env):
    env.setenv("ADMIN_FYI_LEVEL", "digest")
    from app.core.config import get_settings

    get_settings.cache_clear()
    tid = _tid(session)
    _set_dept_email(session, "SECURITY", "frontdesk@acme-real.com")
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "visitor", "summary": "Visitor Monday",
         "details": {"visitor_names": ["Karan Mehta (EY)"], "visit_date": "Monday 12 Oct"}},
    ))
    _run(session, tid, _mail(session, tid, "Karan Mehta from EY visiting Monday"), fake)
    case = session.exec(select(Outcome)).one()
    assert not any("Completed by the desk" in m.subject for m in _mails_to(session, ADMIN))

    assert send_admin_digest(session, tid, force=True)["sent"] is True
    digest = [m for m in _mails_to(session, ADMIN) if "daily summary" in m.subject][-1]
    assert case.case_reference in digest.body


def test_demo_reset_clears_desk_tickets_and_passes(session: Session, env):
    from app.services.demo_reset import reset_demo_operational_data

    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": "visitor", "summary": "Visitor",
         "details": {"visitor_names": ["Riya Sen (KPMG)"], "visit_date": "Tuesday 13 Oct"}},
    ))
    _run(session, tid, _mail(session, tid, "Riya Sen from KPMG visiting Tuesday"), fake)
    assert session.exec(select(ServiceTicket)).all() and session.exec(select(VisitorPass)).all()
    reset_demo_operational_data(session, tid)
    assert session.exec(select(ServiceTicket)).all() == []
    assert session.exec(select(VisitorPass)).all() == []
    assert session.exec(select(Outcome)).all() == []


def test_permanent_employee_parking_goes_to_security_without_a_date(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "SECURITY", "frontdesk@acme-real.com")
    first = FakeGemini(_decision(
        {"type": "new_request", "category": "car_parking", "summary": "Car parking allocation", "details": {},
         "missing": ["What is the vehicle number?", "Which date do you need parking?"]},
    ))
    _run(session, tid, _mail(session, tid, "I need car parking", subject="hi", thread="t-prk"), first)
    case = session.exec(select(Outcome)).one()
    assert case.facts["agent_stage"] == "AWAITING_INFO"

    second = FakeGemini(_decision(
        {"type": "update_case", "case_reference": case.case_reference, "category": "parking",
         "details": {"car_no": "DL2caz9103"}},
        reply="Hi Kapil,\n\nThanks! I've forwarded it to the Security team.\n\nWorkplace Team",
    ))
    _run(session, tid, _mail(
        session, tid, "Car No: DL2caz9103\n\nI am new joinee and need permanent car parking",
        subject="Re: hi", thread="t-prk",
    ), second)
    session.refresh(case)
    assert case.facts["agent_stage"] == "DISPATCHED"
    assert case.facts["details"]["vehicle_numbers"] == "DL2caz9103"
    order = _mails_to(session, "frontdesk@acme-real.com")[-1]
    assert "permanent allocation" in order.subject.lower() or "permanent allocation" in order.body.lower()
    assert session.exec(select(VisitorPass)).all() == []


def test_update_reply_claiming_forwarded_is_replaced_when_still_waiting(session: Session, env):
    tid = _tid(session)
    first = FakeGemini(_decision(
        {"type": "new_request", "category": "parking", "summary": "Guest parking", "details": {}},
    ))
    _run(session, tid, _mail(session, tid, "need guest parking", subject="parking", thread="t-g"), first)
    case = session.exec(select(Outcome)).one()
    second = FakeGemini(_decision(
        {"type": "update_case", "case_reference": case.case_reference, "category": "parking",
         "details": {"car_no": "HR26AB1234"}},
        reply="Hi,\n\nThanks - forwarded to Security.\n\nWorkplace Team",
    ))
    _run(session, tid, _mail(session, tid, "car HR26AB1234", subject="Re: parking", thread="t-g"), second)
    session.refresh(case)
    assert case.facts["agent_stage"] == "AWAITING_INFO"
    reply = _mails_to(session, REQ)[-1]
    assert "forwarded" not in reply.body.lower() and "Which date do you need parking?" in reply.body


def test_tool_catalogue_marks_room_and_invoice_as_existing_flows():
    assert legacy_categories() == {"meeting_room", "invoice"}
    tools = {t["tool"]: t for t in tool_catalogue()}
    assert tools["escalate_to_admin"]["risk"] == "admin"
    assert tools["register_visitor"]["risk"] == "low"
