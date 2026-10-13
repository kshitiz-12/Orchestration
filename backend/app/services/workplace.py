"""Workplace seating + visitor journey completion (M02 / M09)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.company import VisitorPass
from app.models.org import Resource, utcnow


class WorkplaceService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def available_seats(self, *, location_id: Optional[str] = None) -> list[Resource]:
        stmt = select(Resource).where(
            Resource.tenant_id == self.tenant_id,
            Resource.type.in_(["SEAT", "DESK"]),
            Resource.status == "AVAILABLE",
        )
        if location_id:
            stmt = stmt.where(Resource.location_id == location_id)
        return list(self.session.exec(stmt).all())

    def allocate_seat(
        self,
        *,
        person_id: Optional[str] = None,
        location_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
    ) -> dict[str, Any]:
        seat = None
        if resource_id:
            seat = self.session.get(Resource, resource_id)
            if not seat or seat.tenant_id != self.tenant_id:
                raise HTTPException(status_code=404, detail="Seat not found")
            if (seat.status or "").upper() != "AVAILABLE":
                raise HTTPException(status_code=409, detail="Seat not available")
        else:
            seats = self.available_seats(location_id=location_id)
            if not seats:
                raise HTTPException(status_code=409, detail="No available seats")
            seat = seats[0]
        seat.status = "ALLOCATED"
        seat.allocated_to_person_id = person_id
        attrs = dict(seat.attributes or {})
        attrs["allocated_at"] = utcnow().isoformat()
        attrs["outcome_id"] = outcome_id
        seat.attributes = attrs
        seat.updated_at = utcnow()
        self.session.add(seat)
        self.session.commit()
        self.session.refresh(seat)
        return {
            "resource_id": seat.resource_id,
            "name": seat.name,
            "location_id": seat.location_id,
            "status": seat.status,
            "allocated_to_person_id": seat.allocated_to_person_id,
        }

    def release_seat(self, resource_id: str, *, reason: str = "released") -> dict[str, Any]:
        seat = self.session.get(Resource, resource_id)
        if not seat or seat.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Seat not found")
        seat.status = "AVAILABLE"
        seat.allocated_to_person_id = None
        attrs = dict(seat.attributes or {})
        attrs["released_at"] = utcnow().isoformat()
        attrs["release_reason"] = reason
        seat.attributes = attrs
        seat.updated_at = utcnow()
        self.session.add(seat)
        self.session.commit()
        return {"resource_id": resource_id, "status": "AVAILABLE", "reason": reason}

    def check_in_visitor(self, pass_id: str) -> VisitorPass:
        row = self.session.get(VisitorPass, pass_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Visitor pass not found")
        meta = dict(row.attributes or {})
        meta["checked_in_at"] = utcnow().isoformat()
        meta["journey_status"] = "CHECKED_IN"
        row.attributes = meta
        row.status = "CHECKED_IN"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def check_out_visitor(self, pass_id: str) -> VisitorPass:
        row = self.session.get(VisitorPass, pass_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Visitor pass not found")
        meta = dict(row.attributes or {})
        meta["checked_out_at"] = utcnow().isoformat()
        meta["journey_status"] = "CHECKED_OUT"
        row.attributes = meta
        row.status = "CHECKED_OUT"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def expire_open_passes(self) -> int:
        rows = self.session.exec(
            select(VisitorPass).where(
                VisitorPass.tenant_id == self.tenant_id,
                VisitorPass.status.in_(["REGISTERED", "ISSUED", "ACTIVE", "CHECKED_IN"]),
            )
        ).all()
        n = 0
        today = utcnow().date().isoformat()
        for row in rows:
            visit = row.visit_date
            if visit and str(visit)[:10] < today:
                row.status = "EXPIRED"
                row.updated_at = utcnow()
                self.session.add(row)
                n += 1
        if n:
            self.session.commit()
        return n
