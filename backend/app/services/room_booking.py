"""Time-slot room bookings: holds, confirmations, overlap checks, expiry."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.org import Resource, RoomBooking, utcnow

ACTIVE_STATUSES = ("HELD", "CONFIRMED")
_UNUSABLE_ROOM_STATUSES = {"OUT_OF_SERVICE", "MAINTENANCE", "RETIRED", "INACTIVE"}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _today() -> date:
    return utcnow().date()


def _roll_year(month: int, day: int, year: Optional[int], today: date) -> Optional[date]:
    try:
        if year:
            return date(year if year > 100 else 2000 + year, month, day)
        candidate = date(today.year, month, day)
        # A date well in the past without a year means next year's occurrence
        if candidate < today - timedelta(days=30):
            candidate = date(today.year + 1, month, day)
        return candidate
    except ValueError:
        return None


def parse_meeting_date(text: Any, *, today: Optional[date] = None) -> Optional[date]:
    """'26th Sep', '22 September 2026', '25/10', 'tomorrow', 'friday', '2026-09-26' → date."""
    raw = str(text or "").strip().lower()
    if not raw:
        return None
    today = today or _today()

    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    if "day after tomorrow" in raw:
        return today + timedelta(days=2)
    if re.search(r"\b(tomorrow|tmrw|tmr|kal)\b", raw):
        return today + timedelta(days=1)
    if re.search(r"\b(today|aaj)\b", raw):
        return today

    month_names = "|".join(_MONTHS)
    m = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({month_names})[a-z]*\.?,?\s*(\d{{2,4}})?\b",
        raw,
    )
    if m:
        return _roll_year(_MONTHS[m.group(2)], int(m.group(1)), int(m.group(3)) if m.group(3) else None, today)
    m = re.search(
        rf"\b({month_names})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s*(\d{{4}})?\b",
        raw,
    )
    if m:
        return _roll_year(_MONTHS[m.group(1)], int(m.group(2)), int(m.group(3)) if m.group(3) else None, today)

    m = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", raw)
    if m:
        # Indian convention: day/month
        return _roll_year(int(m.group(2)), int(m.group(1)), int(m.group(3)) if m.group(3) else None, today)

    m = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", raw)
    if m:
        delta = (_WEEKDAYS[m.group(1)] - today.weekday()) % 7 or 7
        return today + timedelta(days=delta)
    return None


def parse_clock(text: Any, *, default_pm_below: int = 8) -> Optional[time]:
    """'9.30 a. M', '9:30 AM', '2pm', '14:00', 'noon', '10' → time."""
    raw = str(text or "").strip().lower()
    if not raw:
        return None
    if "noon" in raw:
        return time(12, 0)
    if "midnight" in raw:
        return time(0, 0)
    squashed = re.sub(r"([ap])\s*\.?\s*m\b\.?", r"\1m", raw)
    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", squashed)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    meridiem = m.group(3)
    if hour > 23 or minute > 59:
        return None
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    elif not meridiem and 1 <= hour < default_pm_below:
        hour += 12
    return time(hour, minute)


def meeting_window(facts: dict[str, Any], *, with_buffers: bool = True) -> Optional[tuple[datetime, datetime]]:
    """Occupied window for the meeting (plus setup/release buffers). None when the date is unknown."""
    day = parse_meeting_date(facts.get("date"))
    if not day:
        return None
    start_t = parse_clock(facts.get("preferred_time") or facts.get("time_window"))
    if not start_t:
        start, end = datetime.combine(day, time(0, 0)), datetime.combine(day, time(23, 59))
    else:
        start = datetime.combine(day, start_t)
        end_t = parse_clock(facts.get("end_time"))
        end = datetime.combine(day, end_t) if end_t else None
        if end is not None and end <= start:
            end = None
        if end is None:
            try:
                hours = float(facts.get("duration_hours") or 1)
            except (TypeError, ValueError):
                hours = 1.0
            end = start + timedelta(hours=max(hours, 0.25))
    if with_buffers:
        try:
            start -= timedelta(minutes=int(facts.get("setup_buffer_minutes") or 0))
            end += timedelta(minutes=int(facts.get("release_buffer_minutes") or 0))
        except (TypeError, ValueError):
            pass
    return start, end


class RoomBookingService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    # ---------- queries
    def active_for_outcome(self, outcome_id: str) -> list[RoomBooking]:
        return list(
            self.session.exec(
                select(RoomBooking).where(
                    RoomBooking.tenant_id == self.tenant_id,
                    RoomBooking.outcome_id == outcome_id,
                    RoomBooking.status.in_(ACTIVE_STATUSES),  # type: ignore[attr-defined]
                )
            ).all()
        )

    def conflicts(
        self,
        resource_id: str,
        window: Optional[tuple[datetime, datetime]],
        *,
        exclude_outcome_id: Optional[str] = None,
    ) -> list[RoomBooking]:
        if window is None:
            return []
        start, end = window
        now = utcnow()
        rows = self.session.exec(
            select(RoomBooking).where(
                RoomBooking.tenant_id == self.tenant_id,
                RoomBooking.resource_id == resource_id,
                RoomBooking.status.in_(ACTIVE_STATUSES),  # type: ignore[attr-defined]
                RoomBooking.starts_at < end,  # type: ignore[operator]
                RoomBooking.ends_at > start,  # type: ignore[operator]
            )
        ).all()
        out = []
        for row in rows:
            if exclude_outcome_id and row.outcome_id == exclude_outcome_id:
                continue
            if row.status == "HELD" and row.hold_expires_at and row.hold_expires_at <= now:
                continue
            out.append(row)
        return out

    def is_free(self, room: Resource, window, *, exclude_outcome_id: Optional[str] = None) -> bool:
        if (room.status or "").upper() in _UNUSABLE_ROOM_STATUSES:
            return False
        return not self.conflicts(room.resource_id, window, exclude_outcome_id=exclude_outcome_id)

    def free_rooms(
        self,
        rooms: Iterable[Resource],
        window,
        *,
        exclude_outcome_id: Optional[str] = None,
    ) -> list[Resource]:
        return [r for r in rooms if self.is_free(r, window, exclude_outcome_id=exclude_outcome_id)]

    # ---------- writes
    def release_for_outcome(self, outcome_id: str, *, status: str = "RELEASED", only_held: bool = False) -> int:
        count = 0
        for row in self.active_for_outcome(outcome_id):
            if only_held and row.status != "HELD":
                continue
            row.status = status
            row.updated_at = utcnow()
            self.session.add(row)
            count += 1
        return count

    def hold(
        self,
        *,
        outcome_id: str,
        room_name: str,
        window,
        resource_id: Optional[str] = None,
        is_offsite: bool = False,
        attributes: Optional[dict] = None,
        release_prior: bool = True,
    ) -> RoomBooking:
        if release_prior:
            self.release_for_outcome(outcome_id, only_held=True)
        hours = float(get_settings().proposal_hold_hours or 24)
        booking = RoomBooking(
            tenant_id=self.tenant_id,
            resource_id=resource_id,
            outcome_id=outcome_id,
            room_name=room_name,
            status="HELD",
            starts_at=window[0] if window else None,
            ends_at=window[1] if window else None,
            hold_expires_at=utcnow() + timedelta(hours=hours),
            is_offsite=is_offsite,
            attributes=attributes or {},
        )
        self.session.add(booking)
        self.session.flush()
        return booking

    def confirm(
        self,
        *,
        outcome_id: str,
        room_name: str,
        window,
        resource_id: Optional[str] = None,
        is_offsite: bool = False,
        attributes: Optional[dict] = None,
        keep: Optional[set[str]] = None,
    ) -> RoomBooking:
        """Confirm one room. Other active rows for the outcome are released unless listed in `keep`."""
        existing = next(
            (
                b
                for b in self.active_for_outcome(outcome_id)
                if b.resource_id == resource_id and b.room_name == room_name
            ),
            None,
        )
        if existing is None:
            # Revive an expired hold on the same room rather than creating a duplicate row
            existing = self.session.exec(
                select(RoomBooking).where(
                    RoomBooking.tenant_id == self.tenant_id,
                    RoomBooking.outcome_id == outcome_id,
                    RoomBooking.room_name == room_name,
                    RoomBooking.status == "EXPIRED",
                )
            ).first()
        for other in self.active_for_outcome(outcome_id):
            if other is not existing and other.booking_id not in (keep or set()):
                other.status = "RELEASED"
                self.session.add(other)
        if existing is None:
            existing = RoomBooking(
                tenant_id=self.tenant_id,
                resource_id=resource_id,
                outcome_id=outcome_id,
                room_name=room_name,
                is_offsite=is_offsite,
            )
        existing.status = "CONFIRMED"
        existing.hold_expires_at = None
        if window:
            existing.starts_at, existing.ends_at = window
        existing.attributes = {**(existing.attributes or {}), **(attributes or {})}
        existing.updated_at = utcnow()
        self.session.add(existing)
        self.session.flush()
        return existing
