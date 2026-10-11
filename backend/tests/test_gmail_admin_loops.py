"""Closed-loop Gmail admin: department autocode, stock reorder, flight options."""

from __future__ import annotations

from sqlmodel import Session, select

from app.agent.importer import _autocode_department, _import_departments
from app.models.org import Location, StockSku, Tenant, Vendor
from app.services.communication import CommunicationService
from app.services.flight_search import (
    format_flight_options_for_mail,
    search_flights,
    wants_flight,
)
from app.services.stock import issue_and_maybe_reorder, low_stock_for_vendor, parse_qty


def test_wants_flight_detects_travel_asks():
    assert wants_flight("please arrange a flight Delhi to Bangalore next Monday")
    assert wants_flight("need air tickets for the client visit")
    assert not wants_flight("need a cab to the airport at 6am")


def test_search_flights_always_returns_compare_links(monkeypatch):
    monkeypatch.setattr(
        "app.services.flight_search._duckduckgo_snippets",
        lambda q, limit=6: [
            "IndiGo nonstop Delhi to Bangalore from ₹4,299 — book online",
            "Air India one-way DEL-BLR fares from INR 5,100",
        ],
    )
    opts = search_flights("Delhi", "Bangalore", "2026-10-20")
    assert len(opts) >= 3
    assert any(o.airline and "IndiGo" in o.airline for o in opts)
    assert any(o.source == "google_flights" for o in opts)
    mail = format_flight_options_for_mail(opts)
    assert "Flight options I found" in mail
    assert "google.com/travel/flights" in mail


def test_department_autocode_from_name_and_place(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    place = Location(tenant_id=tid, type="BRANCH", name="Pune HQ", alias="PUN-HQ", code="PUN-HQ")
    session.add(place)
    session.commit()
    assert _autocode_department("Facilities Team", place) == "FACILITIES_PUN_HQ"
    action, label = _import_departments(
        session,
        tid,
        {
            "name": "Facilities - Pune",
            "categories": "maintenance; hvac",
            "primary_email": "facilities.pune@yourco.com",
            "location": "PUN-HQ",
        },
        apply=True,
    )
    session.commit()
    assert action == "new"
    assert label.startswith("FACILITIES_PUN_HQ")


def test_plus_tag_team_email_rejected(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    try:
        _import_departments(
            session,
            tid,
            {
                "code": "FAC_TEST",
                "name": "Facilities Test",
                "primary_email": "desk+facilities@yourco.com",
            },
            apply=False,
        )
        assert False, "expected ValueError for +tag mailbox"
    except ValueError as exc:
        assert "normal mailbox" in str(exc).lower() or "+tag" in str(exc).lower()


def test_stock_below_min_opens_bulk_reorder(session: Session):
    tid = session.exec(select(Tenant)).first().tenant_id
    vendor = Vendor(
        tenant_id=tid,
        name="OfficeMart",
        category="supplies",
        contact_email="orders@officemart.test",
    )
    session.add(vendor)
    session.flush()
    stapler = StockSku(
        tenant_id=tid,
        sku_code="STAPLER",
        name="Stapler",
        qty_on_hand=5,
        reorder_min=4,
        reorder_qty=24,
        vendor_id=vendor.vendor_id,
    )
    pens = StockSku(
        tenant_id=tid,
        sku_code="PEN_BOX",
        name="Pen box",
        qty_on_hand=2,
        reorder_min=3,
        reorder_qty=10,
        vendor_id=vendor.vendor_id,
    )
    session.add(stapler)
    session.add(pens)
    session.commit()

    comms = CommunicationService(session, tid, email_sender=None)
    result = issue_and_maybe_reorder(
        session,
        tid,
        text="please issue 2 staplers for the sales bay",
        location_id=None,
        trigger_outcome=None,
        comms=comms,
    )
    session.commit()
    assert result["issued"] is True
    assert result["qty_on_hand"] == 3
    assert result.get("reorder_case")
    low = low_stock_for_vendor(session, tid, location_id=None, vendor_id=vendor.vendor_id)
    assert {s.sku_code for s in low} >= {"STAPLER", "PEN_BOX"}


def test_parse_qty():
    assert parse_qty("need 3 staplers") == 3.0
    assert parse_qty("stapler please") == 1.0
