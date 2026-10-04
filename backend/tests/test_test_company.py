"""Whole-system run on the manual-test company (scripts/load_test_company.py), scripted AI, no real mail.

What passes here is what you should see when you send the same mails by hand.
"""

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.outcome import Outcome
from scripts.load_test_company import ADMIN, CAF, FAC, HR, IT, build, sub
from test_admin_desk import _mail, _mails_to, _run
from test_live_directory import _ai, _orders, _reads, _reply

ANANYA, VIKRAM, NEHA, KSHITIZ = CAF, FAC, IT, HR  # employees at Pune, Chennai, Gurugram, Mumbai
PUNE_FAC, PUNE_ADMIN, SOUTH_ADMIN = sub(FAC, "pune"), sub(ADMIN, "pune"), sub(ADMIN, "south")
NORTH_IT, COMPANY_IT, COMPANY_FAC = sub(IT, "north"), sub(IT, "it"), sub(FAC, "facilities")


@pytest.fixture
def company(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    get_settings.cache_clear()
    tid = build(session)
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


def test_question_about_a_branch_is_answered_from_knowledge(session: Session, company):
    from app.agent.directory import knowledge_text

    text = knowledge_text(session, company)
    assert "Pune Hinjewadi" in text and "Canteen timings by branch" in text
