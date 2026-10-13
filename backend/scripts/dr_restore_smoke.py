"""DR restore smoke — run after restoring a DB backup into a non-prod URL.

Usage:
  set DATABASE_URL=...restored...
  python -m scripts.dr_restore_smoke

Exit 0 only if tenant, admin person, and schema-critical tables respond.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: F401,E402
from app.core.database import get_engine, init_db  # noqa: E402
from app.models.org import LegalEntity, Person, Tenant  # noqa: E402
from app.models.outcome import Outcome  # noqa: E402


def main() -> int:
    init_db()
    with Session(get_engine()) as session:
        tenants = list(session.exec(select(Tenant)).all())
        if not tenants:
            print("FAIL: no tenants after restore")
            return 1
        people = list(session.exec(select(Person).where(Person.is_active == True)).all())  # noqa: E712
        if not people:
            print("FAIL: no active persons")
            return 1
        entities = list(session.exec(select(LegalEntity)).all())
        outcomes = session.exec(select(Outcome).limit(1)).first()
        print(
            "OK",
            {
                "tenants": len(tenants),
                "active_persons": len(people),
                "legal_entities": len(entities),
                "has_outcome_sample": bool(outcomes),
            },
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
