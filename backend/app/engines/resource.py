"""Resource reservation engine — conflict-safe holds (rooms / assets)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.org import Resource, RoomBooking, utcnow


@dataclass
class ReservationResult:
    ok: bool
    booking_id: Optional[str] = None
    status: str = ""
    reason: str = ""


class ResourceEngine:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def _overlaps(
        self,
        *,
        resource_id: str,
        starts_at: datetime,
        ends_at: datetime,
        exclude_booking_id: Optional[str] = None,
    ) -> bool:
        rows = self.session.exec(
            select(RoomBooking).where(
                RoomBooking.tenant_id == self.tenant_id,
                RoomBooking.resource_id == resource_id,
                RoomBooking.status.in_(["HELD", "CONFIRMED"]),
            )
        ).all()
        for b in rows:
            if exclude_booking_id and b.booking_id == exclude_booking_id:
                continue
            if not b.starts_at or not b.ends_at:
                continue
            if b.starts_at < ends_at and starts_at < b.ends_at:
                return True
        return False

    def hold(
        self,
        *,
        resource_id: str,
        room_name: str,
        starts_at: datetime,
        ends_at: datetime,
        outcome_id: Optional[str] = None,
        hold_minutes: int = 30,
    ) -> ReservationResult:
        if ends_at <= starts_at:
            raise HTTPException(status_code=400, detail="ends_at must be after starts_at")
        resource = self.session.get(Resource, resource_id)
        if not resource or resource.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Resource not found")
        if self._overlaps(resource_id=resource_id, starts_at=starts_at, ends_at=ends_at):
            return ReservationResult(ok=False, status="CONFLICT", reason="Resource already held/confirmed in window")
        from datetime import timedelta

        booking = RoomBooking(
            tenant_id=self.tenant_id,
            resource_id=resource_id,
            outcome_id=outcome_id,
            room_name=room_name or resource.name,
            status="HELD",
            starts_at=starts_at,
            ends_at=ends_at,
            hold_expires_at=utcnow() + timedelta(minutes=hold_minutes),
        )
        self.session.add(booking)
        self.session.commit()
        self.session.refresh(booking)
        return ReservationResult(ok=True, booking_id=booking.booking_id, status="HELD", reason="Hold created")

    def confirm(self, booking_id: str) -> ReservationResult:
        booking = self.session.get(RoomBooking, booking_id)
        if not booking or booking.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking.resource_id and booking.starts_at and booking.ends_at:
            if self._overlaps(
                resource_id=booking.resource_id,
                starts_at=booking.starts_at,
                ends_at=booking.ends_at,
                exclude_booking_id=booking.booking_id,
            ):
                return ReservationResult(ok=False, booking_id=booking_id, status="CONFLICT", reason="Conflict on confirm")
        booking.status = "CONFIRMED"
        booking.hold_expires_at = None
        booking.updated_at = utcnow()
        self.session.add(booking)
        self.session.commit()
        return ReservationResult(ok=True, booking_id=booking_id, status="CONFIRMED", reason="Confirmed")

    def release(self, booking_id: str, *, status: str = "RELEASED") -> ReservationResult:
        booking = self.session.get(RoomBooking, booking_id)
        if not booking or booking.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Booking not found")
        booking.status = status
        booking.updated_at = utcnow()
        self.session.add(booking)
        self.session.commit()
        return ReservationResult(ok=True, booking_id=booking_id, status=status, reason="Released")
