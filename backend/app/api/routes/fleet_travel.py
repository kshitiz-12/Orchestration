"""Fleet + travel itinerary APIs (M11/M12)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import DashboardOpsDep, SessionDep, TenantDep
from app.services.fleet_travel import FleetTravelService

router = APIRouter(tags=["fleet-travel"])


class VehicleIn(BaseModel):
    registration: str
    vehicle_type: str = "CAB"
    capacity: int = 4


class TripIn(BaseModel):
    rider_email: str
    pickup: str
    dropoff: str
    scheduled_at: Optional[str] = None
    outcome_id: Optional[str] = None
    rate_amount: float = 0.0


class ItineraryIn(BaseModel):
    traveller_email: str
    purpose: Optional[str] = None
    outcome_id: Optional[str] = None
    emergency_contact: Optional[str] = None
    segments: list[Any] = Field(default_factory=list)


@router.post("/fleet/vehicles")
def add_vehicle(body: VehicleIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    v = FleetTravelService(session, tenant_id).register_vehicle(**body.model_dump())
    return {"vehicle_id": v.vehicle_id, "registration": v.registration, "status": v.status}


@router.post("/fleet/trips")
def trip(body: TripIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    t = FleetTravelService(session, tenant_id).request_trip(**body.model_dump())
    return {"trip_id": t.trip_id, "status": t.status, "vehicle_id": t.vehicle_id}


@router.post("/fleet/trips/{trip_id}/complete")
def complete_trip(trip_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    t = FleetTravelService(session, tenant_id).complete_trip(trip_id)
    return {"trip_id": t.trip_id, "status": t.status}


@router.post("/travel/itineraries")
def itinerary(body: ItineraryIn, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = FleetTravelService(session, tenant_id).create_itinerary(**body.model_dump())
    return {
        "itinerary_id": row.itinerary_id,
        "status": row.status,
        "duty_of_care": row.duty_of_care,
    }


@router.post("/travel/itineraries/{itinerary_id}/book")
def book(itinerary_id: str, session: SessionDep, tenant_id: TenantDep, _: DashboardOpsDep) -> dict[str, Any]:
    row = FleetTravelService(session, tenant_id).mark_booked(itinerary_id)
    return {"itinerary_id": row.itinerary_id, "status": row.status}
