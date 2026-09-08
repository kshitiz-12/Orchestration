"""Seed prototype demo data for all four scenarios."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.security import hash_password
from app.models import (
    BusinessRule,
    Contract,
    Location,
    NotificationTemplate,
    OutcomeTemplate,
    Person,
    PurchaseOrder,
    Receipt,
    Resource,
    ServiceCatalog,
    Tenant,
    Vendor,
)


TENANT_NAME = "Acme Workplace Demo"


def seed(session: Session) -> str:
    existing = session.exec(select(Tenant).where(Tenant.name == TENANT_NAME)).first()
    if existing:
        return existing.tenant_id

    tenant = Tenant(name=TENANT_NAME, region="IN", status="ACTIVE")
    session.add(tenant)
    session.flush()
    tid = tenant.tenant_id

    # Locations: 1 site, 3 floors, rooms/zones
    site = Location(tenant_id=tid, type="SITE", name="Acme HQ Bengaluru", alias="HQ", site_id=None)
    session.add(site)
    session.flush()
    site.site_id = site.location_id
    floors = []
    for i, name in enumerate(["Floor 1", "Floor 2", "Floor 3"], start=1):
        fl = Location(
            tenant_id=tid,
            parent_id=site.location_id,
            type="FLOOR",
            name=name,
            alias=f"F{i}",
            site_id=site.location_id,
        )
        session.add(fl)
        floors.append(fl)
    session.flush()
    rooms = []
    for fi, fl in enumerate(floors):
        for r in range(1, 4):
            room = Location(
                tenant_id=tid,
                parent_id=fl.location_id,
                type="ROOM",
                name=f"{fl.alias}-R{r}",
                alias=f"{fl.alias}R{r}",
                site_id=site.location_id,
            )
            session.add(room)
            rooms.append(room)
        zone = Location(
            tenant_id=tid,
            parent_id=fl.location_id,
            type="ZONE",
            name=f"{fl.alias} Open Zone",
            alias=f"{fl.alias}Z",
            site_id=site.location_id,
        )
        session.add(zone)
        rooms.append(zone)
    session.flush()

    # People
    def add_person(email, name, role, dept, manager_id=None):
        p = Person(
            tenant_id=tid,
            email=email.lower(),
            name=name,
            role=role,
            department=dept,
            manager_id=manager_id,
            site_id=site.location_id,
            is_active=True,
        )
        session.add(p)
        session.flush()
        return p

    admin = add_person("admin@prototype.local", "Proto Admin", "OPERATOR", "Operations")
    admin.password_hash = hash_password("admin123")
    session.add(admin)

    mgr = add_person("priya.manager@acme.demo", "Priya Manager", "MANAGER", "Engineering")
    hr = add_person("hr@acme.demo", "Hema HR", "HR", "People")
    it = add_person("it@acme.demo", "Ivan IT", "IT", "Technology")
    sec = add_person("security@acme.demo", "Sara Security", "SECURITY", "Security")
    admin_ops = add_person("admin.ops@acme.demo", "Asha Admin", "ADMIN", "Workplace")
    workplace = add_person("workplace@acme.demo", "Wes Workplace", "WORKPLACE", "Workplace")
    procurement = add_person("procurement@acme.demo", "Pam Procurement", "PROCUREMENT", "Procurement")
    finance = add_person("finance@acme.demo", "Finn Finance", "FINANCE", "Finance")

    employees = []
    for i in range(1, 11):
        employees.append(
            add_person(
                f"employee{i}@acme.demo",
                f"Employee {i}",
                "EMPLOYEE",
                "Engineering" if i % 2 else "Operations",
                manager_id=mgr.person_id,
            )
        )

    # Resources
    for i in range(1, 21):
        status = "AVAILABLE" if i > 15 else "ALLOCATED"
        allocated = employees[(i - 1) % len(employees)].person_id if status == "ALLOCATED" else None
        session.add(
            Resource(
                tenant_id=tid,
                type="SEAT",
                name=f"Seat-{i:02d}",
                location_id=rooms[(i - 1) % len(rooms)].location_id,
                status=status,
                allocated_to_person_id=allocated,
            )
        )
    for i in range(1, 11):
        session.add(
            Resource(
                tenant_id=tid,
                type="CHAIR",
                name=f"Chair-{i:02d}",
                location_id=rooms[(i - 1) % len(rooms)].location_id,
                status="ALLOCATED" if i <= 8 else "AVAILABLE",
                allocated_to_person_id=employees[(i - 1) % len(employees)].person_id if i <= 8 else None,
            )
        )
    for i in range(1, 6):
        session.add(
            Resource(
                tenant_id=tid,
                type="PARKING_SLOT",
                name=f"P-{i:02d}",
                location_id=site.location_id,
                status="ALLOCATED" if i <= 3 else "AVAILABLE",
                allocated_to_person_id=employees[i - 1].person_id if i <= 3 else None,
            )
        )
    for i in range(1, 6):
        session.add(
            Resource(
                tenant_id=tid,
                type="LAPTOP",
                name=f"Laptop-{i:02d}",
                status="AVAILABLE",
            )
        )
        session.add(
            Resource(
                tenant_id=tid,
                type="MONITOR",
                name=f"Monitor-{i:02d}",
                status="AVAILABLE",
            )
        )
    for i in range(1, 6):
        session.add(
            Resource(
                tenant_id=tid,
                type="ACCESS_CARD",
                name=f"Access-{i:02d}",
                status="AVAILABLE",
            )
        )

    # Vendors / commercial
    vendors = []
    for name, cat, email in [
        ("BrightFurniture Co", "Furniture", "orders@brightfurniture.demo"),
        ("SecureChips Ltd", "IT Hardware", "billing@securechips.demo"),
        ("CleanSupply Partners", "Facilities", "support@cleansupply.demo"),
    ]:
        v = Vendor(
            tenant_id=tid,
            name=name,
            category=cat,
            contact_email=email,
            location="Bengaluru",
            status="ACTIVE",
            approved_services=[cat],
            pricing={"currency": "INR"},
        )
        session.add(v)
        vendors.append(v)
    session.flush()

    contracts = []
    for v, rate in zip(vendors, [1200.0, 45000.0, 800.0]):
        c = Contract(
            tenant_id=tid,
            vendor_id=v.vendor_id,
            name=f"{v.name} MSA",
            rate_card={"unit_rate": rate, "currency": "INR"},
            status="ACTIVE",
        )
        session.add(c)
        contracts.append(c)
    session.flush()

    pos = []
    for i, (v, c) in enumerate(zip(vendors, contracts), start=1):
        for j in range(1, 3 if i < 3 else 2):
            po = PurchaseOrder(
                tenant_id=tid,
                vendor_id=v.vendor_id,
                contract_id=c.contract_id,
                po_number=f"PO-2026-{i}{j:02d}",
                description=f"{v.category} supply",
                quantity=10 if v.category != "IT Hardware" else 2,
                unit_rate=c.rate_card["unit_rate"],
                status="OPEN",
            )
            session.add(po)
            pos.append(po)
    session.flush()

    for po in pos[:5]:
        session.add(
            Receipt(
                tenant_id=tid,
                po_id=po.po_id,
                quantity_received=po.quantity,
                received_date="2026-03-01",
                status="CONFIRMED",
            )
        )

    # Services
    for cat, name, questions, owner in [
        ("ONBOARDING", "New employee workplace readiness", ["employee_name", "joining_date", "department", "manager"], "HR"),
        ("PARKING_CONFLICT", "Parking conflict resolution", ["resource_id"], "SECURITY"),
        ("FURNITURE_ISSUE", "Furniture issue", ["resource_type", "location"], "ADMIN"),
        ("VENDOR_ESCALATION", "Vendor quality/compliance", ["vendor_name", "issue_types"], "PROCUREMENT"),
        ("INVOICE", "Invoice settlement", ["invoice_number", "amount", "po_number", "vendor_name"], "FINANCE"),
    ]:
        session.add(
            ServiceCatalog(
                tenant_id=tid,
                category=cat,
                name=name,
                mandatory_questions=questions,
                sla_hours=48,
                owner_role=owner,
                evidence_rules=["photo_or_record"] if cat != "INVOICE" else ["invoice_file", "match_report"],
            )
        )

    # Outcome templates
    session.add(
        OutcomeTemplate(
            tenant_id=tid,
            code="ONBOARDING",
            name="Workplace Readiness Onboarding",
            category="ONBOARDING",
            case_prefix="ONB",
            mandatory_fields=["employee_name", "joining_date"],
            requirements=[
                {"code": "EMP_VERIFY", "title": "Employee verification", "is_mandatory": True},
                {"code": "SEAT", "title": "Seating readiness", "is_mandatory": True, "is_blocker": True},
                {"code": "IT_KIT", "title": "IT kit ready", "is_mandatory": True, "evidence_required": True},
                {"code": "ACCESS", "title": "Access credentials", "is_mandatory": True, "evidence_required": True},
                {"code": "INDUCTION", "title": "Induction complete", "is_mandatory": True},
            ],
            tasks=[
                {"code": "HR_VERIFY", "title": "Employee verification", "owner_role": "HR", "task_group": "HR", "requirement_code": "EMP_VERIFY"},
                {"code": "HR_ID", "title": "Issue employee ID", "owner_role": "HR", "task_group": "HR"},
                {"code": "HR_INDUCTION", "title": "Schedule induction", "owner_role": "HR", "task_group": "HR", "requirement_code": "INDUCTION"},
                {"code": "SEAT_PERMANENT", "title": "Allocate permanent seat", "owner_role": "ADMIN", "task_group": "ADMIN_PERMANENT", "requirement_code": "SEAT"},
                {"code": "SEAT_TEMP", "title": "Reserve temporary workstation if needed", "owner_role": "WORKPLACE", "task_group": "ADMIN_TEMP"},
                {"code": "CHAIR", "title": "Provide chair", "owner_role": "ADMIN", "task_group": "ADMIN"},
                {"code": "PEDESTAL", "title": "Provide pedestal", "owner_role": "ADMIN", "task_group": "ADMIN"},
                {"code": "WELCOME_KIT", "title": "Prepare welcome kit", "owner_role": "ADMIN", "task_group": "ADMIN"},
                {"code": "VISITING_CARD", "title": "Order visiting card", "owner_role": "ADMIN", "task_group": "ADMIN", "is_mandatory": False},
                {"code": "LAPTOP", "title": "Prepare laptop", "owner_role": "IT", "task_group": "IT", "requirement_code": "IT_KIT", "evidence_required": True},
                {"code": "MONITOR", "title": "Prepare monitor", "owner_role": "IT", "task_group": "IT"},
                {"code": "ACCOUNT", "title": "Create accounts", "owner_role": "IT", "task_group": "IT"},
                {"code": "APPS", "title": "Provision applications", "owner_role": "IT", "task_group": "IT", "depends_on": ["ACCOUNT"]},
                {"code": "ID_CARD", "title": "Issue ID card", "owner_role": "SECURITY", "task_group": "SECURITY", "requirement_code": "ACCESS"},
                {"code": "ACCESS_CARD", "title": "Issue access card", "owner_role": "SECURITY", "task_group": "SECURITY", "evidence_required": True},
                {"code": "RECEPTION", "title": "Notify reception", "owner_role": "SECURITY", "task_group": "SECURITY"},
                {"code": "PARKING_ACCESS", "title": "Parking access", "owner_role": "SECURITY", "task_group": "SECURITY", "is_mandatory": False},
                {"code": "MGR_APPROVALS", "title": "Access approvals", "owner_role": "MANAGER", "task_group": "MANAGER"},
                {"code": "MGR_DAY1", "title": "First-day plan", "owner_role": "MANAGER", "task_group": "MANAGER"},
                {"code": "MGR_BUDDY", "title": "Assign buddy", "owner_role": "MANAGER", "task_group": "MANAGER"},
            ],
        )
    )
    session.add(
        OutcomeTemplate(
            tenant_id=tid,
            code="PARKING_CONFLICT",
            name="Parking conflict",
            category="PARKING_CONFLICT",
            case_prefix="PARK",
            mandatory_fields=[],
            requirements=[
                {"code": "VERIFY_ALLOC", "title": "Verify allocation", "is_mandatory": True},
                {"code": "RESTORE", "title": "Restore immediate service", "is_mandatory": True, "evidence_required": True},
                {"code": "CORRECTIVE", "title": "Root cause corrective action", "is_mandatory": True},
            ],
            tasks=[
                {"code": "VERIFY_ALLOCATION", "title": "Verify official parking allocation", "owner_role": "SECURITY", "task_group": "VERIFY", "requirement_code": "VERIFY_ALLOC"},
                {"code": "TEMP_ALTERNATIVE", "title": "Provide temporary parking alternative", "owner_role": "SECURITY", "task_group": "RESTORE"},
                {"code": "RESTORE_SLOT", "title": "Restore assigned parking", "owner_role": "SECURITY", "task_group": "RESTORE", "requirement_code": "RESTORE", "evidence_required": True},
                {"code": "VERIFY_RESTORE", "title": "Verify restoration", "owner_role": "SECURITY", "task_group": "VERIFY", "depends_on": ["RESTORE_SLOT"], "evidence_required": True},
                {"code": "ROOT_CAUSE", "title": "Root-cause / corrective action", "owner_role": "ADMIN", "task_group": "CORRECTIVE", "requirement_code": "CORRECTIVE"},
            ],
        )
    )
    session.add(
        OutcomeTemplate(
            tenant_id=tid,
            code="FURNITURE_ISSUE",
            name="Furniture / chair issue",
            category="FURNITURE_ISSUE",
            case_prefix="FURN",
            requirements=[
                {"code": "TEMP_RESTORE", "title": "Temporary restoration", "is_mandatory": True, "evidence_required": True},
                {"code": "ROOT_CAUSE", "title": "Permanent corrective action", "is_mandatory": True},
            ],
            tasks=[
                {"code": "TEMP_CHAIR", "title": "Provide temporary chair", "owner_role": "ADMIN", "task_group": "RESTORE", "requirement_code": "TEMP_RESTORE", "evidence_required": True},
                {"code": "ROOT_CAUSE_CHAIR", "title": "Investigate missing chair root cause", "owner_role": "ADMIN", "task_group": "CORRECTIVE", "requirement_code": "ROOT_CAUSE"},
                {"code": "REPLACE_CHAIR", "title": "Replace / recover chair", "owner_role": "ADMIN", "task_group": "CORRECTIVE"},
            ],
        )
    )
    session.add(
        OutcomeTemplate(
            tenant_id=tid,
            code="VENDOR_ESCALATION",
            name="Vendor quality/compliance escalation",
            category="VENDOR_ESCALATION",
            case_prefix="VND",
            requirements=[
                {"code": "EVIDENCE_PACK", "title": "Collect evidence pack", "is_mandatory": True, "evidence_required": True},
                {"code": "VENDOR_RESPONSE", "title": "Vendor response", "is_mandatory": True},
                {"code": "HUMAN_DECISION", "title": "Authorised human decision", "is_mandatory": True},
            ],
            tasks=[
                {"code": "COLLECT_AGREEMENT", "title": "Collect agreement / spec", "owner_role": "PROCUREMENT", "task_group": "Quality", "requirement_code": "EVIDENCE_PACK"},
                {"code": "COLLECT_PO", "title": "Collect PO / delivery record", "owner_role": "PROCUREMENT", "task_group": "Procurement"},
                {"code": "QUALITY_REVIEW", "title": "Quality review (unverified allegations)", "owner_role": "PROCUREMENT", "task_group": "Quality"},
                {"code": "SAFETY_REVIEW", "title": "Safety review if applicable", "owner_role": "ADMIN", "task_group": "Safety"},
                {"code": "FINANCE_REVIEW", "title": "Billing review", "owner_role": "FINANCE", "task_group": "Finance"},
                {"code": "VENDOR_CONTACT", "title": "Request vendor response", "owner_role": "PROCUREMENT", "task_group": "Vendor Response", "requirement_code": "VENDOR_RESPONSE"},
                {"code": "SUPPLY_CONTINUITY", "title": "Supply continuity plan", "owner_role": "PROCUREMENT", "task_group": "Supply Continuity"},
                {"code": "SANCTION_DECISION", "title": "Human sanction / show-cause decision", "owner_role": "PROCUREMENT", "task_group": "Procurement", "requirement_code": "HUMAN_DECISION"},
            ],
        )
    )
    session.add(
        OutcomeTemplate(
            tenant_id=tid,
            code="INVOICE",
            name="Invoice settlement",
            category="INVOICE",
            case_prefix="INV",
            mandatory_fields=["invoice_number", "amount"],
            requirements=[
                {"code": "EXTRACT", "title": "Invoice extracted & validated", "is_mandatory": True},
                {"code": "THREE_WAY", "title": "Three-way match", "is_mandatory": True},
                {"code": "APPROVAL", "title": "Payment approval", "is_mandatory": True},
                {"code": "ERP", "title": "ERP mock handoff", "is_mandatory": True},
            ],
            tasks=[
                {"code": "EXTRACT_FIELDS", "title": "Extract invoice fields", "owner_role": "FINANCE", "task_group": "Extract", "requirement_code": "EXTRACT"},
                {"code": "VENDOR_VERIFY", "title": "Verify vendor identity", "owner_role": "FINANCE", "task_group": "Extract"},
                {"code": "THREE_WAY_MATCH", "title": "PO + Receipt + Invoice match", "owner_role": "FINANCE", "task_group": "Match", "requirement_code": "THREE_WAY"},
                {"code": "PAYMENT_APPROVAL", "title": "Human payment approval (no auto-pay)", "owner_role": "FINANCE", "task_group": "Approval", "requirement_code": "APPROVAL"},
                {"code": "ERP_HANDOFF", "title": "Controlled ERP mock handoff", "owner_role": "FINANCE", "task_group": "Handoff", "requirement_code": "ERP", "depends_on": ["PAYMENT_APPROVAL"]},
                {"code": "BANK_VERIFY", "title": "Independent bank-details verification if changed", "owner_role": "FINANCE", "task_group": "Approval", "is_mandatory": False},
            ],
        )
    )
    session.add(
        OutcomeTemplate(
            tenant_id=tid,
            code="GENERAL",
            name="General request",
            category="GENERAL",
            case_prefix="EVT",
            requirements=[{"code": "TRIAGE", "title": "Triage request", "is_mandatory": True}],
            tasks=[
                {"code": "TRIAGE", "title": "Operator triage", "owner_role": "OPERATOR", "task_group": "Ops", "requirement_code": "TRIAGE"},
            ],
        )
    )

    session.add(
        BusinessRule(
            tenant_id=tid,
            code="CONFIDENCE_ROUTING",
            category="AI",
            description="Prototype confidence routing thresholds",
            config={"auto": 0.85, "review": 0.65, "sensitive_always_human": True},
        )
    )
    session.add(
        BusinessRule(
            tenant_id=tid,
            code="INVOICE_TOLERANCE",
            category="FINANCE",
            description="Prototype match tolerances",
            config={"quantity_tol": 0.0, "rate_tol": 0.01, "amount_tol": 1.0},
        )
    )
    session.add(
        NotificationTemplate(
            tenant_id=tid,
            code="INFO_REQUIRED",
            communication_type="INFORMATION_REQUIRED",
            subject_template="[INFORMATION REQUIRED] [{{case_reference}}] Additional details needed",
            body_template="We need: {{questions}}",
        )
    )

    session.commit()
    return tid


def main():
    from app.core.database import get_engine, init_db

    init_db()
    with Session(get_engine()) as session:
        tid = seed(session)
        print(f"Seeded tenant_id={tid}")


if __name__ == "__main__":
    main()
