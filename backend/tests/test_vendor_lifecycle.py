"""Vendor lifecycle: invite → register → score → activate; desk only sees ACTIVE."""

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.agent.resolution_tools import list_approved_vendors
from app.models.org import Tenant, Vendor, utcnow
from app.models.ops_ledger import OpsLedgerEvent
from app.services import vendor_lifecycle as vl
from app.services.ops_ledger import record


def _tid(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def test_invite_register_score_activate_flow(session: Session):
    tid = _tid(session)
    vendor = vl.invite_vendor(
        session,
        tid,
        name="CoolAir HVAC",
        contact_email="cool@vendor.test",
        category="hvac",
        invited_by="admin@prototype.local",
        service_areas=["Pune"],
    )
    session.commit()
    assert vendor.status == "INVITED"
    assert vendor.invite_token
    token = vendor.invite_token

    registered = vl.register_by_token(
        session,
        token,
        {
            "legal_name": "CoolAir Pvt Ltd",
            "gstin": "27AAAAA0000A1Z5",
            "pan": "AAAAA0000A",
            "contact_name": "Ravi",
            "documents": {"gst_certificate": True, "pan_card": True, "insurance_policy": True},
            "compliance": {
                "years_in_business": 8,
                "employee_count": 40,
                "annual_turnover": "2cr",
                "background_verification": "yes",
                "data_privacy_policy": "yes",
            },
            "financial": {"annual_turnover": "2cr", "credit_rating": "A", "payment_terms": "30d", "gst_compliant": True},
            "manpower": {"permanent_employees": 40},
            "coverage_states": ["Maharashtra"],
            "coverage_cities": ["Pune", "Mumbai"],
            "coverage_rows": [{"state": "Maharashtra", "city": "Pune", "team_count": 12}],
            "approved_services": ["hvac", "ac amc"],
        },
    )
    session.commit()
    assert registered.status == "UNDER_REVIEW"
    assert registered.score is not None
    assert registered.vendor_tier in {"PREFERRED", "APPROVED", "CONDITIONAL"}

    # Token consumed path still has token until activate clears it
    active = vl.activate_vendor(session, tid, registered.vendor_id, actor_email="admin@prototype.local")
    session.commit()
    assert active.status == "ACTIVE"
    assert active.contract_id

    approved = list_approved_vendors(session, tid, category="hvac")
    assert any(a["vendor_id"] == active.vendor_id for a in approved)
    assert approved[0]["vendor_id"] == active.vendor_id or any(
        a.get("score") for a in approved if a["vendor_id"] == active.vendor_id
    )


def test_expired_token_rejected(session: Session):
    tid = _tid(session)
    vendor = vl.invite_vendor(
        session, tid, name="Old Co", contact_email="old@vendor.test", category="maintenance", invited_by="admin@prototype.local"
    )
    vendor.invite_expires_at = utcnow() - timedelta(days=1)
    session.add(vendor)
    session.commit()
    with pytest.raises(ValueError, match="expired"):
        vl.register_by_token(session, vendor.invite_token, {"legal_name": "Old"})


def test_suspended_excluded_from_desk_tools(session: Session):
    tid = _tid(session)
    vendor = vl.invite_vendor(
        session, tid, name="TempFix", contact_email="temp@vendor.test", category="hvac", invited_by="admin@prototype.local"
    )
    vl.activate_vendor(session, tid, vendor.vendor_id, actor_email="admin@prototype.local", create_contract=False)
    vl.suspend_vendor(session, tid, vendor.vendor_id, reason="SLA misses", actor_email="admin@prototype.local")
    session.commit()
    approved = list_approved_vendors(session, tid, category="hvac")
    assert all(a["vendor_id"] != vendor.vendor_id for a in approved)


def test_scorecard_ledger_backed(session: Session):
    tid = _tid(session)
    vendor = vl.invite_vendor(
        session, tid, name="LedgerCo", contact_email="ledger@vendor.test", category="hvac", invited_by="admin@prototype.local"
    )
    vl.activate_vendor(session, tid, vendor.vendor_id, actor_email="admin@prototype.local", create_contract=False)
    record(
        session,
        tid,
        event_type="SPEND_RECORDED",
        summary=f"Parts via {vendor.name}",
        category="hvac",
        amount=5000,
        actor_role="team",
        payload={"vendor_id": vendor.vendor_id},
    )
    session.commit()
    card = vl.performance_scorecard(session, tid, vendor.vendor_id, days=30)
    assert card["spend_recorded"] >= 5000
    assert card["score"] == vendor.score or card["score"] is not None


def test_invite_activate_suspend_ledger_events(session: Session):
    tid = _tid(session)
    vendor = vl.invite_vendor(
        session,
        tid,
        name="EventCo",
        contact_email="event@vendor.test",
        category="plumbing",
        invited_by="admin@prototype.local",
    )
    vl.activate_vendor(session, tid, vendor.vendor_id, actor_email="admin@prototype.local", create_contract=False)
    vl.suspend_vendor(session, tid, vendor.vendor_id, reason="quality", actor_email="admin@prototype.local")
    session.commit()
    types = [
        r.event_type
        for r in session.exec(select(OpsLedgerEvent).where(OpsLedgerEvent.tenant_id == tid)).all()
    ]
    assert "VENDOR_INVITED" in types
    assert "VENDOR_ACTIVATED" in types
    assert "VENDOR_SUSPENDED" in types
