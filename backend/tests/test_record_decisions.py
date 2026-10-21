"""Record-based decisions: warranty, AMC, repair count, repeats, stock, issued kit."""

from types import SimpleNamespace

from sqlmodel import select

from app.models.org import Asset, BusinessRule, Location, StockSku, Tenant
from app.services.ops_ledger import record
from app.services.record_decisions import decide_for_case


def _case(session, **facts):
    tid = session.exec(select(Tenant)).first().tenant_id
    return tid, SimpleNamespace(
        outcome_id="out_test",
        title=facts.pop("title", "Please fix it"),
        requester_email=facts.pop("requester_email", "person@example.com"),
        facts=facts,
    )


def test_ac_in_room_4_uses_that_units_warranty(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    site = Location(tenant_id=tid, type="BRANCH", name="Whitefield")
    session.add(site)
    session.commit()
    session.add(
        Asset(
            tenant_id=tid,
            type="HVAC",
            name="AC room 4",
            tag="AC-R4",
            location_id=site.location_id,
            attributes={"room": "4", "warranty_end": "2027-06-01"},
        )
    )
    session.commit()
    _, case = _case(
        session,
        title="Please fix the AC in room 4",
        agent_category="hvac",
        location_id=site.location_id,
        details={"location": "room 4"},
    )
    decision = decide_for_case(session, tid, case)
    assert decision["action"] == "WARRANTY_REPAIR"
    assert decision["asset_tag"] == "AC-R4"
    assert "2027-06-01" in decision["summary"]
    assert decision["repair_count"] == 0


def test_fan_repaired_past_the_company_limit_is_a_replacement(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    site = Location(tenant_id=tid, type="BRANCH", name="Whitefield")
    session.add(site)
    session.commit()
    session.add(
        BusinessRule(
            tenant_id=tid,
            code="RECORD_LIMITS",
            category="assets",
            description="Company repair limits",
            config={"replace_after": {"electrical": 50}},
        )
    )
    session.add(
        Asset(
            tenant_id=tid,
            type="ELECTRICAL",
            name="Fan room 4",
            tag="FAN-R4",
            location_id=site.location_id,
            attributes={"room": "4", "warranty_end": "2020-01-01"},
        )
    )
    session.commit()
    for n in range(50):
        record(
            session,
            tid,
            event_type="TEAM_DONE",
            summary=f"Fan repaired #{n}",
            location_id=site.location_id,
            category="electrical",
            asset_tag="FAN-R4",
            outcome_id=f"old_{n}",
        )
    session.commit()
    _, case = _case(
        session,
        title="Please fix the fan in room 4",
        agent_category="electrical",
        location_id=site.location_id,
        details={"location": "room 4"},
    )
    decision = decide_for_case(session, tid, case)
    assert decision["action"] == "REPLACE"
    assert decision["repair_count"] == 50
    assert decision["limit"] == 50
    assert "not another repair" in decision["summary"]


def test_unknown_room_does_not_invent_a_repair_count(session):
    tid, case = _case(session, title="AC is warm", agent_category="hvac", details={})
    decision = decide_for_case(session, tid, case)
    assert decision["action"] == "REPAIR_UNKNOWN"
    assert "repair_count" not in decision or decision["repair_count"] is None
    assert "not applied" in decision["summary"]


def test_repeat_housekeeping_escalates(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    site = Location(tenant_id=tid, type="BRANCH", name="Whitefield")
    session.add(site)
    session.commit()
    for n in range(4):
        record(
            session,
            tid,
            event_type="TEAM_DONE",
            summary="Cleaned washroom room 2",
            location_id=site.location_id,
            category="housekeeping",
            outcome_id=f"hk_{n}",
        )
    session.commit()
    _, case = _case(
        session,
        title="Please clean room 2 again",
        agent_category="housekeeping",
        location_id=site.location_id,
    )
    decision = decide_for_case(session, tid, case)
    assert decision["action"] == "ESCALATE"
    assert decision["repair_count"] == 4


def test_second_laptop_needs_approval(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    session.add(
        Asset(
            tenant_id=tid,
            type="LAPTOP",
            name="Existing laptop",
            tag="LT-1",
            assignee_email="person@example.com",
            status="ACTIVE",
        )
    )
    session.commit()
    _, case = _case(session, title="Need another laptop", agent_category="laptop")
    decision = decide_for_case(session, tid, case)
    assert decision["action"] == "NEEDS_APPROVAL"
    assert "already" in decision["summary"]


def test_expired_stock_is_not_issued(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    site = Location(tenant_id=tid, type="BRANCH", name="Whitefield")
    session.add(site)
    session.commit()
    session.add(
        StockSku(
            tenant_id=tid,
            sku_code="TEA",
            name="Tea bags",
            location_id=site.location_id,
            qty_on_hand=20,
            reorder_min=5,
            expires_on="2020-01-01",
        )
    )
    session.commit()
    _, case = _case(
        session,
        title="Need tea bags",
        agent_category="supplies",
        location_id=site.location_id,
    )
    decision = decide_for_case(session, tid, case)
    assert decision["action"] == "EXPIRED"
    assert "expiry" in decision["summary"].lower()
