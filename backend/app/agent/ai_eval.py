"""Regression check for the AI admin (blueprint 18.2: measure before releasing a prompt / rule change).

Runs a fixed set of everyday office mails plus every verified past case through the current instructions and
the platform's own rules, and scores type, team, priority and approval. It only calls the model - nothing is
created, routed or emailed.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from sqlmodel import Session, select

from app.agent.directory import catalogue, department_for, knowledge_text
from app.agent.playbooks import assess_risk, has_playbook, normalize_category
from app.agent.priority import infer_priority
from app.ai.admin_agent import AGENT_INSTRUCTION, AdminAgent, build_agent_payload
from app.models.company import LearningRecord
from app.models.org import utcnow

# (subject, body, expected) - expected keys: category (str or tuple of acceptable), priority, approval
GOLDEN: list[tuple[str, str, dict[str, Any]]] = [
    ("AC", "bhai 4th floor AC kaam nahi kar raha, bahut garmi hai", {"category": "hvac"}),
    ("urgent", "socket near desk 22 is sparking and there is a burning smell", {"category": ("electrical", "health_safety"), "priority": "URGENT"}),
    ("lift", "lift stuck between 2nd and 3rd floor, two people inside", {"category": ("maintenance", "health_safety"), "priority": "URGENT"}),
    ("washroom", "2nd floor gents washroom very dirty, no soap", {"category": "housekeeping"}),
    ("rats", "saw rats near the pantry again", {"category": "pest_control"}),
    ("visitor", "Neha Kapoor from Deloitte visiting me tomorrow 11am", {"category": "visitor", "approval": False}),
    ("gate pass", "need a gate pass to send 3 old monitors to the vendor, they won't come back", {"category": "material_gate_pass", "approval": True}),
    ("courier", "please courier these documents to our Mumbai office today", {"category": "courier"}),
    ("cab", "need a cab from office to airport on friday 6am", {"category": "travel", "approval": False}),
    ("flight", "please book a flight Delhi to Bangalore for next Monday", {"category": "travel", "approval": True}),
    ("shuttle", "can I get added to the night drop route to Dwarka", {"category": "employee_transport"}),
    ("laptop", "my laptop won't turn on, have a client call in an hour", {"category": ("it_support", "laptop"), "priority": ("HIGH", "URGENT")}),
    ("access", "need access card for server room", {"category": "access_card", "approval": True}),
    ("stationery", "need 5 notebooks and a box of pens, no rush", {"category": "supplies", "priority": "LOW"}),
    ("joining", "Riya Sharma joins on 12 Oct in Gurugram, please arrange laptop, seat and access", {"category": "onboarding"}),
    ("seat", "please shift my seat closer to the finance team", {"category": "seating"}),
    ("catering", "lunch for 20 people on Monday for the client team", {"category": "catering", "approval": True}),
    ("weekend", "AC vendor needs weekend access to 3rd floor for servicing", {"category": ("hvac", "security", "maintenance"), "approval": True}),
]


def prompt_version() -> str:
    return hashlib.sha1(AGENT_INSTRUCTION.encode()).hexdigest()[:8]


def _cases(session: Session, tenant_id: str, limit: int) -> list[dict]:
    rows = [{"source": "golden", "subject": s, "text": b, "expect": e} for s, b, e in GOLDEN]
    history = session.exec(
        select(LearningRecord)
        .where(LearningRecord.tenant_id == tenant_id, LearningRecord.learning_eligible == True)  # noqa: E712
        .order_by(LearningRecord.created_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    for r in history:
        plan = r.final_plan or {}
        if not r.request_text:
            continue
        rows.append({
            "source": r.case_reference or "history",
            "subject": "",
            "text": r.request_text,
            "expect": {"category": plan.get("category") or r.category, "team": plan.get("department"),
                       "approval": plan.get("needed_approval")},
        })
    return rows


def _ok(expected: Any, actual: Any) -> bool:
    if isinstance(expected, (tuple, list)):
        return actual in expected
    return actual == expected


def run_eval(session: Session, tenant_id: str, *, provider: Any = None, history_limit: int = 20) -> dict:
    from app.ai.gemini import HeuristicProvider

    agent = AdminAgent(provider)
    knowledge = knowledge_text(session, tenant_id)
    teams = catalogue(session, tenant_id)
    results = []
    tallies: dict[str, list[int]] = {"type": [0, 0], "team": [0, 0], "priority": [0, 0], "approval": [0, 0]}
    source = "rules"
    for case in _cases(session, tenant_id, history_limit):
        payload = build_agent_payload(
            subject=case["subject"], this_message=case["text"], trail=[], cases=[], current_case=None,
            profile={"known_employee": True}, knowledge=knowledge, departments=teams, attachments=[],
        )
        hint: Optional[str] = None
        if not agent.can_reason:
            try:
                hint = HeuristicProvider().extract(subject=case["subject"], body=case["text"]).event_type
            except Exception:  # noqa: BLE001
                hint = None
        decision = agent.decide(payload, heuristic_hint=hint)
        source = decision.source.split(":")[0]
        intent = next((i for i in decision.intents if i.type in {"new_request", "update_case"}), decision.primary)
        category = normalize_category(intent.category if intent else "general")
        details = dict(intent.details) if intent else {}
        got = {
            "category": category,
            "team": getattr(department_for(session, tenant_id, category), "code", None),
            "priority": infer_priority(f"{intent.summary if intent else ''}\n{case['text']}\n{details}",
                                       intent.priority if intent else None).priority,
            "approval": assess_risk(
                category=category, text=f"{case['text']}\n{details}", details=details,
                agent_flag=bool(intent and intent.needs_admin_decision),
                agent_reason=intent.decision_reason if intent else "",
                confidence=decision.confidence, known=has_playbook(category),
            ).needs_admin,
        }
        exp = case["expect"]
        checks = {
            "type": ("category", exp.get("category")),
            "team": ("team", exp.get("team")),
            "priority": ("priority", exp.get("priority")),
            "approval": ("approval", exp.get("approval")),
        }
        failed = []
        for name, (key, want) in checks.items():
            if want is None:
                continue
            tallies[name][1] += 1
            if _ok(want, got[key]):
                tallies[name][0] += 1
            else:
                failed.append({"check": name, "expected": want if not isinstance(want, tuple) else list(want), "got": got[key]})
        results.append({"source": case["source"], "text": case["text"][:160], "got": got, "failed": failed})
    passed = sum(1 for r in results if not r["failed"])
    return {
        "ran_at": utcnow().isoformat(),
        "mode": source,
        "prompt_version": prompt_version(),
        "total": len(results),
        "passed": passed,
        "score_pct": round(100 * passed / len(results)) if results else None,
        "by_check": {k: {"passed": v[0], "total": v[1], "pct": round(100 * v[0] / v[1]) if v[1] else None}
                     for k, v in tallies.items()},
        "failures": [r for r in results if r["failed"]],
    }
