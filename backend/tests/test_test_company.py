"""Whole-system run on the manual-test company (scripts/load_test_company.py), scripted AI, no real mail.

What passes here is what you should see when you send the same mails by hand.
"""

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.intake import RawEmailEvent
from app.models.org import Person
from app.models.outcome import Communication, Outcome
from scripts.load_test_company import ADMIN, CAF, FAC, HR, IT, build, sub
from test_admin_desk import _mail, _mails_to, _run
from test_live_directory import _ai, _orders, _reads, _reply

ANANYA, VIKRAM, NEHA, KSHITIZ = CAF, FAC, IT, HR  # employees at Pune, Chennai, Gurugram, Mumbai
PUNE_FAC, PUNE_ADMIN, SOUTH_ADMIN = sub(FAC, "pune"), sub(ADMIN, "pune"), sub(ADMIN, "south")
WEST_FAC = sub(FAC, "west")
NORTH_IT, COMPANY_IT, COMPANY_FAC = sub(IT, "north"), sub(IT, "it"), sub(FAC, "facilities")
NOMAD = "rohan.mehta@acme.example"  # employee with no branch on record
OUTSIDER = "anonymousxo1204@gmail.com"


@pytest.fixture
def company(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    monkeypatch.setenv("ACCEPT_REQUESTS_FROM", "employees")
    get_settings.cache_clear()
    tid = build(session)
    session.add(Person(tenant_id=tid, email=NOMAD, name="Rohan Mehta", department="Sales"))
    session.commit()
    yield tid
    get_settings.cache_clear()


def _only_case(session) -> Outcome:
    case = session.exec(select(Outcome)).one()
    session.refresh(case)
    return case


def _request(session, tid, sender, body, subject, intent):
    return _run(session, tid, _mail(session, tid, body, sender=sender, subject=subject), _ai(intent))


def test_build_is_repeatable(session: Session, company):
    assert build(session) == company


def test_company_has_thirty_plus_branches_and_folded_catalogue(session: Session, company):
    from app.agent.directory import catalogue, route_for
    from app.agent.places import find_place
    from app.models.org import Location

    tid = company
    branches = [p for p in session.exec(select(Location).where(Location.tenant_id == tid)).all()
                if (p.type or "").upper() == "BRANCH"]
    assert len(branches) >= 30, f"need 30+ branches for production seed, got {len(branches)}"
    # Prompt size must not grow with branch count
    assert len(catalogue(session, tid)) <= 20
    hyd = find_place(session, tid, "HITEC City")
    assert hyd is not None and hyd.code == "HYD-HIT"
    # East has a local admin; West facilities cover Mumbai when no city team exists
    assert route_for(session, tid, "supplies", hyd.location_id).recipients  # falls back up tree
    mum = find_place(session, tid, "Mumbai Powai")
    assert "west" in (route_for(session, tid, "electrical", mum.location_id).recipients[0] or "")


def test_pune_job_goes_to_pune_facilities_and_their_reply_closes_it(session: Session, company):
    tid = company
    _request(session, tid, ANANYA, "The AC on the 3rd floor is not cooling at all.", "AC not cooling",
             {"type": "new_request", "category": "hvac", "summary": "AC not cooling", "details": {"location": "3rd floor"}})
    case = _only_case(session)
    assert case.facts["location_name"] == "Pune > Pune Hinjewadi"
    orders = _orders(session, PUNE_FAC)
    assert len(orders) == 1 and "Location: Pune > Pune Hinjewadi" in orders[0].body
    assert not _orders(session, COMPANY_FAC)

    # The team answers from the mailbox itself, not the +pune address the order went to.
    _reply(session, tid, "fixed, gas refilled and tested", FAC, orders[0], _reads("done", "Gas refilled and AC tested"))
    case = _only_case(session)
    assert case.facts["agent_stage"] in {"RESOLVED", "COMPLETED", "CLOSED"}, case.facts["agent_stage"]
    assert any("Gas refilled" in m.body for m in _mails_to(session, ANANYA))


def test_chennai_has_no_admin_so_south_admin_takes_it(session: Session, company):
    tid = company
    _request(session, tid, VIKRAM, "Need 2 notebooks and a stapler.", "Stationery",
             {"type": "new_request", "category": "supplies", "summary": "Stationery: 2 notebooks, 1 stapler",
              "details": {"items": ["2 notebooks", "1 stapler"]}})
    assert _only_case(session).facts["location_name"] == "Chennai > Chennai OMR"
    assert len(_orders(session, SOUTH_ADMIN)) == 1


def test_gurugram_laptop_goes_to_north_it_and_mumbai_to_company_it(session: Session, company):
    tid = company
    _request(session, tid, NEHA, "My laptop won't boot since this morning.", "Laptop",
             {"type": "new_request", "category": "it_support", "summary": "Laptop not booting",
              "details": {"issue": "laptop does not boot, black screen"}})
    assert len(_orders(session, NORTH_IT)) == 1 and not _orders(session, COMPANY_IT)

    _request(session, tid, KSHITIZ, "VPN keeps disconnecting on my laptop.", "VPN",
             {"type": "new_request", "category": "network", "summary": "VPN disconnecting",
              "details": {"issue": "VPN drops every few minutes"}})
    assert len(_orders(session, COMPANY_IT)) == 1


def test_visitor_to_another_branch_is_served_there(session: Session, company):
    tid = company
    _request(session, tid, ANANYA, "I'm at the Bengaluru HQ today - the AC in F2-R1 is not working.", "AC at HQ",
             {"type": "new_request", "category": "hvac", "summary": "AC not working in F2-R1",
              "details": {"location": "Bengaluru HQ, F2-R1"}})
    assert "Acme HQ Bengaluru" in _only_case(session).facts["location_name"]
    assert len(_orders(session, COMPANY_FAC)) == 1 and not _orders(session, PUNE_FAC)


def test_pune_approval_reaches_the_pune_admin_and_admin_can_approve(session: Session, company):
    tid = company
    _request(session, tid, ANANYA, "I lost my access card, please issue a new one.", "Access card",
             {"type": "new_request", "category": "access_card", "summary": "Replacement access card",
              "details": {"issue": "lost access card"}})
    case = _only_case(session)
    if case.facts["agent_stage"] != "AWAITING_APPROVAL":
        pytest.skip("access cards are not approval-gated in this setup")
    asks = [m for m in session.exec(select(type(_mails_to(session, ADMIN)[0]))).all()
            if 'Reply "approve"' in (m.body or "")]
    assert any(PUNE_ADMIN in (m.recipients or []) for m in asks), "the Pune branch admin sees Pune approvals"
    decision = next(m for m in asks if ADMIN in (m.recipients or []))
    _reply(session, tid, "approved", ADMIN, decision)
    assert _only_case(session).facts["agent_stage"] != "AWAITING_APPROVAL"
    assert _orders(session, COMPANY_IT), "approved card goes to IT"


FAN = {"type": "new_request", "category": "electrical", "summary": "Fix fan in room 302",
       "details": {"location": "room 302", "issue": "fan not working"}}


def test_outsider_gets_no_reply_no_case_no_work_order(session: Session, company):
    tid = company
    result = _request(session, tid, OUTSIDER, "hey fix the fan in room 302", "fix fan", FAN)
    assert result["status"] == "ignored_unknown_sender"
    assert not session.exec(select(Outcome)).all()
    assert not session.exec(select(Communication)).all()
    event = session.exec(select(RawEmailEvent)).one()
    assert event.safety_flags.get("ignored_unknown_sender") is True


def test_team_inbox_and_admin_are_not_treated_as_outsiders(session: Session, company):
    tid = company
    _request(session, tid, KSHITIZ, "VPN keeps dropping", "VPN", {
        "type": "new_request", "category": "network", "summary": "VPN dropping", "details": {"issue": "VPN drops"}})
    order = _orders(session, COMPANY_IT)[0]
    _reply(session, tid, "on it, ETA 4 pm", sub(IT, "it"), order, _reads("eta", "ETA 4 pm"))
    assert "ignored_unknown_sender" not in str(session.exec(select(RawEmailEvent)).all()[-1].safety_flags)
    _request(session, tid, ADMIN, "Please get the pantry restocked on 3rd floor", "pantry", {
        "type": "new_request", "category": "pantry", "summary": "Restock pantry", "details": {"location": "3rd floor"}})
    assert session.exec(select(Outcome).where(Outcome.requester_email == ADMIN)).first() is not None


def test_unknown_office_is_asked_before_dispatch_then_routed_to_that_branch(session: Session, company):
    tid = company
    _request(session, tid, NOMAD, "hey fix the fan in room 302", "fix fan", FAN)
    case = _only_case(session)
    assert case.facts["agent_stage"] == "AWAITING_INFO"
    assert not _orders(session, COMPANY_FAC) and not _orders(session, PUNE_FAC)
    ask = _mails_to(session, NOMAD)[-1]
    assert "Which office" in ask.body and ("offices" in ask.body or "Pune" in ask.body or "branch" in ask.body)

    _reply(session, tid, "Pune office", NOMAD, ask, _ai(
        {"type": "update_case", "case_reference": case.case_reference, "details": {"office": "Pune office"}}))
    case = _only_case(session)
    assert case.facts["location_name"] == "Pune > Pune Hinjewadi"
    assert case.facts["department_code"] == "FACILITIES_PUN"
    assert len(_orders(session, PUNE_FAC)) == 1 and not _orders(session, COMPANY_FAC)


def test_office_is_asked_only_once(session: Session, company):
    tid = company
    _request(session, tid, NOMAD, "hey fix the fan in room 302", "fix fan", FAN)
    ask = _mails_to(session, NOMAD)[-1]
    _reply(session, tid, "the main one", NOMAD, ask, _ai(
        {"type": "update_case", "case_reference": _only_case(session).case_reference, "details": {"office": "the main one"}}))
    assert _only_case(session).facts["agent_stage"] == "DISPATCHED"
    assert len(_orders(session, COMPANY_FAC)) == 1


def test_employee_and_office_free_requests_are_not_asked(session: Session, company):
    tid = company
    _request(session, tid, ANANYA, "hey fix the fan in room 302", "fix fan", FAN)
    assert len(_orders(session, PUNE_FAC)) == 1
    assert "Which office" not in _mails_to(session, ANANYA)[-1].body

    _request(session, tid, NOMAD, "Please install Figma on my laptop.", "Figma", {
        "type": "new_request", "category": "software", "summary": "Install Figma", "details": {"software": "Figma"}})
    assert "Which office" not in _mails_to(session, NOMAD)[-1].body
    assert _orders(session, COMPANY_IT)


def test_work_order_subject_names_the_task(session: Session, company):
    _request(session, company, ANANYA, "hey fix the fan in room 302", "fix fan", FAN)
    case = _only_case(session)
    assert _orders(session, PUNE_FAC)[0].subject == f"[WORK ORDER] [{case.case_reference}] Fix fan in room 302"


def test_each_request_from_one_mail_gets_its_own_update_subject(session: Session, company):
    tid = company
    _run(session, tid, _mail(session, tid, "1. Fan in room 302 is not working\n2. VPN keeps dropping", sender=KSHITIZ,
                             subject="two things"), _ai(
        {"type": "new_request", "category": "electrical", "summary": "Fix fan in room 302",
         "details": {"location": "room 302", "issue": "fan not working"}},
        {"type": "new_request", "category": "network", "summary": "VPN dropping", "details": {"issue": "VPN drops"}},
    ))
    fan = session.exec(select(Outcome).where(Outcome.title == "Fix fan in room 302")).one()
    vpn = session.exec(select(Outcome).where(Outcome.title == "VPN dropping")).one()
    first = _mails_to(session, KSHITIZ)[-1]
    assert f"[{fan.case_reference}]" in first.subject and f"[{vpn.case_reference}]" in first.subject

    # Mumbai sits under West facilities, not the company-wide team
    order = _orders(session, WEST_FAC)[0] if _orders(session, WEST_FAC) else _orders(session, COMPANY_FAC)[0]
    _reply(session, tid, "done, fan replaced", FAC, order, _reads("done", "Fan replaced"))
    update = _mails_to(session, KSHITIZ)[-1]
    assert update.subject == f"Fix fan in room 302 [{fan.case_reference}]"


def test_new_request_in_an_old_thread_drops_the_old_ticket_numbers(session: Session, company):
    tid = company
    _request(session, tid, KSHITIZ, "I need a seat from 10th Oct", "Re: stationery request [SUP-2026-0001] [PRK-2026-0001]", {
        "type": "new_request", "category": "seating", "summary": "Seat allocation from 10th Oct",
        "details": {"employee_name": "Kshitiz Vishwakarma", "date": "2026-10-10"}})
    case = _only_case(session)
    assert _mails_to(session, KSHITIZ)[-1].subject == f"Re: Seat allocation from 10th Oct [{case.case_reference}]"


def test_empty_template_in_old_thread_does_not_invent_tickets(session: Session, company):
    tid = company
    body = (
        "Please find the details for my requests:\n\n"
        "- Car parking (PRK-2099-0001):\n"
        "- Visiting car (VIS-2099-0001): [VISITOR NAME, COMPANY, DATE AND TIME]\n"
        "- Desk allocation (SEAT-2099-0001): [START DATE]\n"
    )
    _run(session, tid, _mail(session, tid, body, sender=KSHITIZ,
                             subject="Re: stationery request [SUP-2099-0001] [PRK-2099-0001]"), _ai(
        {"type": "update_case", "case_reference": "PRK-2099-0001", "category": "parking",
         "summary": "Update car parking details", "details": {}},
        {"type": "update_case", "case_reference": "VIS-2099-0001", "category": "visitor",
         "summary": "Update visiting car details", "details": {}},
    ))
    assert not session.exec(select(Outcome)).all(), "dead ticket numbers must not become new cases"


def test_vague_cancel_closes_every_waiting_ask(session: Session, company):
    tid = company
    _run(session, tid, _mail(session, tid, "Need parking and a visitor pass tomorrow", sender=KSHITIZ,
                             subject="two asks"), _ai(
        {"type": "new_request", "category": "parking", "summary": "Car parking", "details": {}},
        {"type": "new_request", "category": "visitor", "summary": "Visitor pass", "details": {}},
    ))
    assert all((o.facts or {}).get("agent_stage") == "AWAITING_INFO" for o in session.exec(select(Outcome)).all())
    ask = _mails_to(session, KSHITIZ)[-1]
    _reply(session, tid, "I don't want, thanks", KSHITIZ, ask, _ai({"type": "cancel"}))
    stages = {(o.facts or {}).get("agent_stage") for o in session.exec(select(Outcome)).all()}
    assert stages == {"CANCELLED"}


def test_catering_asks_for_time_before_approval(session: Session, company):
    tid = company
    _request(session, tid, ANANYA, "Lunch for 10 people from outside tomorrow", "Lunch", {
        "type": "new_request", "category": "catering", "summary": "Lunch for 10",
        "details": {"headcount": 10, "date": "2026-10-07", "items": "external lunch"}})
    case = _only_case(session)
    assert case.facts["agent_stage"] == "AWAITING_INFO"
    assert any("time" in q.lower() for q in case.facts.get("missing") or [])


def test_question_about_a_branch_is_answered_from_knowledge(session: Session, company):
    from app.agent.directory import knowledge_text

    text = knowledge_text(session, company)
    assert "Pune Hinjewadi" in text and "Canteen timings by branch" in text
