"""Copy people from the Darwinbox file and stock from the stock file into the desk.

Each source has its own sqlite database. Nothing is written back to those files.
An office code that the desk does not already have is reported and skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session, select

from app.agent.importer import _import_employees, _import_stock
from app.models.org import Person, StockSku

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def sync_darwinbox(session: Session, tenant_id: str, *, db_path: Optional[Path] = None) -> dict[str, Any]:
    from integrations.darwinbox.source import list_employees

    created = updated = deactivated = 0
    errors: list[str] = []
    for row in list_employees(db_path):
        email = (row.get("email") or "").strip().lower()
        if not email or not (row.get("name") or "").strip():
            errors.append(f"skipped a Darwinbox row with no name or email ({row.get('employee_code') or 'no code'})")
            continue
        payload = {
            "email": email,
            "name": row.get("name") or "",
            "department": row.get("department") or "",
            "role": row.get("role") or "EMPLOYEE",
            "manager_email": row.get("manager_email") or "",
            "location": row.get("office_code") or "",
        }
        try:
            action, _ = _import_employees(session, tenant_id, payload, apply=True)
        except ValueError as exc:
            errors.append(f"{email}: {exc}")
            continue
        if action == "new":
            created += 1
        else:
            updated += 1
        if not int(row.get("active") if row.get("active") is not None else 1):
            person = session.exec(select(Person).where(Person.tenant_id == tenant_id, Person.email == email)).first()
            if person is not None and person.is_active:
                person.is_active = False
                session.add(person)
                deactivated += 1
    session.flush()
    return {
        "source": "darwinbox",
        "created": created,
        "updated": updated,
        "deactivated": deactivated,
        "errors": errors,
    }


def sync_stock(session: Session, tenant_id: str, *, db_path: Optional[Path] = None) -> dict[str, Any]:
    from integrations.stock.source import list_items

    created = updated = 0
    errors: list[str] = []
    for row in list_items(db_path):
        code = (row.get("sku_code") or "").strip()
        name = (row.get("name") or "").strip()
        if not code or not name:
            errors.append("skipped a stock row with no sku or name")
            continue
        payload = {
            "sku_code": code,
            "name": name,
            "location": row.get("office_code") or "",
            "qty_on_hand": row.get("qty_on_hand"),
            "reorder_min": row.get("reorder_min"),
            "reorder_qty": row.get("reorder_qty"),
            "unit": row.get("unit") or "each",
            "vendor_email": row.get("vendor_email") or "",
        }
        try:
            action, _ = _import_stock(session, tenant_id, payload, apply=True)
        except ValueError as exc:
            errors.append(f"{code}: {exc}")
            continue
        if action == "new":
            created += 1
        else:
            updated += 1
        expires = (row.get("expires_on") or "").strip()
        if expires:
            sku = session.exec(
                select(StockSku).where(StockSku.tenant_id == tenant_id, StockSku.sku_code == code.upper())
            ).first()
            if sku is not None:
                sku.expires_on = expires[:10]
                session.add(sku)
    session.flush()
    return {"source": "stock", "created": created, "updated": updated, "errors": errors}
