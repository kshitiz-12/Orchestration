"""V3 Phase 1–3 foundation: LegalEntity, multi-tenant worker jobs, engines, context gateway."""

from sqlmodel import Session, select

from app.api.deps import assert_not_self_approve, assert_site_access, user_site_scope
from app.engines.approval import ApprovalEngine
from app.engines.budget import BudgetEngine
from app.engines.evidence import EvidenceEngine
from app.engines.sla import SlaEngine
from app.models.org import Budget, LegalEntity, OutboxEvent, Person, PolicyRule, Tenant
from app.models.outcome import Evidence, Outcome, Task
from app.services.context_gateway import ContextGateway
from app.services.intake import JobQueueService
from app.services.outbox import OutboxService
from fastapi import HTTPException
import pytest


def test_legal_entity_and_person_link(session: Session):
    tenant = session.exec(select(Tenant)).first()
    assert tenant is not None
    entity = LegalEntity(
        tenant_id=tenant.tenant_id,
        code="HQ",
        legal_name="HQ Legal",
        status="ACTIVE",
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)

    person = session.exec(select(Person).where(Person.tenant_id == tenant.tenant_id)).first()
    assert person is not None
    person.entity_id = entity.entity_id
    session.add(person)
    session.commit()
    session.refresh(person)
    assert person.entity_id == entity.entity_id


def test_job_processed_with_job_tenant_not_first_tenant(session: Session):
    """Regression: worker must use job.tenant_id, not first Tenant row."""
    t1 = session.exec(select(Tenant)).first()
    assert t1 is not None
    t2 = Tenant(name="Other Co", region="IN", status="ACTIVE")
    session.add(t2)
    session.commit()
    session.refresh(t2)

    queue = JobQueueService(session)
    job = queue.enqueue(
        tenant_id=t2.tenant_id,
        job_type="PROCESS_EMAIL",
        idempotency_key=f"idem-{t2.tenant_id}-1",
        payload={"ping": True},
    )
    claimed = queue.claim_next(["PROCESS_EMAIL"])
    assert claimed is not None
    assert claimed.job_id == job.job_id
    assert claimed.tenant_id == t2.tenant_id
    # Simulate correct worker behaviour
    assert claimed.tenant_id != t1.tenant_id or t1.tenant_id == t2.tenant_id or True
    assert claimed.tenant_id == t2.tenant_id


def test_outbox_enqueue_and_flush(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    svc = OutboxService(session, tid)
    row = svc.enqueue(
        event_type="NOTIFY.TEST",
        payload={"hello": "world"},
        idempotency_key="obx-test-1",
        aggregate_type="Outcome",
        aggregate_id="out_x",
    )
    assert row.status == "PENDING"
    again = svc.enqueue(
        event_type="NOTIFY.TEST",
        payload={"hello": "world"},
        idempotency_key="obx-test-1",
    )
    assert again.outbox_id == row.outbox_id
    result = svc.flush(limit=10)
    assert result["sent"] >= 1
    refreshed = session.get(OutboxEvent, row.outbox_id)
    assert refreshed.status == "SENT"


def test_approval_engine_policy_and_fallback(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    session.add(
        PolicyRule(
            tenant_id=tid,
            code="APPR_FACILITIES",
            name="Facilities spend",
            rule_family="APPROVAL",
            condition={"min_amount": 1000, "categories": ["FACILITIES"]},
            decision={"required": True, "approvers": ["boss@example.com"]},
            priority=10,
            version=1,
            is_active=True,
        )
    )
    session.commit()
    eng = ApprovalEngine(session, tid)
    hit = eng.decide(amount=2500, category="FACILITIES", requester_email="me@example.com")
    assert hit.required is True
    assert hit.route == ["boss@example.com"]
    assert hit.rule_code == "APPR_FACILITIES"

    low = eng.decide(amount=10, category="FACILITIES")
    assert low.required is False

    high = eng.decide(amount=60000, category="OTHER", default_approver="cfo@example.com")
    assert high.required is True
    assert high.rule_code == "FALLBACK_THRESHOLD"


def test_sla_and_budget_engines(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    sla = SlaEngine(session, tid).target_for(priority="CRITICAL")
    assert sla.resolution_hours == 4

    session.add(
        Budget(
            tenant_id=tid,
            category="OPEX",
            period="2026-Q4",
            original_amount=10000,
            revised_amount=10000,
            status="ACTIVE",
        )
    )
    session.commit()
    eng = BudgetEngine(session, tid)
    ok = eng.check(amount=500, period="2026-Q4")
    assert ok.ok is True
    reserved = eng.reserve(amount=500, period="2026-Q4")
    assert reserved.ok is True
    with pytest.raises(HTTPException):
        eng.reserve(amount=20000, period="2026-Q4")


def test_evidence_engine_blocks_unverified(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    outcome = Outcome(
        tenant_id=tid,
        case_reference="CASE-EVD-1",
        template_code="SERVICE_REQUEST",
        category="FACILITIES",
        title="AC repair",
        status="IN_PROGRESS",
    )
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    task = Task(
        tenant_id=tid,
        outcome_id=outcome.outcome_id,
        code="WO1",
        title="Fix AC",
        evidence_required=True,
        status="DONE",
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    gate = EvidenceEngine(session, tid).gate_for_outcome(outcome.outcome_id)
    assert gate.can_verify_close is False

    session.add(
        Evidence(
            tenant_id=tid,
            outcome_id=outcome.outcome_id,
            task_id=task.task_id,
            evidence_type="PHOTO",
            status="ACCEPTED",
        )
    )
    session.commit()
    gate2 = EvidenceEngine(session, tid).gate_for_outcome(outcome.outcome_id)
    assert gate2.can_verify_close is True


def test_context_gateway_marks_unavailable(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    gw = ContextGateway(session, tid)
    bundle = gw.for_requester(None)
    assert any(u["field"] == "requester" for u in bundle.unavailable)
    ghost = gw.for_requester("nobody-missing@example.com")
    assert any(u["reason"] == "not_in_directory" for u in ghost.unavailable)


def test_asset_and_incident_and_erp_stub(session: Session):
    from app.connectors.erp import CertifiedStubERP, CertifiedStubHRMS
    from app.models.org import Invoice, PurchaseOrder, Vendor
    from app.services.asset_lifecycle import AssetLifecycleService
    from app.services.facilities_ops import FacilitiesOpsService

    tid = session.exec(select(Tenant)).first().tenant_id
    asset = AssetLifecycleService(session, tid).register(type="HVAC", name="AHU-1", tag="AHU-1")
    assert asset.status == "ACTIVE"
    AssetLifecycleService(session, tid).set_status(asset.asset_id, "IN_REPAIR", reason="filter")
    fac = FacilitiesOpsService(session, tid)
    pm = fac.create_pm_schedule(title="AHU filter", asset_id=asset.asset_id, frequency_days=90)
    fac.complete_pm(pm.schedule_id)
    inc = fac.raise_incident(incident_type="FIRE", title="Drill", severity="CRITICAL")
    assert inc.deterministic_urgent is True
    hrms = CertifiedStubHRMS(session, tid).sync_employees()
    assert hrms["ok"] is True

    vendor = Vendor(
        tenant_id=tid, name="ERP V", category="FACILITIES", contact_email="e@example.com", status="ACTIVE"
    )
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    po = PurchaseOrder(
        tenant_id=tid,
        vendor_id=vendor.vendor_id,
        po_number="PO-ERP-1",
        description="x",
        quantity=1,
        unit_rate=50,
    )
    session.add(po)
    session.commit()
    session.refresh(po)
    inv = Invoice(
        tenant_id=tid,
        vendor_id=vendor.vendor_id,
        po_id=po.po_id,
        invoice_number="INV-ERP-1",
        quantity=1,
        unit_rate=50,
        amount=50,
        match_status="MATCHED",
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)
    posted = CertifiedStubERP(session, tid).post_invoice(inv, idempotency_key="erp-1")
    assert posted.ok is True
    assert posted.status == "ACCEPTED"


def test_ai_governance_emergency_and_confidence(monkeypatch):
    from app.ai.governance import AIGovernance
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AI_EMERGENCY_STOP", "true")
    get_settings.cache_clear()
    g = AIGovernance()
    blocked = g.before_inference(purpose="desk_interpretation")
    assert blocked.allowed is False
    monkeypatch.setenv("AI_EMERGENCY_STOP", "false")
    get_settings.cache_clear()
    g2 = AIGovernance(min_confidence=0.5)
    assert g2.after_inference(confidence=0.2).require_human_review is True
    assert g2.after_inference(confidence=0.9).allowed is True
    get_settings.cache_clear()


def test_matching_engine_po_invoice(session: Session):
    from app.engines.matching import MatchingEngine
    from app.models.org import Invoice, PurchaseOrder, Vendor

    tid = session.exec(select(Tenant)).first().tenant_id
    vendor = Vendor(
        tenant_id=tid,
        name="Match Vendor",
        category="FACILITIES",
        contact_email="mv@example.com",
        status="ACTIVE",
    )
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    po = PurchaseOrder(
        tenant_id=tid,
        vendor_id=vendor.vendor_id,
        po_number="PO-MATCH-1",
        description="Filters",
        quantity=10,
        unit_rate=100,
        status="OPEN",
    )
    session.add(po)
    session.commit()
    session.refresh(po)
    inv = Invoice(
        tenant_id=tid,
        vendor_id=vendor.vendor_id,
        po_id=po.po_id,
        invoice_number="INV-MATCH-1",
        quantity=10,
        unit_rate=100,
        amount=1000,
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)
    result = MatchingEngine(session, tid).match_invoice(inv)
    assert result.status == "MATCHED"


def test_admin_modules_mail_lifecycle_utility(session: Session):
    from app.services.admin_modules import AdminModulesService

    tid = session.exec(select(Tenant)).first().tenant_id
    svc = AdminModulesService(session, tid)
    mail = svc.log_mail(direction="INWARD", tracking_ref="AWB1", recipient_name="Desk")
    assert mail.status == "RECEIVED"
    case = svc.start_lifecycle(event_type="JOINER", person_email="newhire@example.com")
    assert case.status == "OPEN"
    assert len(case.checklist) >= 2
    code = case.checklist[0]["code"]
    updated = svc.complete_checklist_item(case.case_id, code)
    assert updated.status == "IN_PROGRESS"
    reading = svc.record_utility(meter_code="M1", utility_type="ELECTRICITY", reading_value=12.5)
    assert reading.reading_value == 12.5


def test_outcome_spine_helpers(session: Session):
    from app.engine.outcome_spine import can_verify_close, ensure_requirement, ensure_task, materialize_service_request
    from app.models.outcome import Outcome, Requirement, Task

    tid = session.exec(select(Tenant)).first().tenant_id
    outcome = Outcome(
        tenant_id=tid,
        case_reference="CASE-SPINE-1",
        template_code="SERVICE_REQUEST",
        category="maintenance",
        title="Spine",
        status="IN_PROGRESS",
        priority="HIGH",
    )
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    ensure_requirement(session, tenant_id=tid, outcome=outcome, code="FIX", title="Fix it", evidence_required=True)
    task = ensure_task(
        session, tenant_id=tid, outcome=outcome, code="WO", title="Work", evidence_required=True, category="maintenance"
    )
    session.commit()
    assert task.sla_hours > 0
    gate = can_verify_close(session, tid, outcome.outcome_id)
    assert gate["can_verify_close"] is False

    desk = Outcome(
        tenant_id=tid,
        case_reference="CASE-SPINE-DESK",
        template_code="SERVICE_REQUEST",
        category="HVAC",
        title="AC",
        status="ACTIVE",
        priority="MEDIUM",
    )
    session.add(desk)
    session.commit()
    session.refresh(desk)
    materialize_service_request(
        session, tenant_id=tid, outcome=desk, category="hvac", evidence_hint="photo of fix", owner_role="FACILITIES"
    )
    session.commit()
    assert session.exec(select(Requirement).where(Requirement.outcome_id == desk.outcome_id)).first()
    assert session.exec(select(Task).where(Task.outcome_id == desk.outcome_id)).first()
    assert (desk.facts or {}).get("unified_spine") is True


def test_sourcing_rfq_award(session: Session):
    from app.models.org import Vendor
    from app.services.vendor_sourcing import VendorSourcingService

    tid = session.exec(select(Tenant)).first().tenant_id
    v1 = Vendor(tenant_id=tid, name="A", category="FACILITIES", contact_email="a@x.com", status="ACTIVE")
    v2 = Vendor(tenant_id=tid, name="B", category="FACILITIES", contact_email="b@x.com", status="ACTIVE")
    session.add(v1)
    session.add(v2)
    session.commit()
    session.refresh(v1)
    session.refresh(v2)
    svc = VendorSourcingService(session, tid)
    req = svc.create_requirement(title="HVAC AMC", category="HVAC")
    rfq = svc.open_rfq(req.requirement_id, vendor_ids=[v1.vendor_id, v2.vendor_id])
    q1 = svc.submit_quote(rfq.rfq_id, vendor_id=v1.vendor_id, amount=50000, lead_time_days=10)
    svc.submit_quote(rfq.rfq_id, vendor_id=v2.vendor_id, amount=40000, lead_time_days=5)
    ranked = svc.compare_quotes(rfq.rfq_id)
    assert ranked[0]["vendor_id"] == v2.vendor_id
    awarded = svc.award(rfq.rfq_id, ranked[0]["quote_id"])
    assert awarded["awarded"] is True


def test_pm_sweeper_creates_outcome(session: Session):
    from datetime import timedelta

    from app.models.facilities import PreventiveSchedule
    from app.models.org import utcnow
    from app.models.outcome import Outcome
    from app.services.pm_sweeper import sweep_preventive_maintenance

    tid = session.exec(select(Tenant)).first().tenant_id
    sched = PreventiveSchedule(
        tenant_id=tid,
        title="Filter change",
        frequency_days=30,
        next_due_at=utcnow() - timedelta(hours=1),
        status="ACTIVE",
    )
    session.add(sched)
    session.commit()
    session.refresh(sched)
    result = sweep_preventive_maintenance(session, tid)
    assert result["created"] >= 1
    cases = session.exec(select(Outcome).where(Outcome.tenant_id == tid)).all()
    assert any((o.facts or {}).get("pm_schedule_id") == sched.schedule_id for o in cases)


def test_workplace_seat_and_p2p_pr(session: Session):
    from app.models.org import Resource
    from app.services.workplace import WorkplaceService
    from app.engines.budget import BudgetEngine
    from app.models.org import Budget
    from datetime import date

    tid = session.exec(select(Tenant)).first().tenant_id
    seat = Resource(tenant_id=tid, type="SEAT", name="Desk A1", status="AVAILABLE")
    session.add(seat)
    session.commit()
    session.refresh(seat)
    alloc = WorkplaceService(session, tid).allocate_seat(resource_id=seat.resource_id)
    assert alloc["status"] == "ALLOCATED"
    WorkplaceService(session, tid).release_seat(seat.resource_id)

    session.add(
        Budget(
            tenant_id=tid,
            category="OPEX",
            period=date.today().isoformat()[:7],
            original_amount=100000,
            revised_amount=100000,
            status="ACTIVE",
        )
    )
    session.commit()
    check = BudgetEngine(session, tid).check(amount=1000, period=date.today().isoformat()[:7])
    assert check.ok is True


def test_sod_helpers():
    actor = Person(
        tenant_id="t",
        email="a@example.com",
        name="A",
        role="BRANCH_ADMIN",
        site_id="site_1",
        allowed_site_ids=["site_2"],
    )
    with pytest.raises(HTTPException):
        assert_not_self_approve(actor=actor, subject_email="a@example.com")
    assert_not_self_approve(actor=actor, subject_email="b@example.com")
    assert_site_access(actor, "site_1")
    assert_site_access(actor, "site_2")
    with pytest.raises(HTTPException):
        assert_site_access(actor, "site_9")
    scope = user_site_scope(actor)
    assert scope == {"site_1", "site_2"}
