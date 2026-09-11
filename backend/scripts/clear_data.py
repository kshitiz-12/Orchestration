"""Clear all prototype/dummy data from the configured database, then reseed baseline.

Does NOT reload the 30 demo emails. Login admin remains available after seed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel

# Ensure backend root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import get_engine, init_db
from app import models  # noqa: F401
from scripts.seed import seed


def clear_all() -> None:
    get_settings.cache_clear()
    import app.core.database as dbmod

    dbmod._engine = None
    settings = get_settings()
    engine = get_engine()

    print(f"Clearing database ({'sqlite' if settings.is_sqlite else 'postgres'})...")

    if settings.is_sqlite:
        SQLModel.metadata.drop_all(engine)
        db_path = Path("orchestration.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass
        dbmod._engine = None
    else:
        # Truncate every mapped table; CASCADE clears FK dependencies
        table_names = [t.name for t in SQLModel.metadata.sorted_tables]
        if not table_names:
            raise RuntimeError("No tables registered in metadata")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE TABLE "
                    + ", ".join(f'"{name}"' for name in table_names)
                    + " RESTART IDENTITY CASCADE"
                )
            )
        print(f"Truncated {len(table_names)} tables")

    dbmod._engine = None
    init_db()
    with Session(get_engine()) as session:
        tid = seed(session)
        print(f"Cleared. Baseline reseeded tenant_id={tid}")
        print("Admin: admin@prototype.local (password from ADMIN_PASSWORD)")
        print("No demo emails/outcomes loaded.")


if __name__ == "__main__":
    clear_all()
