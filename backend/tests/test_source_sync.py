"""Darwinbox and stock each live in their own sqlite file. Sync copies them into the desk."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlmodel import select

from app.models.org import Location, Person, StockSku, Tenant
from app.services.source_sync import sync_darwinbox, sync_stock
from integrations.darwinbox.source import ensure_seeded as seed_darwinbox
from integrations.stock.source import ensure_seeded as seed_stock


def _offices(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    session.add(Location(tenant_id=tid, type="BRANCH", name="Whitefield", code="WF"))
    session.add(Location(tenant_id=tid, type="BRANCH", name="Pune Hq", code="PUN"))
    session.commit()
    return tid


def test_darwinbox_sync_puts_people_on_their_office_and_deactivates_leavers(session, tmp_path):
    tid = _offices(session)
    db = seed_darwinbox(tmp_path / "darwinbox.sqlite")
    result = sync_darwinbox(session, tid, db_path=db)
    session.commit()
    assert result["created"] == 3
    assert result["deactivated"] == 1
    assert result["errors"] == []
    wf = session.exec(select(Location).where(Location.code == "WF")).one()
    riya = session.exec(select(Person).where(Person.email == "riya.shah@example.com")).one()
    priya = session.exec(select(Person).where(Person.email == "priya.nair@example.com")).one()
    left = session.exec(select(Person).where(Person.email == "arun.left@example.com")).one()
    assert riya.site_id == wf.location_id
    assert riya.manager_id == priya.person_id
    assert priya.role == "BRANCH_ADMIN"
    assert left.is_active is False


def test_stock_sync_keeps_quantity_and_expiry_on_that_office(session, tmp_path):
    tid = _offices(session)
    db = seed_stock(tmp_path / "stock.sqlite")
    result = sync_stock(session, tid, db_path=db)
    session.commit()
    assert result["created"] == 2
    assert result["errors"] == []
    wf = session.exec(select(Location).where(Location.code == "WF")).one()
    tea = session.exec(select(StockSku).where(StockSku.sku_code == "TEA")).one()
    assert tea.location_id == wf.location_id
    assert tea.qty_on_hand == 20
    assert tea.expires_on == "2020-01-01"
    pun = session.exec(select(Location).where(Location.code == "PUN")).one()
    stapler = session.exec(select(StockSku).where(StockSku.sku_code == "STAPLER")).one()
    assert stapler.location_id == pun.location_id


def test_unknown_office_is_skipped_not_invented(session, tmp_path):
    tid = session.exec(select(Tenant)).first().tenant_id
    db = seed_darwinbox(tmp_path / "darwinbox.sqlite")
    result = sync_darwinbox(session, tid, db_path=db)
    session.commit()
    assert result["created"] == 0
    assert result["errors"]
    assert session.exec(select(Person).where(Person.email == "riya.shah@example.com")).first() is None
