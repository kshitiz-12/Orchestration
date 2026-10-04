"""Database tool for the current DATABASE_URL.

    python -m scripts.db status    which database, migration revision, and what is missing vs the models
    python -m scripts.db check     same, but exits 1 if anything is missing (for CI / pre-deploy)
    python -m scripts.db upgrade   apply migrations to head (creates/updates the schema; additive only)
"""

from __future__ import annotations

import sys
from urllib.parse import urlparse

from app.core.config import get_settings


def _where() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return f"SQLite ({url.split('///', 1)[-1] or 'memory'})"
    parsed = urlparse(url)
    return f"Postgres {parsed.hostname}:{parsed.port or 5432}/{(parsed.path or '/').lstrip('/')}"


def _revisions(conn) -> tuple[str | None, str]:
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    from app.core.database import alembic_config

    current = MigrationContext.configure(conn).get_current_revision()
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    return current, head


def status(strict: bool = False) -> int:
    from app.core.database import check_database, get_engine
    from app.core.schema_sync import plan

    print(f"Database: {_where()}")
    check_database()
    with get_engine().connect() as conn:
        current, head = _revisions(conn)
        todo = plan(conn)
    print(f"Migration: {current or 'none (never migrated)'} / head {head}")
    lines = todo.describe()
    if not lines:
        print("Schema: up to date with the models")
    else:
        print("Schema differences:")
        for line in lines:
            print(f"  - {line}")
    behind = current != head or not todo.empty
    if behind:
        print("Run: python -m scripts.db upgrade")
    return 1 if strict and behind else 0


def upgrade() -> int:
    from app.core.database import check_database, run_migrations

    print(f"Database: {_where()}")
    check_database()
    run_migrations()
    return status()


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        return status()
    if cmd == "check":
        return status(strict=True)
    if cmd == "upgrade":
        return upgrade()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
