"""Import a multi-sheet company Excel into the live DB (skips the slow Render preview).

    python -m scripts.import_company_xlsx path/to/file.xlsx
    python -m scripts.import_company_xlsx path/to/file.xlsx --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select  # noqa: E402

from app import models  # noqa: E402,F401
from app.agent.importer import prepare_company_import, run_bundle_import  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.models.org import Tenant  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="company .xlsx path")
    parser.add_argument("--dry-run", action="store_true", help="validate only (rollback)")
    args = parser.parse_args()
    path: Path = args.path
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")

    import app.core.database as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    print(f"Database: {get_settings().database_url.split('@')[-1]}")
    content = path.read_bytes()
    bundles, source = prepare_company_import(path.name, content)
    print(f"Source: {source}")
    for kind, rows in bundles.items():
        print(f"  {kind}: {len(rows)} rows")

    eng = dbmod.get_engine()
    with Session(eng) as session:
        tenant = session.exec(select(Tenant)).first()
        if tenant is None:
            raise SystemExit("No tenant — run bootstrap_empty_company first")
        print(f"Tenant: {tenant.tenant_id} ({tenant.name})")
        # Drop leftover locks from a hung Render preview (best-effort).
        try:
            from sqlalchemy import text

            session.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                 "WHERE datname = current_database() "
                                 "AND pid <> pg_backend_pid() "
                                 "AND state = 'idle in transaction' "
                                 "AND query_start < now() - interval '30 seconds'"))
            session.commit()
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            print(f"(could not clear idle transactions: {exc})")

        result = run_bundle_import(
            session, tenant.tenant_id, bundles, commit=not args.dry_run, source=source
        )
        print(
            f"\nDone: committed={result['committed']} new={result['new']} "
            f"updated={result['updated']} errors={len(result['errors'])} total={result['total']}"
        )
        for err in (result["errors"] or [])[:30]:
            print(f"  ERR {err.get('kind')} row {err.get('row')}: {err.get('error')}")
        if len(result["errors"] or []) > 30:
            print(f"  ... and {len(result['errors']) - 30} more")


if __name__ == "__main__":
    main()
