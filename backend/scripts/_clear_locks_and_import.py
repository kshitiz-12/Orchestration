"""Clear stuck transactions then import company xlsx."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlmodel import Session, select

from app import models  # noqa: F401
from app.agent.importer import prepare_company_import, run_bundle_import
from app.core.config import get_settings
from app.core.database import get_engine
from app.models.company import Department
from app.models.org import Location, Person, Tenant

XLSX = Path(r"c:\Users\adity\OneDrive\Desktop\orchestration\asteron_30_branches_1000_employees.xlsx")


def main() -> None:
    get_settings.cache_clear()
    eng = get_engine()
    with Session(eng) as s:
        rows = s.execute(
            text(
                "SELECT pid, state, wait_event_type, left(query, 80) AS q, "
                "now() - query_start AS age "
                "FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                "ORDER BY query_start NULLS LAST"
            )
        ).fetchall()
        print(f"other sessions: {len(rows)}")
        for r in rows:
            print(" ", r)
        killed = s.execute(
            text(
                "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                "AND usename = current_user "
                "AND (state ILIKE '%transaction%' OR wait_event_type = 'Lock' OR state = 'active')"
            )
        ).fetchall()
        s.commit()
        print("terminated same-role blockers:", killed)
        print(
            "counts before:",
            "loc",
            len(s.exec(select(Location)).all()),
            "dept",
            len(s.exec(select(Department)).all()),
            "people",
            len(s.exec(select(Person)).all()),
        )

    content = XLSX.read_bytes()
    bundles, source = prepare_company_import(XLSX.name, content)
    with Session(eng) as s:
        tenant = s.exec(select(Tenant)).first()
        assert tenant
        print(f"importing into {tenant.tenant_id}")
        result = run_bundle_import(s, tenant.tenant_id, bundles, commit=True, source=source)
        print(
            f"Done: new={result['new']} updated={result['updated']} "
            f"errors={len(result['errors'])} total={result['total']}"
        )
        for err in (result["errors"] or [])[:40]:
            print(f"  ERR {err.get('kind')} row {err.get('row')}: {err.get('error')}")


if __name__ == "__main__":
    main()
