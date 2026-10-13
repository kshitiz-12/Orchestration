"""Facilities.docx coverage (excl. real-estate/lease + mobile/IoT)."""

from datetime import date, timedelta

from sqlmodel import Session, select

from app.engines.budget import BudgetEngine
from app.models.org import Asset, Budget, Location, StockSku, Tenant
from app.services.amc_contracts import AmcContractsService
from app.services.asset_lifecycle import AssetLifecycleService
from app.services.facilities_enterprise import FacilitiesEnterpriseService
from app.services.facilities_ops import FacilitiesOpsService
from app.models.org import Contract, Vendor


def _tenant(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def _location(session: Session, tenant_id: str) -> Location:
    loc = Location(tenant_id=tenant_id, type="BRANCH", name="Test Branch", code="TB1")
    session.add(loc)
    session.commit()
    session.refresh(loc)
    return loc


def test_location_profile_and_space_master(session: Session):
    tid = _tenant(session)
    loc = _location(session, tid)
    svc = FacilitiesEnterpriseService(session, tid)
    svc.upsert_location_profile(
        loc.location_id,
        address="1 MG Road",
        cost_centre="CC-FAC",
        owner_email="fac@example.com",
        criticality="HIGH",
        service_bundle=["HVAC", "SECURITY", "HK"],
    )
    c = svc.location_completeness(loc.location_id)
    assert c["complete"] is True
    # lease fields must not stick
    svc.upsert_location_profile(loc.location_id, extra={"lease_id": "L-1", "rent": 100})
    loc2 = session.get(Location, loc.location_id)
    assert "lease_id" not in (loc2.attributes or {})
    assert "rent" not in (loc2.attributes or {})

    space = svc.upsert_space(
        code="FL1-MR1",
        name="Board Room",
        space_type="ROOM",
        location_id=loc.location_id,
        room_type="MEETING",
        capacity_seats=12,
        amenities=["AV", "VC"],
        accessibility=["WHEELCHAIR"],
    )
    assert space.capacity_seats == 12
    assert len(svc.list_spaces(loc.location_id)) == 1


def test_service_catalogue_and_work_order(session: Session):
    tid = _tenant(session)
    svc = FacilitiesEnterpriseService(session, tid)
    item = svc.upsert_service_item(
        service_code="HVAC-BRKD",
        service_family="HVAC",
        service_item="Breakdown repair",
        sla_response_hours=2,
        sla_resolution_hours=24,
        fulfilment_checklist=["diagnose", "repair", "photo"],
        chargeback_rule_code="AREA-FAC",
        rate=500,
    )
    assert item.service_code == "HVAC-BRKD"
    assert len(svc.list_service_items(family="HVAC")) == 1

    asset = AssetLifecycleService(session, tid).register(type="HVAC", name="AHU-1", tag="TAG-AHU-1")
    wo = svc.create_work_order(
        title="AHU not cooling",
        priority="P2",
        asset_id=asset.asset_id,
        service_code="HVAC-BRKD",
        requester_email="user@example.com",
    )
    assert wo.status == "OPEN"
    assert wo.sla_resolve_at is not None
    wo2 = svc.create_work_order(
        title="AHU not cooling",
        asset_id=asset.asset_id,
        service_code="HVAC-BRKD",
    )
    assert wo2.duplicate_of == wo.work_order_id
    advanced = svc.advance_work_order(wo.work_order_id, "CLOSED", closure_code="RESOLVED", labour_hours=2.5)
    assert advanced.status == "CLOSED"
    assert advanced.closure_code == "RESOLVED"


def test_asset_completeness_and_amc_call(session: Session):
    tid = _tenant(session)
    asset = AssetLifecycleService(session, tid).register(type="HVAC", name="Chiller", tag="CH-1")
    loc = _location(session, tid)
    AssetLifecycleService(session, tid).reassign(asset.asset_id, location_id=loc.location_id)
    svc = FacilitiesEnterpriseService(session, tid)
    incomplete = svc.asset_completeness(asset.asset_id)
    assert incomplete["complete"] is False
    svc.enrich_asset(
        asset.asset_id,
        {
            "make": "Carrier",
            "model": "X1",
            "serial": "S1",
            "criticality": "CRITICAL",
            "commissioned_on": "2024-01-01",
            "warranty_end": "2027-01-01",
            "owner_email": "fac@example.com",
            "maintenance_category": "hvac",
        },
    )
    assert svc.asset_completeness(asset.asset_id)["complete"] is True

    vendor = Vendor(tenant_id=tid, name="AMC Co", category="hvac", contact_email="amc@example.com", status="ACTIVE")
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    contract = Contract(tenant_id=tid, vendor_id=vendor.vendor_id, name="HVAC AMC", status="ACTIVE")
    session.add(contract)
    session.commit()
    session.refresh(contract)
    AmcContractsService(session, tid).link_obligation(
        contract_id=contract.contract_id,
        title="Chiller AMC",
        asset_id=asset.asset_id,
        sla_hours=4,
    )
    called = svc.resolve_amc_vendor_call(category="hvac", asset_id=asset.asset_id)
    assert called["action"] == "VENDOR_CALLED"
    assert called["called"]["vendor_email"] == "amc@example.com"


def test_inventory_entitlement_cycle_expiry(session: Session):
    tid = _tenant(session)
    svc = FacilitiesEnterpriseService(session, tid)
    sku = svc.upsert_item_master(
        sku_code="A4-REAM",
        name="A4 Paper Ream",
        category="STATIONERY",
        qty_on_hand=100,
        reorder_min=20,
        safety_stock=10,
        max_stock=200,
        controlled_item=False,
        expires_on=(date.today() + timedelta(days=10)).isoformat(),
        batch_code="B1",
        gl_account="5100",
        chargeback_rule_code="HEADCOUNT",
    )
    svc.set_entitlement(sku_code="A4-REAM", monthly_qty=5, max_per_request=2, requires_approval_above=1)
    check = svc.check_issue_entitlement(sku_code="A4-REAM", qty=2)
    assert check["requires_approval"] is True
    blocked = svc.check_issue_entitlement(sku_code="A4-REAM", qty=5)
    assert blocked["ok"] is False
    cc = svc.record_cycle_count(sku_id=sku.sku_id, counted_qty=95, adjust=True)
    assert cc.variance == -5
    assert session.get(StockSku, sku.sku_id).qty_on_hand == 95
    exp = svc.expiring_batches(30)
    assert any(e["sku_code"] == "A4-REAM" for e in exp)


def test_budget_commit_accrual_transfer_chargeback(session: Session):
    tid = _tenant(session)
    b1 = Budget(
        tenant_id=tid,
        category="OPEX",
        period="2026-Q1",
        original_amount=10000,
        revised_amount=10000,
        status="ACTIVE",
        cost_centre="CC-A",
    )
    b2 = Budget(
        tenant_id=tid,
        category="OPEX",
        period="2026-Q1",
        original_amount=1000,
        revised_amount=1000,
        status="ACTIVE",
        cost_centre="CC-B",
    )
    session.add(b1)
    session.add(b2)
    session.commit()
    session.refresh(b1)
    session.refresh(b2)

    eng = BudgetEngine(session, tid)
    eng.reserve(amount=500, period="2026-Q1", category="OPEX", cost_centre="CC-A")
    eng.commit(amount=500, budget_id=b1.budget_id, from_reservation=True)
    session.refresh(b1)
    assert b1.committed_amount == 500
    assert b1.reserved_amount == 0
    eng.accrue(amount=200, budget_id=b1.budget_id)
    session.refresh(b1)
    assert b1.accrued_amount == 200
    eng.post_actual(amount=200, budget_id=b1.budget_id)
    session.refresh(b1)
    assert b1.actual_amount == 200
    assert b1.accrued_amount == 0

    xfer = eng.transfer(
        source_budget_id=b1.budget_id,
        dest_budget_id=b2.budget_id,
        amount=100,
        justification="Move contingency",
        approved_by="cfo@example.com",
    )
    assert xfer.status == "APPROVED"

    svc = FacilitiesEnterpriseService(session, tid)
    svc.upsert_chargeback_rule(
        code="AREA-FAC",
        name="Area allocation",
        method="AREA",
        allocations=[{"location_id": "L1", "weight": 60}, {"location_id": "L2", "weight": 40}],
    )
    alloc = svc.allocate_chargeback("AREA-FAC", 1000)
    assert alloc["net"] == 1000
    assert abs(alloc["lines"][0]["amount"] - 600) < 0.01


def test_compliance_bcp_incident_fanout_soft_ses(session: Session):
    tid = _tenant(session)
    loc = _location(session, tid)
    svc = FacilitiesEnterpriseService(session, tid)
    req = svc.upsert_compliance(
        requirement_code="FIRE-NOC",
        law_or_standard="State Fire NOC",
        location_ids=[loc.location_id],
        expiry_date=(date.today() + timedelta(days=5)).isoformat(),
        renewal_lead_days=30,
        owner_email="comp@example.com",
    )
    due = svc.compliance_due(30)
    assert any(r.requirement_id == req.requirement_id for r in due)

    plan = svc.upsert_bcp_plan(
        plan_type="FIRE",
        title="Fire evacuation",
        location_id=loc.location_id,
        contact_tree=[{"role": "Warden", "email": "w@example.com"}],
        assembly_points=["North Gate"],
        critical_spares=["extinguisher"],
    )
    drill = svc.record_drill(plan.plan_id, score=0.9, lessons=["stair congestion"])
    assert drill.status == "COMPLETED"

    svc.upsert_risk(title="Power single point", location_id=loc.location_id, inherent_score=8)
    svc.record_esg_metric(metric_type="ENERGY_KWH", period="2026-Q1", value=12000, location_id=loc.location_id)

    inc = FacilitiesOpsService(session, tid).raise_incident(
        incident_type="FIRE",
        title="Smoke in server room",
        severity="CRITICAL",
        location_id=loc.location_id,
    )
    assert inc.deterministic_urgent is True
    assert "EMERGENCY_SERVICES_DESK" in (inc.fanout_notified or [])

    sched = svc.create_soft_schedule(service_type="HOUSEKEEPING", frequency_days=1, location_id=loc.location_id)
    created = svc.generate_due_soft_rounds()
    assert any(c["schedule_id"] == sched.schedule_id for c in created)
    round_id = created[0]["round_id"]
    done = svc.complete_soft_round_with_ses(round_id, score=4.5, findings=[])
    assert done["status"] == "DONE"
    assert done["ses_id"]

    dash = svc.facilities_dashboard()
    assert "open_incidents" in dash
    assert dash["urgent_incidents"] >= 1


def test_pm_job_plan(session: Session):
    tid = _tenant(session)
    svc = FacilitiesEnterpriseService(session, tid)
    plan = svc.upsert_job_plan(
        code="HVAC-Q",
        title="Quarterly HVAC PM",
        asset_types=["HVAC"],
        tasks=["filter", "belts", "readings"],
        safety_permit="LOTO",
        competency="HVAC-TECH",
    )
    assert plan.code == "HVAC-Q"
    row = FacilitiesOpsService(session, tid).create_pm_schedule(
        title="AHU PM", frequency_days=90, checklist=plan.tasks
    )
    row.job_plan_id = plan.plan_id
    row.safety_permit_required = True
    session.add(row)
    session.commit()
    assert row.job_plan_id == plan.plan_id
