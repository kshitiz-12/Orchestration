"""Enterprise V3 closers — gateway tools, commercial cost, contracts, ESG, learning, sealed RFQ."""

from sqlmodel import Session, select

from app.ai.governance import AIGovernance
from app.ai.service import LLMService
from app.models.company import LearningRecord
from app.models.org import Contract, Tenant, Vendor
from app.services.commercial_cost import CommercialCostService
from app.services.context_gateway import ContextGateway
from app.services.enterprise_v3 import EnterpriseV3Service
from app.services.outbox import OutboxService
from app.services.vendor_sourcing import VendorSourcingService
from app.models.outcome import Outcome


def _tid(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def test_context_gateway_tools(session: Session):
    tid = _tid(session)
    gw = ContextGateway(session, tid)
    bundle = gw.for_interpretation(requester_email="admin@prototype.local", category="maintenance")
    d = bundle.as_dict()
    assert "facts" in d and "unavailable" in d
    keys = {f["key"] for f in d["facts"]}
    assert "requester" in keys or any(u["field"] == "requester" for u in d["unavailable"])
    amc = gw.check_amc(category="hvac")
    assert amc.facts and amc.facts[0].key == "amc_coverage"
    assert "source_system" in amc.facts[0].as_dict()


def test_ai_governance_blocks_emergency(session: Session, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AI_EMERGENCY_STOP", "true")
    get_settings.cache_clear()
    gov = AIGovernance()
    v = gov.before_inference(purpose="desk_interpretation")
    assert v.allowed is False
    monkeypatch.setenv("AI_EMERGENCY_STOP", "false")
    get_settings.cache_clear()


def test_commercial_cost_reported_not_paid(session: Session):
    tid = _tid(session)
    outcome = Outcome(
        tenant_id=tid,
        case_reference="FAC-TEST-1",
        template_code="FACILITIES",
        category="MAINTENANCE",
        title="AC fix",
        status="IN_PROGRESS",
    )
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    svc = CommercialCostService(session, tid)
    row = svc.report_operational(outcome.outcome_id, 12500.0, actor="tech@x.com", note="done INR 12500")
    assert row.status == "REPORTED"
    assert row.reported_amount == 12500.0
    assert row.paid_amount == 0.0
    snap = svc.snapshot(outcome.outcome_id)
    assert snap["authoritative_finance"] is False
    assert snap["ops_reported_only"] is True


def test_contract_amend_and_terminate(session: Session):
    tid = _tid(session)
    v = Vendor(tenant_id=tid, name="HVAC Co", category="hvac", contact_email="v@x.com", status="ACTIVE")
    session.add(v)
    session.commit()
    session.refresh(v)
    c = Contract(tenant_id=tid, vendor_id=v.vendor_id, name="AMC", rate_card={"hourly": 500}, status="ACTIVE")
    session.add(c)
    session.commit()
    session.refresh(c)
    svc = EnterpriseV3Service(session, tid)
    am = svc.amend_contract(c.contract_id, change_summary="Rate uplift", rate_card_delta={"hourly": 550})
    assert am.version == 1
    session.refresh(c)
    assert c.rate_card["hourly"] == 550
    term = svc.terminate_contract(c.contract_id, reason="Non performance")
    assert term.status == "TERMINATED"


def test_vendor_workspace_and_sealed_rfq(session: Session):
    tid = _tid(session)
    v = Vendor(tenant_id=tid, name="Bid Co", category="hvac", contact_email="b@x.com", status="ACTIVE")
    session.add(v)
    session.commit()
    session.refresh(v)
    svc = EnterpriseV3Service(session, tid)
    item = svc.vendor_submit(v.vendor_id, item_type="QUOTE", title="Q1", amount=9000)
    assert item.status == "SUBMITTED"
    decided = svc.vendor_ws_decide(item.item_id, status="ACCEPTED")
    assert decided.status == "ACCEPTED"

    sourcing = VendorSourcingService(session, tid)
    req = sourcing.create_requirement(title="Chiller AMC", category="HVAC")
    rfq = sourcing.open_rfq(req.requirement_id, vendor_ids=[v.vendor_id], due_at="2099-01-01T00:00:00")
    sourcing.submit_quote(rfq.rfq_id, vendor_id=v.vendor_id, amount=10000, lead_time_days=7)
    sealed = svc.score_quotes_sealed(rfq.rfq_id, unseal=False)
    assert sealed["sealed"] is True
    open_score = svc.score_quotes_sealed(rfq.rfq_id, unseal=True)
    assert open_score["sealed"] is False
    assert open_score["items"]


def test_meter_rollover_carbon_waste(session: Session):
    tid = _tid(session)
    svc = EnterpriseV3Service(session, tid)
    r1 = svc.record_meter(meter_code="M1", utility_type="ENERGY", reading_value=100)
    assert r1.delta == 100
    r2 = svc.record_meter(meter_code="M1", utility_type="ENERGY", reading_value=50, max_dial=200)
    assert r2.rolled_over is True
    assert r2.delta > 0
    w = svc.log_waste(waste_type="E_WASTE", quantity_kg=12.5, manifest_no="WM-1")
    assert w.manifest_id
    c = svc.upsert_carbon(period="2026-Q1", scope="SCOPE2", tco2e=4.2)
    assert c.scope == "SCOPE2"


def test_governed_learning_requires_corrections(session: Session):
    tid = _tid(session)
    rec = LearningRecord(
        tenant_id=tid,
        category="MAINTENANCE",
        request_text="ac broken",
        ai_plan={"x": 1},
        corrections=[],
        verified=True,
        learning_eligible=False,
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)
    svc = EnterpriseV3Service(session, tid)
    try:
        svc.sign_off_learning(rec.record_id, signed_by="admin@prototype.local", decision="APPROVE")
        assert False, "should require corrections"
    except Exception as exc:  # noqa: BLE001
        assert "corrections" in str(exc).lower() or "409" in str(exc)
    rec.corrections = [{"field": "priority", "to": "P1"}]
    session.add(rec)
    session.commit()
    out = svc.sign_off_learning(rec.record_id, signed_by="admin@prototype.local", decision="APPROVE")
    assert out["learning_eligible"] is True


def test_outbox_dlq_requeue(session: Session):
    tid = _tid(session)
    obx = OutboxService(session, tid)
    row = obx.enqueue(
        event_type="NOTIFY.TEST",
        payload={"a": 1},
        idempotency_key="dlq-test-1",
    )
    row.status = "DEAD"
    row.attempts = 8
    row.last_error = "boom"
    session.add(row)
    session.commit()
    dead = obx.dead_letters()
    assert any(d.outbox_id == row.outbox_id for d in dead)
    again = obx.requeue_dead(row.outbox_id)
    assert again.status == "PENDING"
    assert again.attempts == 0
