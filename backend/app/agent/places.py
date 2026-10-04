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


def place_for_request(
    session: Session,
    tenant_id: str,
    *,
    details: Optional[dict[str, Any]] = None,
    person: Optional[Person] = None,
    text: str = "",
) -> Optional[Location]:
    """Where the work is: a place named in the request details, else the requester's base, else one named in the mail."""
    places = routable_places(session, tenant_id)
    if not places:
        return None
    for value in _detail_texts(details):
        found = find_place(session, tenant_id, value, places)
        if found is not None:
            return found
    if person is not None and person.site_id:
        home = get_place(session, tenant_id, person.site_id)
        if home is not None:
            return home
    return find_place(session, tenant_id, text, places) if text else None
