"""Pull the Darwinbox file and the stock file into the first company in the desk database.

    python -m scripts.sync_external_sources
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import get_engine
from app.models.org import Tenant
from app.services.source_sync import sync_darwinbox, sync_stock


def main() -> None:
    with Session(get_engine()) as session:
        tenant = session.exec(select(Tenant)).first()
        if tenant is None:
            raise SystemExit("No company in the desk database yet. Seed it before syncing.")
        people = sync_darwinbox(session, tenant.tenant_id)
        stock = sync_stock(session, tenant.tenant_id)
        session.commit()
    print("Darwinbox:", people)
    print("Stock:", stock)


if __name__ == "__main__":
    main()
