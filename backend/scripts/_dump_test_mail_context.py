from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine
from app.models.company import Department
from app.models.org import Location, Person
from app.services.admin_ops import admin_ops_email

REAL = [
    "skcbsa1221@gmail.com",
    "flexxftw12@gmail.com",
    "kshitiz.vishwakarma2003@gmail.com",
    "it.servicess8989@gmail.com",
    "cateringservices4656@gmail.com",
    "kmantri1204@gmail.com",
]


def main() -> None:
    s = get_settings()
    print("CLOUDMAILIN_ADDRESS:", (s.cloudmailin_address or "").strip() or "(not set in env)")
    print("ADMIN_OPS:", admin_ops_email())
    print("ACCEPT_REQUESTS_FROM:", s.accept_requests_from)

    with Session(get_engine()) as session:
        print("\n=== REAL PEOPLE ===")
        for e in REAL:
            p = session.exec(select(Person).where(Person.email == e)).first()
            if not p:
                print(e, "MISSING")
                continue
            loc = session.get(Location, p.site_id) if p.site_id else None
            print(
                f"{p.email} | {p.name} | dept={p.department} | role={p.role} | "
                f"site={loc.code if loc else None}"
            )

        print("\n=== TEAMS WITH GMAIL / PLUS ===")
        for d in session.exec(select(Department).where(Department.is_active == True)).all():  # noqa: E712
            e = (d.primary_email or "").lower()
            if "gmail.com" not in e:
                continue
            loc = session.get(Location, d.location_id) if d.location_id else None
            print(
                f"{d.code} | {d.primary_email} | loc={loc.code if loc else 'COMPANY'} | "
                f"cats={d.categories}"
            )

        print("\n=== SAMPLE BRANCHES ===")
        for code in ["BLR-HQ", "PUN-HQ", "GGM-HQ", "MUM-BKC"]:
            loc = session.exec(select(Location).where(Location.code == code)).first()
            print(code, "OK" if loc else "MISSING", loc.name if loc else "")


if __name__ == "__main__":
    main()
