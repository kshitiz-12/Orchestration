"""Finish Asteron import from employees onward (locations/teams already loaded)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlmodel import Session, select

from app import models  # noqa: F401
from app.agent.importer import IMPORT_ORDER, prepare_company_import, run_bundle_import
from app.core.config import get_settings
from app.core.database import get_engine
from app.models.company import CostCentre, Department, KnowledgeEntry, SiteService
from app.models.org import Location, Person, Resource, Tenant, Vendor

XLSX = Path(r"c:\Users\adity\OneDrive\Desktop\orchestration\asteron_30_branches_1000_employees.xlsx")


def counts(session: Session) -> dict[str, int]:
    return {
        "locations": len(session.exec(select(Location)).all()),
        "departments": len(session.exec(select(Department)).all()),
        "people": len(session.exec(select(Person)).all()),
        "resources": len(session.exec(select(Resource)).all()),
        "vendors": len(session.exec(select(Vendor)).all()),
        "knowledge": len(session.exec(select(KnowledgeEntry)).all()),
        "site_services": len(session.exec(select(SiteService)).all()),
        "cost_centres": len(session.exec(select(CostCentre)).all()),
    }


def main() -> None:
    get_settings.cache_clear()
    eng = get_engine()
    with Session(eng) as s:
        try:
            s.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND usename = current_user "
                    "AND (state ILIKE '%transaction%' OR wait_event_type = 'Lock')"
                )
            )
            s.commit()
        except Exception as exc:  # noqa: BLE001
            s.rollback()
            print("lock clear:", exc)
        print("before:", counts(s))

    bundles, source = prepare_company_import(XLSX.name, XLSX.read_bytes())
    # Skip sheets already loaded so we don't re-walk 53 locations slowly.
    for kind in ("locations", "departments"):
        bundles.pop(kind, None)
        print(f"skip {kind} (already loaded)")

    t0 = time.time()
    with Session(eng) as s:
        tenant = s.exec(select(Tenant)).first()
        assert tenant
        # Import remaining kinds one-by-one with progress prints.
        from app.agent.importer import _import_kind_rows, _invalidate_places_cache

        s.execute(text("SET LOCAL statement_timeout = '300s'"))
        total_new = total_upd = 0
        errors = []
        for kind in IMPORT_ORDER:
            rows = bundles.get(kind) or []
            if not rows:
                continue
            print(f"… {kind}: {len(rows)} rows", flush=True)
            part = _import_kind_rows(s, tenant.tenant_id, kind, rows, apply=True)
            s.commit()
            for attr in (
                "_import_places_cache",
                "_import_people_cache",
                "_import_depts_cache",
                "_import_resources_cache",
            ):
                if hasattr(s, attr):
                    delattr(s, attr)
            s.execute(text("SET LOCAL statement_timeout = '300s'"))
            total_new += part["new"]
            total_upd += part["updated"]
            errors.extend(part["errors"])
            print(
                f"  ok {kind}: new={part['new']} updated={part['updated']} "
                f"errors={len(part['errors'])} ({time.time() - t0:.1f}s)",
                flush=True,
            )
        print(f"\nDone in {time.time() - t0:.1f}s — new={total_new} updated={total_upd} errors={len(errors)}")
        for err in errors[:25]:
            print(" ERR", err)
        print("after:", counts(s))


if __name__ == "__main__":
    main()
