"""Closing the AI learning loop: human corrections, knowledge drafts, suggested rules, accuracy and regression check."""

from sqlmodel import Session, select

from app.agent.ai_eval import GOLDEN, run_eval
from app.agent.directory import department_for
from app.agent.learning import accuracy_summary, apply_route_rule, rule_suggestions
from app.models.company import Department, KnowledgeEntry, ServiceTicket
from app.models.outcome import Outcome
from test_admin_desk import ADMIN, REQ, FakeGemini, _mail, _mails_to, _run, _tid, env  # noqa: F401
from test_admin_desk_scenarios import _decision, _set_dept_email


def _case(session, tid, summary, category="maintenance", body=None, thread=None):
    fake = FakeGemini(_decision(
        {"type": "new_request", "category": category, "summary": summary,
         "details": {"location": "cabin 7", "issue": summary}},
    ))
    _run(session, tid, _mail(session, tid, body or summary, subject=summary, thread=thread), fake)
    return session.exec(select(Outcome).where(Outcome.title == summary)).one()


def _order_subject(session, case):
    return [m for m in _mails_to(session, ADMIN) if case.case_reference in (m.subject or "")][-1].subject


def test_admin_can_fix_team_type_and_priority_and_it_is_recorded(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "IT", "it-helpdesk@acme-real.com")
    case = _case(session, tid, "Projector not working")
    subject = _order_subject(session, case)

    res = _run(session, tid, _mail(session, tid, "change team to IT", sender=ADMIN, subject=f"Re: {subject}"))
    assert res["action"] == "rerouted"
    session.refresh(case)
    assert case.facts["department_override"] == "IT"
    assert _mails_to(session, "it-helpdesk@acme-real.com"), "the new team gets the work order"
    assert session.exec(select(ServiceTicket)).one().department_code == "IT"

    _run(session, tid, _mail(session, tid, "change priority to high", sender=ADMIN, subject=f"Re: {subject}"))
    _run(session, tid, _mail(session, tid, "change type to it_support", sender=ADMIN, subject=f"Re: {subject}"))
    session.refresh(case)
    assert case.priority == "HIGH" and case.facts["agent_category"] == "it_support"
    kinds = [c["kind"] for c in case.facts["corrections"]]
    assert kinds == ["rerouted", "priority_changed", "recategorised"]


def test_team_reply_follows_the_override(session: Session, env):
    tid = _tid(session)
    _set_dept_email(session, "IT", "it-helpdesk@acme-real.com")
    case = _case(session, tid, "Projector flickering")
    subject = _order_subject(session, case)
    _run(session, tid, _mail(session, tid, "change team to IT", sender=ADMIN, subject=f"Re: {subject}"))
    it_order = _mails_to(session, "it-helpdesk@acme-real.com")[-1]
    res = _run(session, tid, _mail(session, tid, "done, replaced the HDMI cable", sender="it-helpdesk@acme-real.com",
                                   subject=f"Re: {it_order.subject}"))
    assert res["action"] == "done"


def test_admin_answer_becomes_a_draft_the_ai_only_uses_after_approval(session: Session, env, client, auth_headers):
    tid = _tid(session)
    fake = FakeGemini(_decision(
        {"type": "question", "category": "general", "summary": "Gym timings", "answer_verified": False},
    ))
    _run(session, tid, _mail(session, tid, "what are the gym timings?"), fake)
    case = session.exec(select(Outcome)).one()
    order = [m for m in _mails_to(session, ADMIN) if case.case_reference in (m.subject or "")][-1]
    _run(session, tid, _mail(session, tid, "tell requester: the gym is open 7am to 10pm on weekdays",
                             sender=ADMIN, subject=f"Re: {order.subject}"))
    draft = session.exec(select(KnowledgeEntry).where(KnowledgeEntry.section == "draft")).one()
    assert draft.is_active is False and "7am to 10pm" in draft.content

    from app.agent.directory import knowledge_text

    assert "7am to 10pm" not in knowledge_text(session, tid), "drafts are not used until approved"
    summary = client.get("/api/v1/learning/summary", headers=auth_headers).json()
    assert any(d["entry_id"] == draft.entry_id for d in summary["knowledge_drafts"])
    assert client.post(f"/api/v1/learning/knowledge/{draft.entry_id}/approve", json={}, headers=auth_headers).status_code == 200
    session.expire_all()
    assert "7am to 10pm" in knowledge_text(session, tid)


def test_repeated_rerouting_becomes_a_one_click_rule(session: Session, env):
    tid = _tid(session)
    for n in (1, 2):
        case = _case(session, tid, f"Projector issue {n}", category="maintenance", thread=f"t-p{n}")
        subject = _order_subject(session, case)
        _run(session, tid, _mail(session, tid, "change team to IT", sender=ADMIN, subject=f"Re: {subject}"))
    suggestions = rule_suggestions(session, tid)
    route = next(s for s in suggestions if s["kind"] == "route")
    assert route["action"] == {"type": "route_category", "category": "maintenance", "department": "IT"}
    assert route["count"] == 2

    apply_route_rule(session, tid, "maintenance", "IT", ADMIN)
    session.commit()
    assert department_for(session, tid, "maintenance").code == "IT"
    facilities = session.exec(select(Department).where(Department.code == "FACILITIES")).one()
    assert "maintenance" not in facilities.categories


def test_accuracy_reflects_human_corrections(session: Session, env):
    tid = _tid(session)
    _case(session, tid, "Fan noisy", thread="t-a1")
    wrong = _case(session, tid, "Monitor broken", thread="t-a2")
    _run(session, tid, _mail(session, tid, "change type to it_support", sender=ADMIN,
                             subject=f"Re: {_order_subject(session, wrong)}"))
    acc = accuracy_summary(session, tid)
    assert acc["overall"]["cases"] == 2
    assert acc["overall"]["type_accuracy_pct"] == 50
    assert acc["correction_trend"][0]["kind"] == "recategorised"


def test_regression_check_runs_without_side_effects(session: Session, env):
    tid = _tid(session)
    result = run_eval(session, tid)
    assert result["total"] >= len(GOLDEN) and result["mode"] == "rules"
    assert result["by_check"]["type"]["total"] == len(GOLDEN)
    assert session.exec(select(Outcome)).all() == [], "evaluation never creates cases"
    assert _mails_to(session, REQ) == []


def test_regression_check_scores_the_model_answers(session: Session, env):
    tid = _tid(session)

    class Perfect:
        def generate_json(self, *, system_instruction, payload, temperature=0.2):
            text = payload["this_message"]
            for subject, body, expect in GOLDEN:
                if body == text:
                    cat = expect["category"]
                    cat = cat[0] if isinstance(cat, tuple) else cat
                    return {"intents": [{"type": "new_request", "category": cat, "summary": subject,
                                         "priority": (expect.get("priority") if isinstance(expect.get("priority"), str)
                                                      else (expect.get("priority") or ("MEDIUM",))[0]),
                                         "needs_admin_decision": bool(expect.get("approval"))}],
                            "confidence": 0.9}, {"label": "fake"}
            return {"intents": [{"type": "new_request", "category": "general"}], "confidence": 0.9}, {"label": "fake"}

    result = run_eval(session, tid, provider=Perfect())
    assert result["mode"] == "gemini"
    assert result["by_check"]["type"]["pct"] == 100


def test_learning_endpoints(client, session: Session, env, auth_headers):
    body = client.get("/api/v1/learning/summary", headers=auth_headers).json()
    assert {"accuracy", "suggestions", "automation", "knowledge_drafts", "last_eval", "prompt_version"} <= set(body)
    run = client.post("/api/v1/learning/eval/run", headers=auth_headers)
    assert run.status_code == 200
    assert client.get("/api/v1/learning/summary", headers=auth_headers).json()["last_eval"]["total"] == run.json()["total"]
