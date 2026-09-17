"""Phases 3–5: policy, alternatives, SLA, pattern, eval harness."""

from datetime import timedelta

from app.engine.outcome_pattern import GenericStage, apply_generic_snapshot, derive_generic_stage
from app.evals.harness import run_eval
from app.policy.meeting_policy import (
    POLICY_VERSION,
    active_modules,
    build_no_resource_alternatives,
    default_meeting_policy,
)
from app.services.meeting_room import buffer_minutes, is_low_risk_auto_bookable


def test_versioned_policy_buffers_and_auto_book():
    pol = default_meeting_policy()
    assert pol.version == POLICY_VERSION
    facts = {
        "meeting_type": "internal meeting",
        "attendees": 8,
        "recommended_room": {"score": 95},
        "hybrid_av": "no",
        "catering": "none",
        "external_visitors": 0,
    }
    assert is_low_risk_auto_bookable(facts, policy=pol) is True
    setup, release = buffer_minutes(facts, policy=pol)
    assert setup == pol.setup_buffer_internal_minutes
    assert release == pol.release_buffer_internal_minutes
    complex_facts = {**facts, "catering": "requested", "external_visitors": 2}
    s2, r2 = buffer_minutes(complex_facts, policy=pol)
    assert s2 == pol.setup_buffer_complex_minutes
    assert r2 == pol.release_buffer_complex_minutes


def test_no_resource_alternatives_structured():
    alts = build_no_resource_alternatives(
        {"attendees": 200, "date": "tomorrow", "preferred_time": "3pm"},
        max_capacity=40,
    )
    codes = {a["code"] for a in alts}
    assert "REDUCE_HEADCOUNT" in codes
    assert "DIFFERENT_TIME" in codes
    assert "LARGER_VENUE" in codes
    assert "SPLIT_ROOMS" in codes


def test_active_modules_selective():
    mods = active_modules(
        {
            "catering": "requested",
            "external_visitors": 2,
            "guest_vehicles": 0,
            "hybrid_av": "no",
            "presentation_display": "yes",
        }
    )
    assert mods["catering"] is True
    assert mods["visitors"] is True
    assert mods["parking"] is False
    assert mods["av"] is True


def test_generic_pattern_onboarding_shape():
    stage = derive_generic_stage(
        has_blocking_gaps=True,
        awaiting_approval=True,
        blocked=True,
        complete=False,
        closed=False,
    )
    assert stage == GenericStage.BLOCKED
    snap = apply_generic_snapshot(
        {},
        entities={"joiner_name": "Ada"},
        stage=stage.value,
        modules={"seating": True},
        missing=[{"field": "permanent_seat", "question": "Choose alternative", "blocking": True}],
        decision={"kind": "onboarding", "stage": stage.value},
    )
    assert snap["orchestration_stage"] == "BLOCKED"
    assert snap["modules_active"]["seating"] is True
    assert snap["decision_trace"][-1]["kind"] == "onboarding"
    assert snap["field_contract"]["missing"]


def test_golden_eval_pass_rate():
    report = run_eval(use_heuristic=True)
    assert report["total"] >= 3
    # Kapil + informal reply should pass; date_only and townhall are softer
    assert report["passed"] >= 2
    assert report["pass_rate"] >= 0.5
    by_id = {r["id"]: r for r in report["results"]}
    assert by_id["kapil_typo_disclaimer"]["passed"] is True
    assert by_id["informal_reply_completes"]["passed"] is True


def test_sla_tick_marks_overdue(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.models.org import utcnow
    from app.services import sla as sla_mod

    now = utcnow()
    task = SimpleNamespace(
        task_id="tsk_1",
        outcome_id="out_1",
        due_at=now - timedelta(hours=10),
        status="ASSIGNED",
        result={},
        tenant_id="ten_1",
    )
    outcome = SimpleNamespace(
        outcome_id="out_1",
        status="ACTIVE",
        facts={},
    )

    session = MagicMock()
    session.exec.return_value.all.return_value = [task]
    session.get.return_value = outcome

    monkeypatch.setattr(sla_mod, "load_meeting_policy", lambda *_a, **_k: default_meeting_policy())
    monkeypatch.setattr(sla_mod, "AuditService", lambda _s: MagicMock(record=MagicMock()))

    # Avoid SQLAlchemy flag_modified on SimpleNamespace
    import sqlalchemy.orm.attributes as attrs

    monkeypatch.setattr(attrs, "flag_modified", lambda *_a, **_k: None)

    result = sla_mod.tick_sla(session, "ten_1")
    assert result["overdue_tasks"] == 1
    assert result["escalated_tasks"] == 1
    assert task.result.get("sla_overdue") is True
    assert task.result.get("sla_escalated") is True
    assert outcome.status == "AT_RISK"
