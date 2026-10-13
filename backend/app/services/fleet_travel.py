"""Fleet / cab trips + travel duty-of-care stubs with real persisted records (M11/M12)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, Session, select

from app.models.org import TimestampMixin, new_id, utcnow
from app.services.outbox import OutboxService


class FleetVehicle(TimestampMixin, table=True):
    __tablename__ = "fleet_vehicles"

    vehicle_id: str = Field(default_factory=lambda: new_id("veh_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    registration: str = Field(index=True)
    vehicle_type: str = "CAB"  # CAB | BUS | OWNED
    capacity: int = 4
    status: str = "AVAILABLE"  # AVAILABLE | ON_TRIP | MAINTENANCE | RETIRED
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class TripRecord(TimestampMixin, table=True):
    __tablename__ = "trip_records"

    trip_id: str = Field(default_factory=lambda: new_id("trp_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    vehicle_id: Optional[str] = Field(default=None, foreign_key="fleet_vehicles.vehicle_id")
    rider_email: Optional[str] = None
    pickup: Optional[str] = None
    dropoff: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: str = "REQUESTED"  # REQUESTED | ASSIGNED | COMPLETED | CANCELLED
    rate_amount: float = 0.0
    currency: str = "INR"
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class TravelItinerary(TimestampMixin, table=True):
    __tablename__ = "travel_itineraries"

    itinerary_id: str = Field(default_factory=lambda: new_id("itn_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    traveller_email: str
    purpose: Optional[str] = None
    segments: list = Field(default_factory=list, sa_column=Column(JSON))
    duty_of_care: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "DRAFT"  # DRAFT | APPROVED | BOOKED | IN_TRIP | CLOSED | CANCELLED
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class FleetTravelService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def register_vehicle(self, *, registration: str, vehicle_type: str = "CAB", capacity: int = 4) -> FleetVehicle:
        row = FleetVehicle(
            tenant_id=self.tenant_id,
            registration=registration.strip().upper(),
            vehicle_type=vehicle_type.strip().upper(),
            capacity=capacity,
            status="AVAILABLE",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def request_trip(
        self,
        *,
        rider_email: str,
        pickup: str,
        dropoff: str,
        scheduled_at: Optional[str] = None,
        outcome_id: Optional[str] = None,
        rate_amount: float = 0.0,
    ) -> TripRecord:
        vehicle = self.session.exec(
            select(FleetVehicle).where(
                FleetVehicle.tenant_id == self.tenant_id,
                FleetVehicle.status == "AVAILABLE",
            )
        ).first()
        trip = TripRecord(
            tenant_id=self.tenant_id,
            outcome_id=outcome_id,
            vehicle_id=vehicle.vehicle_id if vehicle else None,
            rider_email=rider_email.strip().lower(),
            pickup=pickup,
            dropoff=dropoff,
            scheduled_at=scheduled_at,
            status="ASSIGNED" if vehicle else "REQUESTED",
            rate_amount=rate_amount,
        )
        if vehicle:
            vehicle.status = "ON_TRIP"
            vehicle.updated_at = utcnow()
            self.session.add(vehicle)
        self.session.add(trip)
        self.session.commit()
        self.session.refresh(trip)
        return trip

    def complete_trip(self, trip_id: str) -> TripRecord:
        trip = self.session.get(TripRecord, trip_id)
        if not trip or trip.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Trip not found")
        trip.status = "COMPLETED"
        trip.updated_at = utcnow()
        if trip.vehicle_id:
            vehicle = self.session.get(FleetVehicle, trip.vehicle_id)
            if vehicle:
                vehicle.status = "AVAILABLE"
                vehicle.updated_at = utcnow()
                self.session.add(vehicle)
        self.session.add(trip)
        self.session.commit()
        self.session.refresh(trip)
        return trip

    def create_itinerary(
        self,
        *,
        traveller_email: str,
        segments: Optional[list] = None,
        purpose: Optional[str] = None,
        outcome_id: Optional[str] = None,
        emergency_contact: Optional[str] = None,
    ) -> TravelItinerary:
        row = TravelItinerary(
            tenant_id=self.tenant_id,
            outcome_id=outcome_id,
            traveller_email=traveller_email.strip().lower(),
            purpose=purpose,
            segments=segments or [],
            duty_of_care={
                "emergency_contact": emergency_contact,
                "check_in_required": True,
                "risk_flag": False,
            },
            status="DRAFT",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="TRAVEL.ITINERARY_CREATED",
            payload={"itinerary_id": row.itinerary_id, "traveller": row.traveller_email},
            idempotency_key=f"itn-{row.itinerary_id}",
            aggregate_type="TravelItinerary",
            aggregate_id=row.itinerary_id,
        )
        return row

    def mark_booked(self, itinerary_id: str) -> TravelItinerary:
        row = self.session.get(TravelItinerary, itinerary_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        row.status = "BOOKED"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row
