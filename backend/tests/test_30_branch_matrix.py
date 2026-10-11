"""30-branch routing matrix — synthetic mail only (no CloudMailin / SMTP).

Blueprint coverage:
- Geographic tree with deliberate dense / partial / sparse team gaps
- TC-01..06 archetypes
- Parametrized per-branch bubble-up for facilities
- Multi-turn team "done" reply closes cleanly

Outbound SMTP is already blanked in conftest; communications land in the DB.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.agent.directory import route_for
from app.agent.importer import run_bundle_import
from app.agent.places import find_place
from app.core.config import get_settings
from app.models.company import Department
from app.models.intake import RawEmailEvent
from app.models.org import Location, Person
from app.models.outcome import Communication, Outcome
from test_admin_desk import _mail, _mails_to, _run
from test_live_directory import _ai, _orders, _reads, _reply

# --- mailboxes (deterministic @company.com — never hit a real server) ---
ADMIN_OPS = "central-admin@company.com"
IT_BLR = "it.blr@company.com"
FAC_BLR = "facilities.blr@company.com"
FAC_GGN = "facilities.ggn@company.com"
IT_GGN = "it.ggn@company.com"
FAC_MUM = "facilities.mumbai@company.com"
IT_MUM = "it.mumbai@company.com"
IT_NORTH = "it.north@company.com"
ADMIN_FAR = "admin.faridabad@company.com"
FAC_WEST = "facilities.west@company.com"

# Dense / partial / sparse anchors from the blueprint
BLR_HQ, GGN_HQ, MUM_BKC = "BLR-HQ", "GGN-HQ", "MUM-BKC"
FARIDABAD, RANCHI = "FAR", "RAN"


def _places_rows() -> list[dict[str, str]]:
    """4 regions, cities, 30 branches — matches the blueprint tree (codes stable for assertions)."""
    regions = [
        ("NORTH", "North", "REGION", ""),
        ("WEST", "West", "REGION", ""),
        ("SOUTH", "South", "REGION", ""),
        ("EAST", "East", "REGION", ""),
    ]
    cities = [
        ("NCR", "Delhi NCR", "CITY", "NORTH"),
        ("PBH", "Punjab Haryana", "CITY", "NORTH"),
        ("MH", "Maharashtra", "CITY", "WEST"),
        ("GJ", "Gujarat", "CITY", "WEST"),
        ("KA", "Karnataka", "CITY", "SOUTH"),
        ("TNTEL", "Tamil Nadu Telangana", "CITY", "SOUTH"),
        ("EASTC", "East Corridor", "CITY", "EAST"),
    ]
    branches = [
        # North (8)
        ("GGN-HQ", "Gurugram HQ", "NCR", "Gurugram; Gurgaon"),
        ("NOI-62", "Noida Sector 62", "NCR", "Noida"),
        ("DEL-CP", "Delhi Connaught Place", "NCR", "CP; Connaught Place"),
        (FARIDABAD, "Faridabad", "NCR", "Faridabad office"),
        ("CHD", "Chandigarh", "PBH", "Chandigarh"),
        ("LDH", "Ludhiana", "PBH", ""),
        ("ASR", "Amritsar", "PBH", ""),
        ("KNL", "Karnal", "PBH", ""),
        # West (9)
        (MUM_BKC, "Mumbai BKC", "MH", "BKC; Mumbai office"),
        ("MUM-AND", "Mumbai Andheri", "MH", "Andheri"),
        ("PUN-HJ", "Pune Hinjewadi", "MH", "Hinjewadi; Pune office"),
        ("PUN-MG", "Pune Magarpatta", "MH", "Magarpatta"),
        ("NAG", "Nagpur", "MH", ""),
        ("NSK", "Nashik", "MH", ""),
        ("AHM-SG", "Ahmedabad SG", "GJ", "SG Highway; Ahmedabad"),
        ("SUR", "Surat", "GJ", ""),
        ("VAD", "Vadodara", "GJ", ""),
        # South (9)
        (BLR_HQ, "Bengaluru HQ", "KA", "HQ; Bengaluru office; Bangalore HQ"),
        ("BLR-WF", "Bengaluru Whitefield", "KA", "Whitefield"),
        ("MYS", "Mysuru", "KA", "Mysore"),
        ("CHN-OMR", "Chennai OMR", "TNTEL", "OMR"),
        ("CHN-GU", "Chennai Guindy", "TNTEL", "Guindy"),
        ("HYD-HIT", "Hyderabad HITEC", "TNTEL", "HITEC; Hitec City"),
        ("HYD-GAC", "Hyderabad Gachibowli", "TNTEL", "Gachibowli"),
        ("CBE", "Coimbatore", "TNTEL", ""),
        ("COK", "Kochi", "TNTEL", "Cochin"),
        # East (4)
        ("KOL-SL", "Kolkata Salt Lake", "EASTC", "Salt Lake"),
        ("BBI", "Bhubaneswar", "EASTC", ""),
        ("PAT", "Patna", "EASTC", ""),
        (RANCHI, "Ranchi", "EASTC", ""),
    ]
    rows = [{"code": c, "name": n, "type": t, "parent_code": p, "aliases": ""} for c, n, t, p in regions + cities]
    rows += [{"code": c, "name": n, "type": "BRANCH", "parent_code": city, "aliases": a} for c, n, city, a in branches]
    assert len(branches) == 30
    return rows


def _dept_rows() -> list[dict[str, str]]:
    """Dense local desks, regional IT North, partial Faridabad admin, West facilities hub.

    Company-wide FACILITIES / IT stay on @example.invalid so sparse branches redirect to ADMIN_OPS.
    """
    fac_cats = "maintenance; furniture; electrical; plumbing; hvac; pest_control"
    it_cats = "it_support; laptop; network; software; access_card; phone_sim; asset"
    rows = [
        # Dense: Gurugram HQ, Bengaluru HQ, Mumbai BKC
        {"code": "FACILITIES_GGN", "name": "Facilities - Gurugram", "categories": fac_cats,
         "primary_email": FAC_GGN, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": GGN_HQ},
        {"code": "IT_GGN", "name": "IT - Gurugram", "categories": it_cats,
         "primary_email": IT_GGN, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": GGN_HQ},
        {"code": "FACILITIES_BLR", "name": "Facilities - Bengaluru HQ", "categories": fac_cats,
         "primary_email": FAC_BLR, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": BLR_HQ},
        {"code": "IT_BLR", "name": "IT - Bengaluru HQ", "categories": it_cats,
         "primary_email": IT_BLR, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": BLR_HQ},
        {"code": "FACILITIES_MUM", "name": "Facilities - Mumbai BKC", "categories": fac_cats,
         "primary_email": FAC_MUM, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": MUM_BKC},
        {"code": "IT_MUM", "name": "IT - Mumbai BKC", "categories": it_cats,
         "primary_email": IT_MUM, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": MUM_BKC},
        # Regional fallbacks
        {"code": "IT_NORTH", "name": "IT - North Region", "categories": it_cats,
         "primary_email": IT_NORTH, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": "NORTH"},
        {"code": "FACILITIES_WEST", "name": "Facilities - West Region", "categories": fac_cats,
         "primary_email": FAC_WEST, "backup_emails": "", "approver_email": "", "sla_hours": "8",
         "spend_approval_limit": "0", "location": "WEST"},
        # Partial: Faridabad pantry/admin only (no IT)
        {"code": "ADMIN_FAR", "name": "Admin - Faridabad", "categories": "supplies; pantry; seating; printing",
         "primary_email": ADMIN_FAR, "backup_emails": "", "approver_email": ADMIN_FAR, "sla_hours": "8",
         "spend_approval_limit": "0", "location": FARIDABAD},
    ]
    return rows


def _employee_rows() -> list[dict[str, str]]:
    named = [
        ("ramesh.it042@company.com", "Ramesh Kumar", "Technology", "EMPLOYEE", BLR_HQ),
        ("simran.hr112@company.com", "Simran Kaur", "People", "EMPLOYEE", FARIDABAD),
        ("alok.ops301@company.com", "Alok Verma", "Operations", "EMPLOYEE", RANCHI),
        ("priya.fin88@company.com", "Priya Shah", "Finance", "EMPLOYEE", "PUN-HJ"),
        ("vikram.mkt09@company.com", "Vikram Mehta", "Marketing", "EMPLOYEE", "AHM-SG"),
    ]
    # One synthetic employee per branch for the matrix
    extras = []
    for i, row in enumerate(_places_rows()):
        if row["type"] != "BRANCH":
            continue
        extras.append((
            f"emp.{row['code'].lower().replace('-', '')}@company.com",
            f"Employee {row['code']}",
            "Operations",
            "EMPLOYEE",
            row["code"],
        ))
    out = []
    for email, name, dept, role, loc in named + extras:
        out.append({
            "email": email, "name": name, "department": dept, "role": role,
            "manager_email": "", "location": loc,
        })
    return out


@pytest.fixture
def matrix(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN_OPS)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "off")
    monkeypatch.setenv("ACCEPT_REQUESTS_FROM", "employees")
    get_settings.cache_clear()

    tid = session.exec(select(Person).where(Person.email == "admin@prototype.local")).first().tenant_id
    # Keep company FACILITIES/IT as placeholders so sparse branches redirect to ADMIN_OPS
    for code in ("FACILITIES", "IT", "ADMIN", "HOUSEKEEPING"):
        dept = session.exec(select(Department).where(Department.tenant_id == tid, Department.code == code)).first()
        if dept:
            dept.primary_email = f"{code.lower()}@example.invalid"
            dept.backup_emails = []
            session.add(dept)
    session.commit()

    result = run_bundle_import(
        session,
        tid,
        {
            "locations": _places_rows(),
            "departments": _dept_rows(),
            "employees": _employee_rows(),
        },
        commit=True,
        source="workbook",
    )
    assert not result["errors"], result["errors"]
    branches = [p for p in session.exec(select(Location).where(Location.tenant_id == tid)).all()
                if (p.type or "").upper() == "BRANCH"]
    assert len(branches) >= 30
    yield tid
    get_settings.cache_clear()


def _request(session, tid, sender, body, subject, intent):
    return _run(session, tid, _mail(session, tid, body, sender=sender, subject=subject), _ai(intent))


def _branch_codes() -> list[str]:
    return [r["code"] for r in _places_rows() if r["type"] == "BRANCH"]


def _expected_facilities_mailbox(code: str) -> str:
    """Nearest facilities desk: dense local → West hub → local admin (if any) → ADMIN_OPS."""
    if code == BLR_HQ:
        return FAC_BLR
    if code == GGN_HQ:
        return FAC_GGN
    if code == MUM_BKC:
        return FAC_MUM
    west = {"MUM-AND", "PUN-HJ", "PUN-MG", "NAG", "NSK", "AHM-SG", "SUR", "VAD"}
    if code in west:
        return FAC_WEST
    # Faridabad has a local admin; company FACILITIES is placeholder so work redirects there
    if code == FARIDABAD:
        return ADMIN_FAR
    # Elsewhere: no local facilities mailbox → ADMIN_OPS
    return ADMIN_OPS


# --- structural ---

def test_matrix_has_thirty_branches_and_fallback_traps(session: Session, matrix):
    tid = matrix
    assert len(_branch_codes()) == 30
    # Dense local IT
    blr = find_place(session, tid, BLR_HQ)
    assert route_for(session, tid, "network", blr.location_id).recipients == [IT_BLR]
    # Partial Faridabad: IT climbs to North
    far = find_place(session, tid, FARIDABAD)
    assert route_for(session, tid, "network", far.location_id).recipients == [IT_NORTH]
    assert route_for(session, tid, "supplies", far.location_id).recipients == [ADMIN_FAR]
    # Sparse Ranchi: facilities → ADMIN_OPS (no real company facilities mailbox)
    ran = find_place(session, tid, RANCHI)
    route = route_for(session, tid, "plumbing", ran.location_id)
    assert route.recipients == [ADMIN_OPS]
    assert route.redirected_to_admin is True


# --- TC-01 .. TC-06 ---

def test_tc01_direct_local_match_bengaluru_it(session: Session, matrix):
    tid = matrix
    sender = "ramesh.it042@company.com"
    _request(
        session, tid, sender,
        "Projector not working in 4th Floor Boardroom",
        "Projector not working",
        {"type": "new_request", "category": "it_support", "summary": "Projector not working in boardroom",
         "details": {"location": "4th Floor Boardroom", "issue": "projector not working"}},
    )
    case = session.exec(select(Outcome)).one()
    assert BLR_HQ in (case.facts or {}).get("location_name", "") or "Bengaluru" in (case.facts or {}).get("location_name", "")
    orders = _orders(session, IT_BLR)
    assert len(orders) == 1
    assert _mails_to(session, sender), "ack / update to requester"


def test_tc02_upward_fallback_region_faridabad_it(session: Session, matrix):
    tid = matrix
    sender = "simran.hr112@company.com"
    _request(
        session, tid, sender,
        "Need VPN access and laptop charger",
        "VPN and Charger issue",
        {"type": "new_request", "category": "network", "summary": "VPN and laptop charger",
         "details": {"issue": "VPN disconnected, need charger"}},
    )
    assert len(_orders(session, IT_NORTH)) == 1
    assert not _orders(session, IT_GGN)
    assert not _orders(session, IT_BLR)


def test_tc03_upward_fallback_root_ranchi(session: Session, matrix):
    tid = matrix
    sender = "alok.ops301@company.com"
    _request(
        session, tid, sender,
        "Water dispenser leaking near reception",
        "Water dispenser leaking",
        {"type": "new_request", "category": "plumbing", "summary": "Water dispenser leaking",
         "details": {"location": "near reception", "issue": "leaking"}},
    )
    assert len(_orders(session, ADMIN_OPS)) == 1
    assert not _orders(session, FAC_WEST)
    assert not _orders(session, FAC_BLR)


def test_tc04_explicit_location_override_visitor_to_mumbai(session: Session, matrix):
    tid = matrix
    sender = "priya.fin88@company.com"  # home = Pune Hinjewadi
    _request(
        session, tid, sender,
        "Visiting Mumbai BKC today. Chair wheel broken at Hotdesk 12B",
        "Chair broken at BKC",
        {"type": "new_request", "category": "furniture", "summary": "Chair wheel broken at Hotdesk 12B",
         "details": {"location": "Mumbai BKC", "issue": "chair wheel broken at Hotdesk 12B"}},
    )
    case = session.exec(select(Outcome)).one()
    assert "Mumbai BKC" in (case.facts or {}).get("location_name", "")
    assert len(_orders(session, FAC_MUM)) == 1
    assert not _orders(session, FAC_WEST)


def test_tc05_missing_information_loop_catering(session: Session, matrix):
    tid = matrix
    sender = "vikram.mkt09@company.com"
    _request(
        session, tid, sender,
        "Need lunch catering for client meeting tomorrow",
        "Catering tomorrow",
        {"type": "new_request", "category": "catering", "summary": "Lunch catering for client meeting",
         "details": {"date": "tomorrow"}},
    )
    case = session.exec(select(Outcome)).one()
    assert case.facts.get("agent_stage") == "AWAITING_INFO"
    assert any("time" in str(q).lower() or "headcount" in str(q).lower() or "people" in str(q).lower()
               or "veg" in str(q).lower() or "dietary" in str(q).lower()
               for q in (case.facts.get("missing") or []) + [str(case.facts.get("missing") or "")])
    # No work order to cafeteria / facilities while waiting
    assert not [m for m in session.exec(select(Communication)).all() if "WORK ORDER" in (m.subject or "")]
    assert _mails_to(session, sender), "clarification to requester"


def test_tc06_employee_gate_rejection(session: Session, matrix):
    tid = matrix
    result = _request(
        session, tid, "spammer123@gmail.com",
        "Urgent: AC repair needed in Gurugram branch",
        "AC repair",
        {"type": "new_request", "category": "hvac", "summary": "AC repair", "details": {"location": "Gurugram"}},
    )
    assert result["status"] == "ignored_unknown_sender"
    assert not session.exec(select(Outcome)).all()
    assert not session.exec(select(Communication)).all()
    event = session.exec(select(RawEmailEvent)).one()
    assert event.safety_flags.get("ignored_unknown_sender") is True


def test_team_done_reply_closes_without_duplicate(session: Session, matrix):
    """Multi-turn: Faridabad IT request → North IT done → requester update, one case."""
    tid = matrix
    sender = "simran.hr112@company.com"
    _request(
        session, tid, sender,
        "Need VPN access and laptop charger",
        "VPN and Charger issue",
        {"type": "new_request", "category": "network", "summary": "VPN and charger",
         "details": {"issue": "VPN disconnected"}},
    )
    order = _orders(session, IT_NORTH)[0]
    case_ref = session.exec(select(Outcome)).one().case_reference
    _reply(session, tid, "Fixed. Charger delivered and VPN profile refreshed.", IT_NORTH, order,
           _reads("done", "Charger delivered and VPN refreshed"))
    cases = session.exec(select(Outcome)).all()
    assert len(cases) == 1
    assert cases[0].case_reference == case_ref
    assert cases[0].facts.get("agent_stage") in {"RESOLVED", "COMPLETED", "CLOSED"}
    assert any("VPN" in (m.subject or "") or "resolved" in (m.body or "").lower() or "Charger" in (m.body or "")
               for m in _mails_to(session, sender))


def test_edge_reopen_after_done_reuses_same_case(session: Session, matrix):
    """Employee says 'still not working' on a resolved thread → reopen same CASE-REF, alert technician."""
    tid = matrix
    sender = "ramesh.it042@company.com"
    _request(
        session, tid, sender,
        "Projector not working in 4th Floor Boardroom",
        "Projector not working",
        {"type": "new_request", "category": "it_support", "summary": "Projector not working",
         "details": {"location": "4th Floor Boardroom", "issue": "projector not working"}},
    )
    order = _orders(session, IT_BLR)[0]
    case = session.exec(select(Outcome)).one()
    case_ref = case.case_reference
    _reply(session, tid, "done, projector replaced", IT_BLR, order, _reads("done", "Projector replaced"))
    assert session.exec(select(Outcome)).one().facts.get("agent_stage") == "RESOLVED"

    before_orders = len(_orders(session, IT_BLR))
    _run(
        session, tid,
        _mail(
            session, tid,
            "Actually, it's still not working",
            sender=sender,
            subject=f"Re: Projector not working [{case_ref}]",
            thread=order.thread_id or order.conversation_id,
        ),
        _ai({"type": "update_case", "case_reference": case_ref, "details": {}}),
    )
    cases = session.exec(select(Outcome)).all()
    assert len(cases) == 1
    assert cases[0].case_reference == case_ref
    assert cases[0].facts.get("agent_stage") == "DISPATCHED"
    assert int(cases[0].facts.get("reopen_count") or 0) >= 1
    assert len(_orders(session, IT_BLR)) > before_orders
    assert any("Reopened" in (m.body or "") or "reopen" in (m.subject or "").lower() for m in _orders(session, IT_BLR))


def test_edge_duplicate_inbound_webhook_is_idempotent(session: Session, matrix):
    """Same Message-ID twice → one RawEmailEvent, one outcome, one work order."""
    from app.ai.service import LLMService
    from app.engine.pipeline import ProcessingPipeline
    from app.services.intake import IntakeService

    tid = matrix
    intake = IntakeService(session, tid)
    mid = "<dup-matrix-001@mock.local>"
    payload = dict(
        message_id=mid,
        thread_id=mid,
        sender="simran.hr112@company.com",
        recipients=["desk@inbound.company.com"],
        subject="VPN and Charger issue",
        body_text="Hi Admin, My VPN is disconnected and I need a replacement charger at my desk.",
        source="CLOUDMAILIN",
    )
    first = intake.ingest(**payload)
    second = intake.ingest(**payload)
    assert first["status"] == "queued"
    assert second["status"] == "deduplicated"
    assert first["event_id"] == second["event_id"]
    assert len(session.exec(select(RawEmailEvent)).all()) == 1

    provider = _ai(
        {"type": "new_request", "category": "network", "summary": "VPN and charger",
         "details": {"issue": "VPN disconnected"}},
    )
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(provider))
    pipeline.process_event(first["event_id"])
    pipeline.process_event(first["event_id"])  # retry must not double-dispatch
    assert len(session.exec(select(Outcome)).all()) == 1
    assert len(_orders(session, IT_NORTH)) == 1


def test_edge_ambiguous_delhi_office_asks_instead_of_home_branch(session: Session, matrix):
    """Faridabad employee says 'Delhi office' without a branch code → do not silently use Faridabad."""
    tid = matrix
    sender = "simran.hr112@company.com"
    _request(
        session, tid, sender,
        "Please check the printer at the Delhi office",
        "Printer issue",
        {"type": "new_request", "category": "printing", "summary": "Printer at Delhi office",
         "details": {"issue": "printer not working", "location": "Delhi office"}},
    )
    case = session.exec(select(Outcome)).one()
    stage = case.facts.get("agent_stage")
    location_name = case.facts.get("location_name") or ""
    # Prefer clarification; if a unique Delhi place matched, it must not be Faridabad home
    if stage == "AWAITING_INFO":
        ask = _mails_to(session, sender)[-1]
        assert "Which office" in ask.body or "office" in ask.body.lower()
        assert not _orders(session, ADMIN_FAR), "no Faridabad work order while office is unclear"
    else:
        assert "Faridabad" not in location_name
        assert "Delhi" in location_name or "Connaught" in location_name or "NCR" in location_name


# --- Parametrized 30-branch facilities bubble-up (routing layer — fast, no AI) ---

@pytest.mark.parametrize("branch_code", _branch_codes())
def test_facilities_routing_per_branch(session: Session, matrix, branch_code):
    tid = matrix
    place = find_place(session, tid, branch_code)
    assert place is not None, branch_code
    route = route_for(session, tid, "hvac", place.location_id)
    expected = _expected_facilities_mailbox(branch_code)
    assert route.recipients == [expected], f"{branch_code}: got {route.recipients} want {[expected]} ({route.department_code})"
