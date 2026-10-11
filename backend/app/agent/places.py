"""The company's places as one tree (region > city > branch > building > floor ...) of any depth and size.

Teams, branch admins and settings hang off a place and cover everything below it, so routing walks up the tree
from where the work is until it finds someone.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from sqlmodel import Session, select

from app.models.org import Location, Person

# Rooms and desks can run into thousands; requests name a branch, building or city, never a room, to route.
ROUTABLE_TYPES = {"REGION", "COUNTRY", "STATE", "CITY", "CAMPUS", "BRANCH", "SITE", "BUILDING", "FLOOR"}
PLACE_TYPES = ROUTABLE_TYPES | {"ZONE", "ROOM", "DESK"}
_DETAIL_KEYS = ("branch", "office", "site", "location", "campus", "building", "city", "work_location")


def get_place(session: Session, tenant_id: str, location_id: Optional[str]) -> Optional[Location]:
    if not location_id:
        return None
    place = session.get(Location, location_id)
    return place if place is not None and place.tenant_id == tenant_id else None


def chain(session: Session, tenant_id: str, location_id: Optional[str]) -> list[Location]:
    """The place and everything above it, nearest first."""
    out: list[Location] = []
    seen: set[str] = set()
    place = get_place(session, tenant_id, location_id)
    while place is not None and place.location_id not in seen:
        out.append(place)
        seen.add(place.location_id)
        place = get_place(session, tenant_id, place.parent_id)
    return out


def chain_ids(session: Session, tenant_id: str, location_id: Optional[str]) -> list[str]:
    return [p.location_id for p in chain(session, tenant_id, location_id)]


def path_label(session: Session, tenant_id: str, location_id: Optional[str]) -> Optional[str]:
    """'Pune > Hinjewadi Tower', top-level region left out when there is more than one level."""
    names = [p.name for p in reversed(chain(session, tenant_id, location_id))]
    if len(names) > 2:
        names = names[1:]
    return " > ".join(names) or None


def aliases(place: Location) -> list[str]:
    return [a.strip() for a in re.split(r"[;,|]", place.alias or "") if a.strip()]


def _names(place: Location) -> list[str]:
    return [n for n in [place.name, place.code or "", *aliases(place)] if n and len(n.strip()) >= 2]


def routable_places(session: Session, tenant_id: str) -> list[Location]:
    rows = session.exec(select(Location).where(Location.tenant_id == tenant_id)).all()
    return [p for p in rows if (p.type or "").upper() in ROUTABLE_TYPES]


def offices(session: Session, tenant_id: str) -> list[Location]:
    """The places a requester would call 'my office' - branches, sites and campuses, else cities."""
    rows = routable_places(session, tenant_id)
    for kinds in ({"BRANCH", "SITE", "CAMPUS"}, {"CITY"}):
        found = [p for p in rows if (p.type or "").upper() in kinds]
        if found:
            return sorted(found, key=lambda p: p.name.lower())
    return []


def find_place(session: Session, tenant_id: str, text: str, places: Optional[list[Location]] = None) -> Optional[Location]:
    """The place a piece of text names. Exact name/code/alias first, then a whole-word mention.

    A longer name beats a shorter one ("Bengaluru Whitefield" over "Bengaluru"); at equal length the deeper place wins.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    rows = places if places is not None else routable_places(session, tenant_id)
    want = raw.lower()
    exact = [p for p in rows if any(n.lower() == want for n in _names(p))]
    if exact:
        return _most_specific(session, tenant_id, exact)
    best: Optional[Location] = None
    best_key: tuple[int, int] = (0, 0)
    for p in rows:
        for n in _names(p):
            if re.search(rf"(?<![\w-]){re.escape(n.lower())}(?![\w-])", want):
                key = (len(n), len(chain_ids(session, tenant_id, p.location_id)))
                if key > best_key:
                    best, best_key = p, key
    return best


def _most_specific(session: Session, tenant_id: str, rows: list[Location]) -> Location:
    return max(rows, key=lambda p: len(chain_ids(session, tenant_id, p.location_id)))


def _detail_texts(details: Optional[dict[str, Any]]) -> Iterable[str]:
    for key in _DETAIL_KEYS:
        value = (details or {}).get(key)
        if isinstance(value, str) and value.strip():
            yield value


_PLACE_HINT_STOP = {
    "office", "sector", "road", "park", "city", "floor", "tower", "campus", "branch",
    "north", "south", "east", "west", "region", "building", "desk", "room", "gate",
}


def _text_hints_other_place(
    session: Session,
    tenant_id: str,
    text: str,
    home: Location,
    places: list[Location],
) -> bool:
    """True when the mail names another city/branch (e.g. 'Delhi office') than the employee's home."""
    low = (text or "").lower()
    if not low.strip():
        return False
    home_blob = " ".join(_names(home)).lower()
    home_ids = set(chain_ids(session, tenant_id, home.location_id))
    for p in places:
        if p.location_id in home_ids:
            continue
        if (p.type or "").upper() not in {"CITY", "BRANCH", "SITE", "CAMPUS"}:
            continue
        for name in _names(p):
            for token in re.findall(r"[a-z]{4,}", name.lower()):
                if token in _PLACE_HINT_STOP or token in home_blob:
                    continue
                if re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", low):
                    return True
    return False


def place_for_request(
    session: Session,
    tenant_id: str,
    *,
    details: Optional[dict[str, Any]] = None,
    person: Optional[Person] = None,
    text: str = "",
) -> Optional[Location]:
    """Where the work is: place named in details/mail, else home — unless the mail hints a different office."""
    places = routable_places(session, tenant_id)
    if not places:
        return None
    for value in _detail_texts(details):
        found = find_place(session, tenant_id, value, places)
        if found is not None:
            return found
    text_place = find_place(session, tenant_id, text, places) if text else None
    if text_place is not None:
        return text_place
    home = get_place(session, tenant_id, person.site_id) if person is not None and person.site_id else None
    if home is not None and text and _text_hints_other_place(session, tenant_id, text, home, places):
        return None
    return home
