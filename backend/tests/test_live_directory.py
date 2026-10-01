"""End-to-end mail flows with the directory set up exactly like the live dashboard."""

import re
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.company import Department
from app.models.outcome import Outcome
from test_admin_desk import FakeGemini, _mail, _mails_to, _run, _tid

ADMIN = "skcbsa1221@gmail.com"
HR = "kshitiz.vishwakarma2003@gmail.com"
IT = "it.servicess8989@gmail.com"
FAC = "flexxftw12@gmail.com"
CAF = "cateringservices4656@gmail.com"
EMP = "rohan.mehta@acme.demo"

LIVE = {
    "ADMIN": (ADMIN, ADMIN, 0.0),
    "CAFETERIA": (CAF, CAF, 0.0),
    "FACILITIES": (FAC, FAC, 1000.0),
    "HR": (HR, HR, 0.0),
    "IT": (IT, IT, 0.0),
}


@pytest.fixture
def live(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    get_settings.cache_clear()
    for dept in session.exec(select(Department)).all():
        if dept.code in LIVE:
            dept.primary_email, dept.approver_email, dept.spend_approval_limit = LIVE[dept.code]
        else:
            dept.primary_email, dept.approver_email = f"{dept.code.lower()}@example.invalid", None
        dept.backup_emails = []
        session.add(dept)
    session.commit()
    yield _tid(session)
    import os
    if os.getenv("DUMP_MAILS"):
        from app.models.outcome import Communication
        for m in session.exec(select(Communication)).all():
            print("\n=====", m.recipients, "|", m.subject, "\n", m.body)
    get_settings.cache_clear()


def _ai(*intents: dict) -> FakeGemini:
    return FakeGemini({"intents": list(intents), "reply_to_requester": "", "confidence": 0.9})


def _reads(action: str, note: str) -> FakeGemini:
    return FakeGemini({"action": action, "note": note, "confidence": 0.9})


def _orders(session, addr):
    return [m for m in _mails_to(session, addr) if "WORK ORDER" in (m.subject or "") or "WORK ORDER" in (m.body or "")]


def _reply(session, tid, body, sender, to_mail, provider=None):
    return _run(session, tid, _mail(session, tid, body, sender=sender, subject=f"Re: {to_mail.subject}"), provider)


def _case(session) -> Outcome:
    case = session.exec(select(Outcome)).one()
    session.refresh(case)
    return case


def _joining_in(days: int) -> date:
    return (datetime.now(timezone(timedelta(hours=5, minutes=30))) + timedelta(days=days)).date()


def test_onboarding_from_hr_runs_end_to_end(session: Session, live):
    from app.agent.lifecycle import sweep_desk_cases

    tid = live
    joins = _joining_in(4)
    when = f"{joins.day} {joins:%B %Y}"
    body = (
        "Hi team,\n\nPlease arrange onboarding for our new joinee.\n\n"
        f"Employee name: Naman Kumar\nJoining date: {when}\nDepartment: Marketing\n\n"
        "1. Laptop with Office and VPN\n2. Access card\n3. A desk near the marketing team\n\nRegards,\nKshitiz (HR)"
    )
    _run(session, tid, _mail(session, tid, body, sender=HR, subject="New joinee - Naman Kumar"), FakeGemini({
        "intents": [{"type": "new_request", "category": "onboarding", "summary": "Onboarding for Naman Kumar",
                     "details": {"employee_name": "Naman Kumar", "joining_date": when, "department": "Marketing",
                                 "items": ["Laptop with Office and VPN", "Access card", "A desk near the marketing team"]},
                     "tasks": ["Laptop with Office and VPN", "Access card", "A desk near the marketing team"]}],
        "reply_to_requester": f"Hi Kshitiz,\n\nThanks - onboarding for Naman Kumar on {when} is under way ([[REF1]]).\n\n"
                              "Best regards,\nWorkplace Team",
        "confidence": 0.9,
    }))
    case = _case(session)
    assert case.facts["agent_stage"] == "DISPATCHED"
    assert case.facts["joining_on"] == joins.isoformat()
    ack = _mails_to(session, HR)[0].body
    assert ack.index("Day-1 note") < ack.index("Best regards"), "the Day-1 note goes above the sign-off"
    assert not _orders(session, HR), "HR raised it, it must not get its own work order"

    it_orders, fac_orders = _orders(session, IT), _orders(session, FAC)
    assert len(it_orders) == 1 and len(fac_orders) == 1
    assert "Laptop with Office and VPN" in it_orders[0].body and "Access card" in it_orders[0].body
    assert "A desk near the marketing team" in fac_orders[0].body and "Laptop" not in fac_orders[0].body
    assert "Naman Kumar" in it_orders[0].body
    assert "Teams working on it: IT Support, Facilities & Maintenance" in it_orders[0].body
    assert "Team: People / HR" not in it_orders[0].body
    assert any("Naman Kumar" in m.body for m in _mails_to(session, HR))

    _reply(session, tid, "laptop is being imaged, will be done by evening", IT, it_orders[0],
           _reads("progress", "Laptop is being imaged, ready by evening"))
    assert "Laptop is being imaged" in _mails_to(session, HR)[-1].body
    assert "Laptop is being imaged" in _mails_to(session, ADMIN)[-1].body

    _reply(session, tid, "desk is ready, 3F-12", FAC, fac_orders[0], _reads("done", "Desk 3F-12 is ready"))
    case = _case(session)
    assert case.facts["agent_stage"] != "RESOLVED"
    assert "Facilities & Maintenance has finished" in _mails_to(session, HR)[-1].body

    _reply(session, tid, "everything is arranged, will hand over the laptop and card when he joins", IT, it_orders[0],
           _reads("done", "Laptop and card ready - handover when he joins"))
    case = _case(session)
    assert case.facts["agent_stage"] == "READY_FOR_JOINING", "prepared is not finished - the handover is still ahead"
    assert case.status != "RESOLVED"
    ready = _mails_to(session, HR)[-1].body
    assert "Everything for Naman Kumar is ready" in ready and "confirm they've handed everything over" in ready
    assert "Good news" not in ready
    assert any("Ready for joining" in m.body for m in _mails_to(session, ADMIN))

    the_day_before = datetime.combine(joins - timedelta(days=1), time(12, 0)) - timedelta(hours=5, minutes=30)
    assert sweep_desk_cases(session, tid, now=the_day_before)["handover_checks"] == 0
    joining_morning = datetime.combine(joins, time(10, 0)) - timedelta(hours=5, minutes=30)
    assert sweep_desk_cases(session, tid, now=joining_morning)["handover_checks"] == 1
    assert sweep_desk_cases(session, tid, now=joining_morning + timedelta(minutes=5))["handover_checks"] == 0
    case = _case(session)
    assert case.facts["agent_stage"] == "DISPATCHED"
    it_check, fac_check = _mails_to(session, IT)[-1], _mails_to(session, FAC)[-1]
    assert "Naman Kumar joins today" in it_check.body and "Laptop with Office and VPN" in it_check.body
    assert "Naman Kumar joins today" in fac_check.body and "desk" in fac_check.body
    assert "joins today" in _mails_to(session, HR)[-1].body

    _reply(session, tid, "laptop and card handed over", IT, it_check, _reads("done", "Laptop and access card handed over"))
    assert _case(session).facts["agent_stage"] != "RESOLVED"
    _reply(session, tid, "he is seated at 3F-12", FAC, fac_check, _reads("done", "Seated at desk 3F-12"))
    case = _case(session)
    assert case.facts["agent_stage"] == "RESOLVED"
    assert all(g["done"] for g in case.facts["team_groups"] if not g.get("raised_by_team"))
    assert "Good news" in _mails_to(session, HR)[-1].body
    completed = [m for m in _mails_to(session, ADMIN) if "Completed - Facilities & Maintenance finished the last part" in m.body]
    assert len(completed) == 1 and "Seated at desk 3F-12" in completed[0].body

    def strip_re(s):
        return re.sub(r"^\s*(?:re\s*:\s*)+", "", s or "", flags=re.I)

    for addr in (HR, IT, FAC, ADMIN):
        subjects = {strip_re(m.subject) for m in _mails_to(session, addr)}
        assert len(subjects) == 1, f"{addr} got updates in more than one thread: {subjects}"
    assert strip_re(_mails_to(session, HR)[0].subject) == "New joinee - Naman Kumar [ONB-2026-0001]"


def test_updates_to_a_team_reply_to_the_previous_mail(session: Session, live):
    from app.services.communication import CommunicationService

    tid = live
    _run(session, tid, _mail(session, tid, "AC not cooling at 4th floor near pantry", sender=EMP, subject="AC issue"), _ai(
        {"type": "new_request", "category": "hvac", "summary": "AC not cooling on 4th floor",
         "details": {"location": "4th floor near pantry"}},
    ))
    case = _case(session)

    class Sender:
        sent: list[dict] = []

        def get_account_email(self):
            return "orchestration@adminservices.in"

        def send_reply(self, *, to, subject, body, conversation_id=None, in_reply_to_message_id=None):
            self.sent.append({"subject": subject, "refs": conversation_id, "parent": in_reply_to_message_id})
            return f"id-{len(self.sent)}"

    comms = CommunicationService(session, tid, email_sender=Sender())
    for i in range(3):
        comms.send_case_update(outcome=case, communication_type="INFORMATION_ONLY", body=f"update {i}",
                               recipients=[FAC], action_label="OPS UPDATE", subject_hint=f"Headline {i}",
                               suppress_fingerprint=f"u{i}")
    first, second, third = Sender.sent
    assert first["subject"] == second["subject"] == third["subject"] == _orders(session, FAC)[0].subject
    assert second["parent"] == "<id-1@cloudmta.net>" and third["parent"] == "<id-2@cloudmta.net>"
    assert second["refs"] == third["refs"] == "<id-1@cloudmta.net>"


def test_reply_chain_uses_the_message_id_recipients_see():
    from app.services.communication import _rfc_message_id

    assert _rfc_message_id("a0578687-11aa") == "<a0578687-11aa@cloudmta.net>"
    assert _rfc_message_id("<x@mail.gmail.com>") == "<x@mail.gmail.com>"
    assert _rfc_message_id("x@mail.gmail.com") == "<x@mail.gmail.com>"
    assert _rfc_message_id("cloudmailin-api:user") is None and _rfc_message_id(None) is None

def test_ac_complaint_goes_to_facilities_and_back(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "AC not cooling at 4th floor near pantry", sender=EMP, subject="AC issue"), _ai(
        {"type": "new_request", "category": "hvac", "summary": "AC not cooling on 4th floor",
         "details": {"location": "4th floor near pantry", "issue": "AC not cooling"}},
    ))
    order = _orders(session, FAC)[-1]
    assert not _orders(session, ADMIN)
    _reply(session, tid, "technician will reach in 30 mins", FAC, order, _reads("progress", "Technician arriving in 30 minutes"))
    assert "Technician arriving in 30 minutes" in _mails_to(session, EMP)[-1].body
    _reply(session, tid, "gas refilled, cooling fine now", FAC, order, _reads("done", "Gas refilled, cooling restored"))
    assert _case(session).facts["agent_stage"] == "RESOLVED"
    assert "Gas refilled" in _mails_to(session, EMP)[-1].body


def test_laptop_issue_blocked_then_done_by_it(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "my laptop is not booting, shows blue screen", sender=EMP, subject="laptop"), _ai(
        {"type": "new_request", "category": "laptop", "summary": "Laptop not booting (blue screen)",
         "details": {"issue": "laptop not booting, blue screen"}},
    ))
    order = _orders(session, IT)[-1]
    _reply(session, tid, "need the motherboard from dell, 3 days", IT, order, _reads("blocked", "Waiting for a motherboard from Dell (3 days)"))
    assert _case(session).facts["agent_stage"] == "BLOCKED"
    assert "motherboard" in _mails_to(session, EMP)[-1].body
    assert "motherboard" in _mails_to(session, ADMIN)[-1].body
    _reply(session, tid, "replaced the board, laptop returned to user", IT, order, _reads("done", "Motherboard replaced, laptop returned"))
    assert _case(session).facts["agent_stage"] == "RESOLVED"


def test_catering_needs_approval_cafeteria_head_approves(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "Need lunch for 20 people tomorrow 1 PM in the board room", sender=EMP, subject="lunch"), _ai(
        {"type": "new_request", "category": "catering", "summary": "Lunch for 20, tomorrow 1 PM",
         "details": {"date": "tomorrow", "time": "1 PM", "headcount": 20, "location": "board room"}},
    ))
    case = _case(session)
    assert case.facts["agent_stage"] == "AWAITING_APPROVAL"
    decision = [m for m in _mails_to(session, CAF) if 'Reply "approve"' in m.body][-1]
    assert ADMIN in decision.recipients
    assert not _orders(session, CAF)

    _reply(session, tid, "approve", CAF, decision)
    case = _case(session)
    assert case.facts["agent_stage"] == "DISPATCHED"
    order = _orders(session, CAF)[-1]
    assert "Visit date" not in order.body and "- Date: tomorrow" in order.body
    _reply(session, tid, "lunch served", CAF, order, _reads("done", "Lunch for 20 served in the board room"))
    assert _case(session).facts["agent_stage"] == "RESOLVED"
    assert "Lunch for 20 served" in _mails_to(session, EMP)[-1].body


def test_catering_date_given_later_waits_for_approval_and_is_due_by_the_meal(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "i need food for 30 people , on 3rd floor , 10 veg rest non veg",
                             sender=EMP, subject="need catering", thread="t-cat"), _ai(
        {"type": "new_request", "category": "catering", "summary": "Catering for 30 people on 3rd floor",
         "details": {"headcount": 30, "location": "3rd floor", "meal_preference": "10 veg, 20 non-veg"},
         "missing": ["For which date and time?"]},
    ))
    case = _case(session)
    assert case.facts["agent_stage"] == "AWAITING_INFO"

    meal = datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None, second=0, microsecond=0) + timedelta(hours=3)
    meal_day, meal_time = f"{meal.day} {meal:%B %Y}", meal.strftime("%H:%M")
    _run(session, tid, _mail(session, tid, f"{meal_day}, {meal_time}", sender=EMP, subject="Re: need catering", thread="t-cat"),
         FakeGemini({
             "intents": [{"type": "update_case", "case_reference": case.case_reference, "category": "catering",
                          "details": {"date": meal_day, "time": meal_time}}],
             "reply_to_requester": "Hi,\n\nThanks - I've updated your request and passed it on to the Cafeteria team.\n\nWorkplace Team",
             "confidence": 0.9,
         }))
    case = _case(session)
    assert case.facts["agent_stage"] == "AWAITING_APPROVAL"
    told = _mails_to(session, EMP)[-1].body
    assert "passed it on to the Cafeteria" not in told and "approval" in told

    decision = [m for m in _mails_to(session, ADMIN) if 'Reply "approve"' in m.body][-1]
    _reply(session, tid, "approve", ADMIN, decision)
    case = _case(session)
    assert case.facts["agent_stage"] == "DISPATCHED"
    assert case.due_at == meal - timedelta(hours=5, minutes=30), "the team's deadline is the meal time, not 12h later"


def test_visitor_with_no_security_inbox_goes_to_admin(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "Visitor Neha Kapoor from Deloitte on 8 Oct 3 PM", sender=EMP, subject="visitor"), _ai(
        {"type": "new_request", "category": "visitor", "summary": "Visitor Neha Kapoor",
         "details": {"visitor_names": ["Neha Kapoor (Deloitte)"], "visit_date": "8 Oct", "visit_time": "3 PM"}},
    ))
    assert _case(session).facts["agent_stage"] == "COMPLETED"
    assert any("Neha Kapoor" in m.body for m in _mails_to(session, ADMIN))
    assert not [m for m in session.exec(select(Outcome)).all() if "example.invalid" in str(m.facts)]


def test_admin_team_request_is_handled_by_the_admin_inbox(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "Need 10 notebooks and 10 pens for the training room", sender=EMP, subject="supplies"), _ai(
        {"type": "new_request", "category": "supplies", "summary": "10 notebooks and 10 pens",
         "details": {"items": "10 notebooks, 10 pens", "location": "training room"}},
    ))
    order = _orders(session, ADMIN)[-1]
    _reply(session, tid, "kept in the training room", ADMIN, order, _reads("done", "Notebooks and pens placed in the training room"))
    assert _case(session).facts["agent_stage"] == "RESOLVED"
    assert "training room" in _mails_to(session, EMP)[-1].body


def test_offboarding_needs_approval_then_only_it_gets_one_order(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "Rahul Verma's last working day is 10 Oct, please do exit formalities", sender=HR, subject="Exit - Rahul Verma"), _ai(
        {"type": "new_request", "category": "offboarding", "summary": "Exit for Rahul Verma",
         "details": {"employee_name": "Rahul Verma", "last_working_day": "10 Oct"}},
    ))
    case = _case(session)
    assert case.facts["agent_stage"] == "AWAITING_APPROVAL"
    decision = [m for m in _mails_to(session, ADMIN) if 'Reply "approve"' in m.body][-1]
    _reply(session, tid, "approve", ADMIN, decision)
    case = _case(session)
    assert case.case_reference.startswith("EXT-")
    assert case.facts["agent_stage"] == "DISPATCHED"
    assert "assigned to IT Support" in _mails_to(session, HR)[-1].body
    assert len(_orders(session, IT)) == 1
    assert not _orders(session, HR) and not _orders(session, FAC)
    _reply(session, tid, "laptop collected and card deactivated", IT, _orders(session, IT)[-1],
           _reads("done", "Laptop collected, access card deactivated"))
    assert _case(session).facts["agent_stage"] == "RESOLVED"
    assert "Good news" in _mails_to(session, HR)[-1].body


def test_team_question_for_requester_is_passed_on(session: Session, live):
    tid = live
    _run(session, tid, _mail(session, tid, "Chair is broken at my desk 2F-08", sender=EMP, subject="chair"), _ai(
        {"type": "new_request", "category": "furniture", "summary": "Broken chair at 2F-08",
         "details": {"item": "chair", "location": "2F-08"}},
    ))
    order = _orders(session, FAC)[-1]
    _reply(session, tid, "is it the armrest or the wheel? and when is the user at desk", FAC, order,
           _reads("message", "Is it the armrest or the wheel, and when will you be at your desk?"))
    last = _mails_to(session, EMP)[-1]
    assert "armrest or the wheel" in last.body and "Facilities" in last.body
    assert _case(session).facts["agent_stage"] != "RESOLVED"
