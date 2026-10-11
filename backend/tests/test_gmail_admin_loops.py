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


def test_search_flights_returns_structured_details_not_links(monkeypatch):
    from app.services.flight_search import FlightOption

    fake = [
        FlightOption(
            airline="IndiGo",
            flight_numbers="6E2041",
            depart_at="20 Oct 06:15",
            arrive_at="20 Oct 09:00",
            duration="2h 45m",
            stops="Non-stop",
            price="INR 4,299",
            origin="DEL",
            destination="BLR",
            source="amadeus",
        ),
        FlightOption(
            airline="Air India",
            flight_numbers="AI803 + AI505",
            depart_at="20 Oct 08:00",
            arrive_at="20 Oct 13:40",
            duration="5h 40m",
            stops="1 stop (BOM, 1h 10m)",
            price="INR 5,840",
            origin="DEL",
            destination="BLR",
            source="amadeus",
        ),
    ]
    monkeypatch.setattr("app.services.flight_search._serpapi_flights", lambda *a, **k: [])
    monkeypatch.setattr("app.services.flight_search._amadeus_flights", lambda *a, **k: fake)
    opts = search_flights("Delhi", "Bangalore", "2026-10-20")
    assert len(opts) == 2
    assert opts[0].price.startswith("INR")
    assert "Non-stop" in opts[0].stops
    assert "BOM" in opts[1].stops
    mail = format_flight_options_for_mail(opts)
    assert "Depart:" in mail and "Arrive:" in mail and "Fare:" in mail
    assert "http" not in mail.lower()
    assert "kayak" not in mail.lower()


def test_parse_travel_date_and_iata():
    from app.services.flight_search import parse_travel_date, resolve_iata
    from datetime import date

    assert resolve_iata("Bengaluru") == "BLR"
    assert resolve_iata("Delhi") == "DEL"
    assert resolve_iata("Ranchi hotel") == "IXR"
    assert parse_travel_date("20 Oct 2026") == "2026-10-20"
    assert parse_travel_date("2026-11-05") == "2026-11-05"
    assert parse_travel_date("next Monday", today=date(2026, 10, 11))  # Sunday → 12 Oct


def test_old_link_flight_options_are_not_usable():
    from app.services.flight_search import flight_options_are_usable

    assert not flight_options_are_usable(
        [{"summary": "Compare live fares", "url": "https://www.google.com/travel/flights", "source": "google_flights"}]
    )
    assert flight_options_are_usable(
        [{"airline": "IndiGo", "depart_at": "20 Oct 06:15", "price": "INR 4299", "flight_numbers": "6E1"}]
    )


def test_pick_realistic_fare_ignores_india_teaser_list_price():
    from app.services.flight_search import _pick_realistic_fare

    fare, note = _pick_realistic_fare(
        list_price=5499,
        booking_prices=[12490, 13200, 15800],
        typical_low=12000,
        typical_high=18000,
        domestic_in=True,
    )
    assert fare is not None and fare >= 12000
    assert "teaser" in note.lower() or "bookable" in note.lower()

    skipped, reason = _pick_realistic_fare(
        list_price=5499,
        booking_prices=[],
        typical_low=12000,
        typical_high=18000,
        domestic_in=True,
    )
    assert skipped is None
    assert reason == "below_market_teaser"



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
