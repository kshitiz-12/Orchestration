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


def test_tool_catalogue_marks_room_and_invoice_as_existing_flows():
    assert legacy_categories() == {"meeting_room", "invoice"}
    tools = {t["tool"]: t for t in tool_catalogue()}
    assert tools["escalate_to_admin"]["risk"] == "admin"
    assert tools["register_visitor"]["risk"] == "low"
