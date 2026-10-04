"""Companies with many branches: work goes to the team covering the place, falling back up the tree."""

from sqlmodel import Session, select

from app.agent.directory import catalogue, find_department, route_for
from app.agent.importer import run_import
from app.agent.places import find_place, path_label, place_for_request
from app.models.company import Department
from app.models.org import Location, Person
from test_admin_desk import _mail, _mails_to, _run
from test_live_directory import ADMIN, EMP, FAC, _ai, _case, _orders, live  # noqa: F401

PUNE_FAC = "facilities.pune@acme.demo"
PUNE_ADMIN = "admin.pune@acme.demo"
BLR_IT = "it.blr@acme.demo"


def _tree(session: Session, tid: str) -> dict[str, Location]:
    """West > Pune > Pune Hinjewadi (+ Tower B), South > Bengaluru > Whitefield, and an empty Chennai branch."""
    rows = [
        {"code": "WEST", "name": "West", "type": "REGION"},
        {"code": "SOUTH", "name": "South", "type": "REGION"},
        {"code": "PUN", "name": "Pune", "type": "CITY", "parent_code": "WEST"},
        {"code": "PUN-HJ", "name": "Pune Hinjewadi", "type": "BRANCH", "parent_code": "PUN", "aliases": "Hinjewadi; Pune office"},
        {"code": "PUN-HJ-B", "name": "Tower B", "type": "BUILDING", "parent_code": "PUN-HJ"},
        {"code": "BLR", "name": "Bengaluru", "type": "CITY", "parent_code": "SOUTH"},
        {"code": "BLR-WF", "name": "Bengaluru Whitefield", "type": "BRANCH", "parent_code": "BLR", "aliases": "Whitefield"},
        {"code": "CHN", "name": "Chennai", "type": "BRANCH", "parent_code": "SOUTH"},
    ]
    # Children listed before parents on purpose: the import sorts it out.
    result = run_import(session, tid, "locations", list(reversed(rows)), commit=True)
    assert result["errors"] == [] and result["new"] == len(rows)
    return {p.code: p for p in session.exec(select(Location).where(Location.code.is_not(None))).all()}


def _team(session, tid, code, name, cats, email, place: Location, approver=None):
    dept = Department(tenant_id=tid, code=code, name=name, categories=cats, primary_email=email,
                      approver_email=approver, location_id=place.location_id)
    session.add(dept)
    session.commit()
    return dept


def test_tree_lookup_and_labels(session: Session, live):
    tid = live
    t = _tree(session, tid)
    assert find_place(session, tid, "Hinjewadi").code == "PUN-HJ"
    assert find_place(session, tid, "pun-hj").code == "PUN-HJ"
    assert find_place(session, tid, "AC broken at our Whitefield office").code == "BLR-WF"
    assert find_place(session, tid, "Bengaluru Whitefield, 3rd floor").code == "BLR-WF", "longest name wins"
    assert find_place(session, tid, "Pune").code == "PUN"
    assert find_place(session, tid, "computer") is None
    assert path_label(session, tid, t["PUN-HJ-B"].location_id) == "Pune > Pune Hinjewadi > Tower B"


def test_place_comes_from_details_then_home_branch_then_mail_text(session: Session, live):
    tid = live
    t = _tree(session, tid)
    person = Person(tenant_id=tid, email="traveller@acme.demo", name="T", site_id=t["PUN-HJ"].location_id)
    session.add(person)
    session.commit()
    visiting = place_for_request(session, tid, details={"location": "Whitefield"}, person=person, text="")
    assert visiting.code == "BLR-WF", "a place named in the request beats the home branch"
    assert place_for_request(session, tid, details={"location": "3rd floor"}, person=person).code == "PUN-HJ"
    assert place_for_request(session, tid, details={}, person=None, text="lights out in Chennai").code == "CHN"
    assert place_for_request(session, tid, details={}, person=None, text="lights out") is None


def test_nearest_team_wins_and_empty_branches_fall_back_up_the_tree(session: Session, live):
    tid = live
    t = _tree(session, tid)
    _team(session, tid, "FACILITIES_PUN", "Facilities - Pune", ["maintenance", "hvac"], PUNE_FAC, t["PUN"])
    _team(session, tid, "IT_BLR", "IT - Bengaluru", [], BLR_IT, t["BLR"])

    assert route_for(session, tid, "maintenance", t["PUN-HJ-B"].location_id).recipients == [PUNE_FAC]
    assert route_for(session, tid, "maintenance", t["PUN"].location_id).recipients == [PUNE_FAC]
    assert route_for(session, tid, "maintenance", t["BLR-WF"].location_id).recipients == [FAC], "no Bengaluru team"
    assert route_for(session, tid, "maintenance", t["CHN"].location_id).recipients == [FAC]
    assert route_for(session, tid, "maintenance").recipients == [FAC], "unknown place = company-wide team"
    it = route_for(session, tid, "it_support", t["BLR-WF"].location_id)
    assert it.department_code == "IT_BLR" and it.recipients == [BLR_IT], "team named after the usual owner, no list"


def test_branch_admin_covers_its_branch_only(session: Session, live):
    tid = live
    t = _tree(session, tid)
    _team(session, tid, "ADMIN_PUN", "Admin - Pune", [], PUNE_ADMIN, t["PUN"], approver=PUNE_ADMIN)
    pune = route_for(session, tid, "pest_control", t["PUN-HJ"].location_id)
    assert pune.local_admins == [PUNE_ADMIN]
    assert pune.approver in {PUNE_ADMIN, FAC}
    blr = route_for(session, tid, "pest_control", t["BLR-WF"].location_id)
    assert blr.local_admins == []
    unknown = route_for(session, tid, "no_such_service_xyz", t["PUN-HJ"].location_id)
    assert unknown.recipients == [PUNE_ADMIN], "work nobody handles goes to the branch admin, not head office"


def test_reroute_by_name_picks_the_branch_team(session: Session, live):
    tid = live
    t = _tree(session, tid)
    _team(session, tid, "FACILITIES_PUN", "Facilities - Pune", ["maintenance"], PUNE_FAC, t["PUN"])
    assert find_department(session, tid, "facilities", t["PUN-HJ"].location_id).code == "FACILITIES_PUN"
    assert find_department(session, tid, "facilities", t["BLR-WF"].location_id).code == "FACILITIES"
    assert find_department(session, tid, "FACILITIES_PUN").code == "FACILITIES_PUN"


def test_ai_catalogue_does_not_grow_with_branches(session: Session, live):
    tid = live
    t = _tree(session, tid)
    before = len(catalogue(session, tid))
    for code in ("PUN", "BLR", "CHN"):
        _team(session, tid, f"FACILITIES_{code}", f"Facilities - {code}", ["maintenance", "hvac"],
              f"fac.{code.lower()}@acme.demo", t[code])
    assert len(catalogue(session, tid)) <= before + 1


def test_mail_from_pune_employee_reaches_the_pune_team(session: Session, live):
    tid = live
    t = _tree(session, tid)
    _team(session, tid, "FACILITIES_PUN", "Facilities - Pune", ["maintenance", "hvac"], PUNE_FAC, t["PUN"])
    _team(session, tid, "ADMIN_PUN", "Admin - Pune", [], PUNE_ADMIN, t["PUN"])
    emp = session.exec(select(Person).where(Person.email == EMP)).first()
    if emp is None:
        emp = Person(tenant_id=tid, email=EMP, name="Rohan Mehta")
    emp.site_id = t["PUN-HJ"].location_id
    session.add(emp)
    session.commit()

    _run(session, tid, _mail(session, tid, "The AC on our floor is not cooling.", sender=EMP, subject="AC not cooling"), _ai(
        {"type": "new_request", "category": "hvac", "summary": "AC not cooling", "details": {"location": "4th floor"}}
    ))
    case = _case(session)
    assert case.facts["location_id"] == t["PUN-HJ"].location_id
    assert case.facts["location_name"] == "Pune > Pune Hinjewadi"
    orders = _orders(session, PUNE_FAC)
    assert len(orders) == 1 and "Location: Pune > Pune Hinjewadi" in orders[0].body
    assert not _orders(session, FAC), "head-office facilities must not get a Pune job"


def test_visiting_employee_is_served_by_the_branch_they_name(session: Session, live):
    tid = live
    t = _tree(session, tid)
    _team(session, tid, "FACILITIES_PUN", "Facilities - Pune", ["maintenance", "hvac"], PUNE_FAC, t["PUN"])
    _team(session, tid, "FACILITIES_BLR", "Facilities - Bengaluru", ["maintenance", "hvac"], "fac.blr@acme.demo", t["BLR"])
    emp = session.exec(select(Person).where(Person.email == EMP)).first() or Person(tenant_id=tid, email=EMP, name="Rohan")
    emp.site_id = t["PUN-HJ"].location_id
    session.add(emp)
    session.commit()

    _run(session, tid, _mail(session, tid, "I'm at Whitefield this week - the meeting room AC is dead.", sender=EMP,
                             subject="AC"), _ai(
        {"type": "new_request", "category": "hvac", "summary": "AC not working", "details": {"location": "Whitefield"}}
    ))
    assert _orders(session, "fac.blr@acme.demo") and not _orders(session, PUNE_FAC)


def test_import_people_and_teams_onto_branches(session: Session, live):
    tid = live
    t = _tree(session, tid)
    res = run_import(session, tid, "employees", [
        {"email": "a.one@acme.demo", "name": "A One", "location": "PUN-HJ"},
        {"email": "b.two@acme.demo", "name": "B Two", "location": "Bengaluru Whitefield"},
        {"email": "c.three@acme.demo", "name": "C Three", "location": "Atlantis"},
    ], commit=True)
    assert res["new"] == 2 and res["errors"][0]["row"] == 4 and "Atlantis" in res["errors"][0]["error"]
    a = session.exec(select(Person).where(Person.email == "a.one@acme.demo")).one()
    assert a.site_id == t["PUN-HJ"].location_id

    res = run_import(session, tid, "departments", [
        {"code": "FACILITIES_CHN", "name": "Facilities - Chennai", "categories": "maintenance; hvac",
         "primary_email": "fac.chn@acme.demo", "location": "CHN"},
    ], commit=True)
    assert res["errors"] == []
    assert route_for(session, tid, "hvac", t["CHN"].location_id).recipients == ["fac.chn@acme.demo"]


def test_locations_preview_saves_nothing(session: Session, live):
    tid = live
    res = run_import(session, tid, "locations", [
        {"code": "NORTH", "name": "North", "type": "REGION"},
        {"code": "DEL", "name": "Delhi", "type": "CITY", "parent_code": "NORTH"},
    ], commit=False)
    assert res["new"] == 2 and res["errors"] == []
    assert session.exec(select(Location).where(Location.code == "DEL")).first() is None


def test_setup_api_manages_places_and_team_scope(client, auth_headers):
    h = auth_headers
    west = client.post("/api/v1/setup/locations", json={"name": "West", "type": "REGION", "code": "west"}, headers=h)
    assert west.status_code == 200, west.text
    pune = client.post("/api/v1/setup/locations", headers=h, json={
        "name": "Pune", "type": "BRANCH", "code": "PUN", "parent_id": west.json()["location_id"], "aliases": "Pune office"})
    assert pune.status_code == 200 and pune.json()["path"] == "West > Pune"
    dup = client.post("/api/v1/setup/locations", json={"name": "Other", "code": "PUN"}, headers=h)
    assert dup.status_code == 409
    loop = client.patch(f"/api/v1/setup/locations/{west.json()['location_id']}",
                        json={"parent_id": pune.json()["location_id"]}, headers=h)
    assert loop.status_code == 422

    team = client.post("/api/v1/setup/departments", headers=h, json={
        "code": "FACILITIES_PUN", "name": "Facilities - Pune", "categories": ["maintenance"],
        "primary_email": "fac.pune@acme.demo", "location_id": pune.json()["location_id"]})
    assert team.status_code == 200 and team.json()["location_name"] == "West > Pune"

    listing = client.get("/api/v1/setup/locations", headers=h).json()
    row = next(i for i in listing["items"] if i["code"] == "PUN")
    assert row["teams"] == 1
    blocked = client.delete(f"/api/v1/setup/locations/{row['location_id']}", headers=h)
    assert blocked.status_code == 409 and "1 teams" in blocked.json()["detail"]
    client.patch(f"/api/v1/setup/departments/{team.json()['department_id']}", json={"location_id": ""}, headers=h)
    assert client.delete(f"/api/v1/setup/locations/{row['location_id']}", headers=h).status_code == 200
