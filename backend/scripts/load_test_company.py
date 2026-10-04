"""Build the manual-test company on the current DATABASE_URL.

    python -m scripts.load_test_company --wipe     clear EVERYTHING, then build the test company
    python -m scripts.load_test_company            build on top of what is there (idempotent)

Every team uses a Gmail sub-address of one of the five real test inboxes (flexxftw12+pune@gmail.com lands in
flexxftw12@gmail.com), so work orders for different teams/branches are real, visible and still easy to tell apart by
the To: line. The plain addresses are employees at different branches, so you can send requests from them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.models.company import Department, KnowledgeEntry  # noqa: E402
from app.models.org import Location, Person, Tenant  # noqa: E402

ADMIN = "skcbsa1221@gmail.com"
FAC = "flexxftw12@gmail.com"
IT = "it.servicess8989@gmail.com"
HR = "kshitiz.vishwakarma2003@gmail.com"
CAF = "cateringservices4656@gmail.com"


def sub(addr: str, tag: str) -> str:
    local, domain = addr.split("@")
    return f"{local}+{tag}@{domain}"


# code, name, type, parent code, aliases
PLACES = [
    ("WEST", "West", "REGION", None, ""),
    ("SOUTH", "South", "REGION", None, ""),
    ("NORTH", "North", "REGION", None, ""),
    ("MUM", "Mumbai", "CITY", "WEST", "Bombay"),
    ("MUM-BKC", "Mumbai BKC", "BRANCH", "MUM", "BKC; Bandra Kurla Complex; Mumbai office"),
    ("PUN", "Pune", "CITY", "WEST", ""),
    ("PUN-HJ", "Pune Hinjewadi", "BRANCH", "PUN", "Hinjewadi; Pune office"),
    ("BLR", "Bengaluru", "CITY", "SOUTH", "Bangalore"),
    # BLR-HQ is the seed's existing site (with its floors and meeting rooms), re-parented here.
    ("CHN", "Chennai", "CITY", "SOUTH", "Madras"),
    ("CHN-OMR", "Chennai OMR", "BRANCH", "CHN", "OMR; Chennai office"),
    ("GGN", "Gurugram", "CITY", "NORTH", "Gurgaon"),
    ("GGN-CC", "Gurugram Cyber City", "BRANCH", "GGN", "Cyber City; Gurgaon office; Gurugram office"),
]

# Company-wide teams (codes from the default catalogue): mailbox, approver, spend limit, where to collect
COMPANY_TEAMS = {
    "ADMIN": (ADMIN, ADMIN, 0.0, None),
    "FACILITIES": (sub(FAC, "facilities"), ADMIN, 1000.0, None),
    "IT": (sub(IT, "it"), ADMIN, 0.0, "IT desk, 2nd floor, Bengaluru HQ, 10 AM - 6 PM"),
    "HR": (sub(HR, "hr"), ADMIN, 0.0, None),
    "CAFETERIA": (sub(CAF, "cafeteria"), ADMIN, 0.0, None),
}

# Branch / region teams: code, name, categories, mailbox, covers, approver, collect
BRANCH_TEAMS = [
    ("FACILITIES_PUN", "Facilities - Pune", ["maintenance", "furniture", "electrical", "plumbing", "hvac",
                                             "pest_control", "housekeeping"], sub(FAC, "pune"), "PUN", None,
     "Admin desk, ground floor, Pune Hinjewadi"),
    ("ADMIN_PUN", "Admin - Pune", ["supplies", "courier", "printing", "seating"], sub(ADMIN, "pune"), "PUN",
     sub(ADMIN, "pune"), "Admin desk, ground floor, Pune Hinjewadi, 9:30 AM - 6 PM"),
    ("IT_NORTH", "IT Support - North", ["it_support", "laptop", "network", "software", "access_card", "phone_sim",
                                        "asset"], sub(IT, "north"), "NORTH", None,
     "IT room, 5th floor, Gurugram Cyber City"),
    ("ADMIN_SOUTH", "Admin - South", [], sub(ADMIN, "south"), "SOUTH", sub(ADMIN, "south"), None),
]

# Real inboxes as employees: email, name, department, role, branch
REAL_EMPLOYEES = [
    (HR, "Kshitiz Vishwakarma", "People", "HR", "MUM-BKC"),
    (CAF, "Ananya Rao", "Sales", "EMPLOYEE", "PUN-HJ"),
    (FAC, "Vikram Shetty", "Engineering", "EMPLOYEE", "CHN-OMR"),
    (IT, "Neha Kapoor", "Finance", "EMPLOYEE", "GGN-CC"),
]

FIRST = ["Aarav", "Diya", "Kabir", "Isha", "Rohan", "Meera", "Arjun", "Sana", "Dev", "Tara", "Karan", "Riya",
         "Aditya", "Pooja", "Nikhil", "Sneha", "Varun", "Kavya", "Siddharth", "Anjali"]
LAST = ["Sharma", "Iyer", "Gupta", "Nair", "Patel", "Reddy", "Mehta", "Khan", "Das", "Joshi"]
DEPTS = ["Engineering", "Sales", "Finance", "Operations", "Marketing", "People", "Technology", "Legal"]
FAKE_BRANCHES = ["MUM-BKC", "PUN-HJ", "BLR-HQ", "CHN-OMR", "GGN-CC"]

KNOWLEDGE = {
    "offices": ("office", "Our offices",
                "Mumbai BKC (West) - registered office, 9:30 AM - 6:30 PM.\n"
                "Pune Hinjewadi (West) - Phase 1, 9:30 AM - 6 PM; admin desk on the ground floor.\n"
                "Bengaluru HQ (South) - 3 floors, meeting rooms F1-R1 to F3-R3; IT desk on the 2nd floor.\n"
                "Chennai OMR (South) - 9 AM - 6 PM; handled by the South admin team.\n"
                "Gurugram Cyber City (North) - 9:30 AM - 6:30 PM; IT room on the 5th floor."),
    "canteen_by_branch": ("office", "Canteen timings by branch",
                          "Bengaluru HQ and Mumbai BKC: 8:30 AM - 6 PM. Pune Hinjewadi: 9 AM - 4 PM. "
                          "Chennai OMR and Gurugram: pantry only (tea/coffee), lunch via the empanelled caterer."),
}


def wipe() -> None:
    import app.core.database as dbmod

    get_settings.cache_clear()
    dbmod._engine = None
    settings = get_settings()
    engine = dbmod.get_engine()
    if settings.is_sqlite:
        SQLModel.metadata.drop_all(engine)
    else:
        names = [t.name for t in SQLModel.metadata.sorted_tables]
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
    print("Wiped all data")


def build(session: Session) -> str:
    from app.agent.company_seed import ensure_company_seed
    from app.engine.meeting_scenario import ensure_meeting_room_resources, ensure_meeting_room_template
    from scripts.seed import seed

    tid = seed(session)
    ensure_meeting_room_template(session, tid)
    ensure_meeting_room_resources(session, tid)
    ensure_company_seed(session, tid)
    session.commit()

    by_code: dict[str, Location] = {
        p.code: p for p in session.exec(select(Location).where(Location.tenant_id == tid)).all() if p.code
    }
    for code, name, ptype, parent, aliases in PLACES:
        place = by_code.get(code) or Location(tenant_id=tid, code=code, name=name, type=ptype)
        place.name, place.type, place.alias = name, ptype, aliases or None
        place.parent_id = by_code[parent].location_id if parent else None
        session.add(place)
        session.flush()
        by_code[code] = place

    hq = by_code.get("BLR-HQ") or session.exec(
        select(Location).where(Location.tenant_id == tid, Location.name == "Acme HQ Bengaluru")
    ).first()
    if hq is not None:
        hq.code, hq.type, hq.parent_id = "BLR-HQ", "BRANCH", by_code["BLR"].location_id
        hq.alias = "HQ; head office; Bengaluru HQ; Bangalore HQ; Bengaluru office; Bangalore office"
        session.add(hq)
        session.flush()
        by_code["BLR-HQ"] = hq

    depts = {d.code: d for d in session.exec(select(Department).where(Department.tenant_id == tid)).all()}
    for code, (mailbox, approver, limit, collect) in COMPANY_TEAMS.items():
        d = depts[code]
        d.primary_email, d.approver_email, d.backup_emails = mailbox, approver, []
        d.spend_approval_limit, d.location_id = limit, None
        d.handover_info = collect
        d.notes = "Test company"
        session.add(d)
    for code, name, cats, mailbox, covers, approver, collect in BRANCH_TEAMS:
        d = depts.get(code) or Department(tenant_id=tid, code=code, name=name)
        d.name, d.categories, d.primary_email, d.backup_emails = name, cats, mailbox, []
        d.approver_email, d.handover_info, d.is_active = approver, collect, True
        d.location_id = by_code[covers].location_id
        d.sla_hours = 8
        d.notes = "Test company"
        session.add(d)
    session.flush()

    people = {p.email: p for p in session.exec(select(Person).where(Person.tenant_id == tid)).all()}
    hr_person = None
    for email, name, dept, role, branch in REAL_EMPLOYEES:
        p = people.get(email) or Person(tenant_id=tid, email=email, name=name)
        p.name, p.department, p.role, p.is_active = name, dept, role, True
        p.site_id = by_code[branch].location_id
        session.add(p)
        session.flush()
        people[email] = p
        if email == HR:
            hr_person = p
    for email, *_ in REAL_EMPLOYEES[1:]:
        people[email].manager_id = hr_person.person_id if hr_person else None
        session.add(people[email])

    for i in range(60):
        first, last = FIRST[i % len(FIRST)], LAST[(i * 7) % len(LAST)]
        email = f"{first}.{last}{i:02d}@acme.example".lower()
        p = people.get(email) or Person(tenant_id=tid, email=email, name=f"{first} {last}")
        p.department = DEPTS[i % len(DEPTS)]
        p.role = "MANAGER" if i % 10 == 0 else "EMPLOYEE"
        p.site_id = by_code[FAKE_BRANCHES[i % len(FAKE_BRANCHES)]].location_id
        session.add(p)
    session.flush()

    for key, (section, title, content) in KNOWLEDGE.items():
        entry = session.exec(
            select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tid, KnowledgeEntry.key == key)
        ).first() or KnowledgeEntry(tenant_id=tid, key=key, title=title, content=content)
        entry.section, entry.title, entry.content, entry.is_active = section, title, content, True
        session.add(entry)

    tenant = session.get(Tenant, tid)
    session.commit()
    return tenant.tenant_id


def summary(session: Session, tid: str) -> None:
    from app.agent.places import path_label

    print("\nBranches:")
    for p in session.exec(select(Location).where(Location.tenant_id == tid, Location.code.is_not(None))).all():
        if p.type == "BRANCH":
            print(f"  {p.code:8} {path_label(session, tid, p.location_id)}")
    print("\nTeams with a real inbox:")
    for d in session.exec(select(Department).where(Department.tenant_id == tid).order_by(Department.code)).all():
        if d.primary_email and not d.primary_email.endswith("invalid"):
            where = path_label(session, tid, d.location_id) if d.location_id else "whole company"
            print(f"  {d.code:15} {d.primary_email:42} covers {where}")
    print("\nSend requests from (employee, branch):")
    for email, name, _, _, branch in REAL_EMPLOYEES:
        print(f"  {email:36} {name:22} {branch}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="delete ALL data first")
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
        tid = build(session)
        summary(session, tid)
    print("\nAdmin login: admin@prototype.local")


if __name__ == "__main__":
    main()
