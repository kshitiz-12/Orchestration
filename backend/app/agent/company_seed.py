"""Sample company data so the AI admin has something real to work with.

Everything here is a placeholder the company replaces from the dashboard or by bulk upload.
Department mailboxes use the reserved `.invalid` domain: mail for them is redirected to the
main admin (ADMIN_OPS_EMAIL) until a real address is entered.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.company import Department, KnowledgeEntry
from app.models.org import Person, Vendor

PLACEHOLDER_DOMAIN = "example.invalid"

DEFAULT_DEPARTMENTS: list[dict] = [
    {"code": "ADMIN", "name": "Admin & Workplace", "categories": [
        "general", "meeting_room", "supplies", "courier", "printing", "seating", "event", "guest_house"], "sla_hours": 24},
    {"code": "FACILITIES", "name": "Facilities & Maintenance", "categories": [
        "maintenance", "furniture", "electrical", "plumbing", "hvac", "pest_control", "waste_disposal", "health_safety"],
     "sla_hours": 8},
    {"code": "HOUSEKEEPING", "name": "Housekeeping", "categories": ["housekeeping", "pantry", "cleaning"], "sla_hours": 4},
    {"code": "IT", "name": "IT Support", "categories": [
        "it_support", "access_card", "laptop", "network", "software", "phone_sim", "asset"], "sla_hours": 8},
    {"code": "SECURITY", "name": "Security & Front Desk", "categories": [
        "visitor", "security", "parking", "material_gate_pass", "lost_found", "keys_locker"], "sla_hours": 4},
    {"code": "TRAVEL", "name": "Travel Desk", "categories": ["travel", "cab", "hotel", "flight", "employee_transport"], "sla_hours": 12},
    {"code": "HR", "name": "People / HR", "categories": ["onboarding", "hr_query", "offboarding"], "sla_hours": 24},
    {"code": "FINANCE", "name": "Finance & Accounts", "categories": ["invoice", "reimbursement", "payment"], "sla_hours": 48, "spend_approval_limit": 50000},
    {"code": "PROCUREMENT", "name": "Procurement", "categories": ["purchase", "vendor"], "sla_hours": 48, "spend_approval_limit": 25000},
    {"code": "CAFETERIA", "name": "Cafeteria & Catering", "categories": ["catering", "cafeteria"], "sla_hours": 12},
]

DEFAULT_KNOWLEDGE: list[dict] = [
    {
        "key": "company_profile",
        "section": "company",
        "title": "Company profile",
        "content": (
            "Acme Corp (sample data). The Workplace / Admin Desk handles meeting rooms, visitors, parking, "
            "facility issues, IT help routing, supplies, travel, onboarding logistics and vendor invoices. "
            "Employees reach us by simply emailing this mailbox."
        ),
    },
    {
        "key": "offices",
        "section": "offices",
        "title": "Offices and working hours",
        "content": (
            "Corporate Office, Gurugram (primary): Tower B, Cyber City, DLF Phase 2, Gurugram 122002. "
            "Hours Mon-Fri 9:00 AM-7:00 PM, Sat 10:00 AM-2:00 PM.\n"
            "Acme HQ Bengaluru: Outer Ring Road, Bellandur, Bengaluru 560103. Hours Mon-Fri 9:00 AM-6:30 PM.\n"
            "Admin desk is on the ground floor reception at both offices."
        ),
    },
    {
        "key": "visitor_policy",
        "section": "policy",
        "title": "Visitor policy",
        "content": (
            "Visitors must be pre-registered by an employee host at least 2 hours before arrival. "
            "Visitors carry a government photo ID; the host receives them at reception. "
            "Visiting hours 9:00 AM-7:00 PM. Laptops are logged at the gate."
        ),
    },
    {
        "key": "parking_policy",
        "section": "policy",
        "title": "Parking policy",
        "content": (
            "Visitor parking is allotted on request with the vehicle number, subject to availability. "
            "Employee parking is by monthly allocation from Security. Parking hours 8:00 AM-9:00 PM."
        ),
    },
    {
        "key": "supplies_policy",
        "section": "policy",
        "title": "Supplies and purchases",
        "content": (
            "Stationery and standard peripherals up to INR 5,000 per request are issued without approval. "
            "Above that, manager/admin approval is needed. Monitors and laptops go through IT."
        ),
    },
    {
        "key": "travel_policy",
        "section": "policy",
        "title": "Travel policy",
        "content": (
            "Office cabs are available for late-night drops after 9:00 PM and for client visits. "
            "Airport transfers are booked by the Travel Desk with 24 hours notice. "
            "Flights and hotels need manager approval before booking."
        ),
    },
    {
        "key": "catering_policy",
        "section": "policy",
        "title": "Catering",
        "content": (
            "Tea/coffee and drinking water are included site facilities (no approval). "
            "Working lunch is subsidised and high tea / special menus are chargeable to the requester's cost centre; "
            "only the chargeable portion needs cost approval. See the site service catalogue in Company setup."
        ),
    },
    {
        "key": "faq_wifi",
        "section": "faq",
        "title": "Guest Wi-Fi",
        "content": "Guest Wi-Fi network 'Acme-Guest'; the reception issues a daily access code to registered visitors.",
    },
    {
        "key": "faq_lost_found",
        "section": "faq",
        "title": "Lost and found",
        "content": "Lost and found is kept at the ground-floor reception for 30 days.",
    },
]

SAMPLE_EMPLOYEES: list[tuple[str, str, str, str]] = [
    ("rohan.mehta@acme.demo", "Rohan Mehta", "MANAGER", "Sales"),
    ("neha.kapoor@acme.demo", "Neha Kapoor", "EMPLOYEE", "Sales"),
    ("arjun.singh@acme.demo", "Arjun Singh", "EMPLOYEE", "Engineering"),
    ("kavya.iyer@acme.demo", "Kavya Iyer", "EMPLOYEE", "Engineering"),
    ("vikram.rao@acme.demo", "Vikram Rao", "MANAGER", "Finance"),
    ("sneha.joshi@acme.demo", "Sneha Joshi", "EMPLOYEE", "Marketing"),
    ("amit.verma@acme.demo", "Amit Verma", "EMPLOYEE", "Operations"),
    ("pooja.nair@acme.demo", "Pooja Nair", "EMPLOYEE", "People"),
    ("rahul.gupta@acme.demo", "Rahul Gupta", "EMPLOYEE", "Technology"),
    ("ananya.das@acme.demo", "Ananya Das", "EMPLOYEE", "Legal"),
    ("karan.malhotra@acme.demo", "Karan Malhotra", "MANAGER", "Operations"),
    ("divya.menon@acme.demo", "Divya Menon", "EMPLOYEE", "Marketing"),
]

SAMPLE_VENDORS: list[tuple[str, str, str]] = [
    ("QuickRide Corporate Cabs", "transport", f"bookings@quickride.{PLACEHOLDER_DOMAIN}"),
    ("FixIt Facility Services", "facility_maintenance", f"service@fixit.{PLACEHOLDER_DOMAIN}"),
    ("OfficeMart Supplies", "stationery", f"orders@officemart.{PLACEHOLDER_DOMAIN}"),
]


def placeholder_email(code: str) -> str:
    return f"{code.lower()}@{PLACEHOLDER_DOMAIN}"


def is_placeholder(email: str | None) -> bool:
    addr = (email or "").strip().lower()
    return not addr or addr.endswith("." + PLACEHOLDER_DOMAIN) or addr.endswith("@" + PLACEHOLDER_DOMAIN)


def ensure_company_seed(session: Session, tenant_id: str) -> None:
    """Idempotent: only adds rows that are missing, never overwrites what the company edited."""
    have_depts = {d.code for d in session.exec(select(Department).where(Department.tenant_id == tenant_id)).all()}
    for spec in DEFAULT_DEPARTMENTS:
        if spec["code"] in have_depts:
            continue
        session.add(
            Department(
                tenant_id=tenant_id,
                code=spec["code"],
                name=spec["name"],
                categories=list(spec["categories"]),
                primary_email=placeholder_email(spec["code"]),
                sla_hours=spec.get("sla_hours", 24),
                spend_approval_limit=float(spec.get("spend_approval_limit", 0)),
                notes="Sample data - replace the placeholder email from Company setup.",
            )
        )

    have_kb = {k.key for k in session.exec(select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tenant_id)).all()}
    for spec in DEFAULT_KNOWLEDGE:
        if spec["key"] not in have_kb:
            session.add(KnowledgeEntry(tenant_id=tenant_id, **spec))

    have_people = {p.email for p in session.exec(select(Person).where(Person.tenant_id == tenant_id)).all()}
    for email, name, role, dept in SAMPLE_EMPLOYEES:
        if email not in have_people:
            session.add(Person(tenant_id=tenant_id, email=email, name=name, role=role, department=dept))

    have_vendors = {v.name for v in session.exec(select(Vendor).where(Vendor.tenant_id == tenant_id)).all()}
    for name, category, email in SAMPLE_VENDORS:
        if name not in have_vendors:
            session.add(Vendor(tenant_id=tenant_id, name=name, category=category, contact_email=email))
    session.flush()

    from app.services.site_services import ensure_site_services

    ensure_site_services(session, tenant_id)
