"""Wipe the database and leave an empty company ready for Setup CSV/Excel import.

    python -m scripts.bootstrap_empty_company --wipe

Keeps: one tenant, dashboard login, meeting-room outcome template, department catalogue stubs.
Does not load: branches, employees, rooms, vendors, knowledge, or any demo / test-company data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402,F401
from app.agent.company_seed import ensure_company_seed  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.engine.meeting_scenario import ensure_meeting_room_template  # noqa: E402
from app.models.company import Department  # noqa: E402
from app.models.org import LegalEntity, Person, Tenant  # noqa: E402
from scripts.load_test_company import wipe  # noqa: E402

TENANT_NAME = "Company"
_WEAK_PASSWORDS = frozenset({"", "admin123", "password", "changeme", "change-me", "secret"})


def _admin_credentials() -> tuple[str, str]:
    """Login from ADMIN_EMAIL / ADMIN_PASSWORD. Production refuses default passwords."""
    settings = get_settings()
    email = (settings.admin_email or "").strip().lower() or "admin@prototype.local"
    password = (settings.admin_password or "").strip()
    if settings.is_production and password.lower() in _WEAK_PASSWORDS:
        raise RuntimeError(
            "ADMIN_PASSWORD must be set to a strong non-default value before bootstrapping in production."
        )
    if not password:
        password = "admin123"
    return email, password


def bootstrap_empty(session: Session) -> str:
    admin_email, admin_password = _admin_credentials()
    tenant = session.exec(select(Tenant)).first()
    if tenant is None:
        tenant = Tenant(name=TENANT_NAME, region="IN", status="ACTIVE")
        session.add(tenant)
        session.flush()
    else:
        tenant.name = TENANT_NAME
        session.add(tenant)

    tid = tenant.tenant_id
    entity = session.exec(
        select(LegalEntity).where(LegalEntity.tenant_id == tid, LegalEntity.code == "DEFAULT")
    ).first()
    if entity is None:
        entity = LegalEntity(
            tenant_id=tid,
            code="DEFAULT",
            legal_name=f"{TENANT_NAME} Legal Entity",
            country="IN",
            currency="INR",
            status="ACTIVE",
        )
        session.add(entity)
        session.flush()

    admin = session.exec(select(Person).where(Person.tenant_id == tid, Person.email == admin_email)).first()
    if admin is None:
        admin = Person(
            tenant_id=tid,
            entity_id=entity.entity_id,
            email=admin_email,
            name="Company Admin",
            role="OPERATOR",
            department="Operations",
            is_active=True,
        )
    admin.entity_id = admin.entity_id or entity.entity_id
    admin.password_hash = hash_password(admin_password)
    admin.is_active = True
    session.add(admin)

    ensure_meeting_room_template(session, tid)
    ensure_company_seed(session, tid)
    session.commit()
    return tid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="delete ALL rows first")
    args = parser.parse_args()

    import app.core.database as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    print(f"Database: {get_settings().database_url.split('@')[-1]}")
    if args.wipe:
        wipe()
        dbmod._engine = None
    dbmod.init_db()
    with Session(dbmod.get_engine()) as session:
        tid = bootstrap_empty(session)
        email, _ = _admin_credentials()
        depts = session.exec(select(Department).where(Department.tenant_id == tid)).all()
        people = session.exec(select(Person).where(Person.tenant_id == tid)).all()
        print(f"\nEmpty company ready: tenant={tid}")
        print(f"  Departments (stubs only): {len(depts)}")
        print(f"  People (login only): {len(people)}")
        print(f"  Login: {email} / (ADMIN_PASSWORD)")
        print("  Next: Company data > Upload Excel")


if __name__ == "__main__":
    main()
