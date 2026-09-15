"""Canonical meeting-room requirement state — the decision surface for orchestration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.services.meeting_room import PRIMARY_OFFICE_HINT, _answered, catering_needed


class Provenance(str, Enum):
    UNKNOWN = "unknown"
    CANDIDATE_HEURISTIC = "candidate_heuristic"
    SYSTEM = "system"
    INFERRED_POLICY = "inferred_policy"
    MASTER = "master"
    EXTRACTED = "extracted"
    USER_CONFIRMED = "user_confirmed"


FIELD_PROVENANCE_RANK: dict[Provenance, int] = {
    Provenance.UNKNOWN: 0,
    Provenance.CANDIDATE_HEURISTIC: 1,
    Provenance.SYSTEM: 2,
    Provenance.INFERRED_POLICY: 3,
    Provenance.MASTER: 4,
    Provenance.EXTRACTED: 5,
    Provenance.USER_CONFIRMED: 6,
}


class VisitorNeed(str, Enum):
    """Visitor requirement without inventing a headcount."""

    UNKNOWN = "unknown"
    NONE = "none"
    INDICATED = "indicated"  # yes, count unknown
    COUNT_ONLY = "count_only"
    NAMED = "named"


class MeetingStage(str, Enum):
    REGISTERED = "REGISTERED"
    AWAITING_REQUIREMENTS = "AWAITING_REQUIREMENTS"
    SEARCHING = "SEARCHING"
    PROPOSED = "PROPOSED"
    AUTO_BOOKED = "AUTO_BOOKED"
    NO_RESOURCE = "NO_RESOURCE"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"


REQUIREMENT_FIELDS = (
    "attendees",
    "date",
    "preferred_time",
    "end_time",
    "duration_hours",
    "meeting_type",
    "location_preference",
    "hybrid_av",
    "presentation_display",
    "catering",
    "dietary",
    "special_access",
    "external_visitors",
    "external_visitors_indicated",
    "visitor_details",
    "guest_vehicles",
    "vehicle_numbers",
    "confidentiality",
)

# Keys the reducer must never drop from persistence
PLATFORM_KEYS = (
    "registration_ack_sent",
    "primary_office",
    "operational_status",
    "financial_status",
    "operational_readiness_pct",
    "pending_confirmation",
    "proposed_room",
    "booked_room",
    "policy_assumptions",
    "defaults_applied",
    "execution_plan",
    "auto_booked_low_risk",
    "orchestration_stage",
    "field_provenance",
    "speech_acts",
    "needs_ops",
    "auto_book_skipped",
    "hold_start",
    "hold_end",
    "setup_buffer_minutes",
    "release_buffer_minutes",
    "recommended_room",
    "room_scores",
    "outbound_required",
    "last_action",
    "booking_confirmed",
    "employee_satisfied",
    "time_window",
    "checklist_missing",
    "last_outbound",
    "inventory_max_capacity",
)


class FieldMeta(BaseModel):
    provenance: Provenance = Provenance.UNKNOWN
    status: Literal["unknown", "stated", "assumed", "blocking"] = "unknown"


class FactDelta(BaseModel):
    """Interpreter output: changes to apply, not a full form."""

    set: dict[str, Any] = Field(default_factory=dict)
    unset: list[str] = Field(default_factory=list)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    speech_acts: list[str] = Field(default_factory=list)
    provenance: Provenance = Provenance.EXTRACTED
    reason: str = ""


class MeetingRequirementState(BaseModel):
    attendees: Optional[int] = None
    date: Optional[str] = None
    preferred_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_hours: Optional[float] = None
    meeting_type: Optional[str] = None
    location_preference: Optional[str] = None
    hybrid_av: Optional[str] = None
    presentation_display: Optional[str] = None
    catering: Optional[str] = None
    dietary: Optional[str] = None
    special_access: Optional[str] = None
    external_visitors: Optional[int] = None
    external_visitors_indicated: bool = False
    visitor_details: Optional[str] = None
    guest_vehicles: Optional[int] = None
    vehicle_numbers: Optional[str] = None
    confidentiality: Optional[str] = None
    primary_office: Optional[str] = None
    field_provenance: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)

    def visitor_need(self) -> VisitorNeed:
        if _answered(self.visitor_details) and (self.external_visitors or 0) > 0:
            return VisitorNeed.NAMED
        if (self.external_visitors or 0) > 0:
            return VisitorNeed.COUNT_ONLY
        if self.external_visitors_indicated:
            return VisitorNeed.INDICATED
        if self.external_visitors == 0 and self.external_visitors_indicated is False:
            if self.field_provenance.get("external_visitors") in {
                Provenance.EXTRACTED.value,
                Provenance.USER_CONFIRMED.value,
                Provenance.INFERRED_POLICY.value,
                Provenance.SYSTEM.value,
            }:
                return VisitorNeed.NONE
        return VisitorNeed.UNKNOWN

    def blocking_gaps(self) -> list[dict[str, Any]]:
        """Derived from typed state — never from stale checklist_missing."""
        gaps: list[dict[str, Any]] = []
        if self.attendees is None:
            gaps.append(
                {
                    "field": "attendees",
                    "question": "How many people will attend in person?",
                    "blocking": True,
                }
            )
        if not _answered(self.date):
            gaps.append(
                {
                    "field": "date",
                    "question": "Which date do you need the room?",
                    "blocking": True,
                }
            )
        if not _answered(self.preferred_time) and not _answered(self.extra.get("time_window")):
            gaps.append(
                {
                    "field": "preferred_time",
                    "question": "What start time do you need (e.g. 2:00 PM)?",
                    "blocking": True,
                }
            )
        if self.duration_hours is None and not _answered(self.end_time):
            gaps.append(
                {
                    "field": "duration",
                    "question": "How long do you need the room (end time or duration)?",
                    "blocking": True,
                }
            )
        if not _answered(self.location_preference):
            office = self.primary_office or PRIMARY_OFFICE_HINT
            gaps.append(
                {
                    "field": "location_preference",
                    "question": (
                        f"Which office or building is required? Your primary office is {office}."
                    ),
                    "blocking": True,
                }
            )
        if not _answered(self.meeting_type):
            gaps.append(
                {
                    "field": "meeting_type",
                    "question": (
                        "Meeting type: internal, client/vendor, interview, training, confidential, or other?"
                    ),
                    "blocking": True,
                }
            )

        need = self.visitor_need()
        if need == VisitorNeed.INDICATED:
            gaps.append(
                {
                    "field": "external_visitors",
                    "question": (
                        "How many external visitors will attend? "
                        "Please also share their names, organisations and emails."
                    ),
                    "blocking": True,
                }
            )
        elif need == VisitorNeed.COUNT_ONLY:
            n = int(self.external_visitors or 0)
            gaps.append(
                {
                    "field": "visitor_details",
                    "question": (
                        "Please share visitor names, organisations and emails "
                        f"(you indicated {n} external visitor{'s' if n != 1 else ''})."
                    ),
                    "blocking": True,
                }
            )
        if (self.guest_vehicles or 0) > 0 and not _answered(self.vehicle_numbers):
            gaps.append(
                {
                    "field": "vehicle_numbers",
                    "question": (
                        f"Please share the {self.guest_vehicles} guest vehicle number(s)."
                    ),
                    "blocking": True,
                }
            )
        facts_for_catering = {"catering": self.catering}
        if catering_needed(facts_for_catering) and not _answered(self.dietary):
            gaps.append(
                {
                    "field": "dietary",
                    "question": (
                        "Please share dietary split (veg / non-veg) and any allergies for catering."
                    ),
                    "blocking": True,
                }
            )
        return gaps

    def is_complete(self) -> bool:
        return len(self.blocking_gaps()) == 0

    def derive_stage(self, extra: Optional[dict[str, Any]] = None) -> MeetingStage:
        bag = extra if extra is not None else self.extra
        if (bag.get("operational_status") or "").upper() == "CLOSED" or bag.get("employee_satisfied"):
            if bag.get("booked_room"):
                return MeetingStage.CLOSED
        if bag.get("booked_room"):
            return MeetingStage.MONITORING if bag.get("auto_booked_low_risk") or not bag.get("pending_confirmation") else MeetingStage.AUTO_BOOKED
        if bag.get("pending_confirmation") and bag.get("proposed_room"):
            return MeetingStage.PROPOSED
        if bag.get("auto_book_skipped") == "no_room_available" or bag.get("orchestration_stage") == MeetingStage.NO_RESOURCE.value:
            if not bag.get("booked_room"):
                return MeetingStage.NO_RESOURCE
        if not self.is_complete():
            if bag.get("registration_ack_sent"):
                return MeetingStage.AWAITING_REQUIREMENTS
            return MeetingStage.REGISTERED
        return MeetingStage.SEARCHING


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def state_from_facts(facts: dict[str, Any] | None) -> MeetingRequirementState:
    facts = dict(facts or {})
    provenance = dict(facts.get("field_provenance") or {})
    extra = {k: v for k, v in facts.items() if k not in REQUIREMENT_FIELDS and k != "field_provenance"}
    indicated = bool(facts.get("external_visitors_indicated"))
    visitors = _coerce_int(facts.get("external_visitors"))
    return MeetingRequirementState(
        attendees=_coerce_int(facts.get("attendees")),
        date=facts.get("date") or None,
        preferred_time=facts.get("preferred_time") if _answered(facts.get("preferred_time")) else None,
        end_time=facts.get("end_time") or None,
        duration_hours=_coerce_float(facts.get("duration_hours")),
        meeting_type=facts.get("meeting_type") or None,
        location_preference=facts.get("location_preference") or None,
        hybrid_av=facts.get("hybrid_av") or None,
        presentation_display=facts.get("presentation_display") or None,
        catering=facts.get("catering") or None,
        dietary=facts.get("dietary") or None,
        special_access=facts.get("special_access") or None,
        external_visitors=visitors,
        external_visitors_indicated=indicated,
        visitor_details=facts.get("visitor_details") or None,
        guest_vehicles=_coerce_int(facts.get("guest_vehicles")),
        vehicle_numbers=facts.get("vehicle_numbers") or None,
        confidentiality=facts.get("confidentiality") or None,
        primary_office=facts.get("primary_office") or None,
        field_provenance=provenance,
        extra=extra,
    )


def facts_from_state(state: MeetingRequirementState) -> dict[str, Any]:
    out = dict(state.extra or {})
    payload = state.model_dump(exclude={"extra", "field_provenance"})
    for key, value in payload.items():
        if value is None:
            continue
        out[key] = value
    out["field_provenance"] = dict(state.field_provenance or {})
    gaps = state.blocking_gaps()
    out["checklist_missing"] = [g["field"] for g in gaps]
    out["orchestration_stage"] = state.derive_stage(out).value
    return out
