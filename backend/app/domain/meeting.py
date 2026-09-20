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
    "registration_ack_deferred",
    "clarification_sent",
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
    "interpretation_path",
    "interpretation_endpoint",
    "requester_display_name",
    "field_status",
    "field_contract",
    "outbound_suppressions",
    "admin_ops_notices",
    "admin_ops_last",
    "decision_trace",
    "last_decision",
    "policy_version",
    "policy_code",
    "modules_active",
    "no_resource_alternatives",
    "no_resource_fingerprint",
    "no_resource_choice",
    "no_resource_diagnosis",
    "sla_at_risk",
    "open_requests",
    "post_booking_requests",
    "raw_reply",
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
        missing_start = not _answered(self.preferred_time) and not _answered(
            self.extra.get("time_window")
        )
        missing_duration = self.duration_hours is None and not _answered(self.end_time)
        # One ask when both are open — start vs length is the same reply for requesters
        if missing_start and missing_duration:
            gaps.append(
                {
                    "field": "preferred_time",
                    "question": (
                        "What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?"
                    ),
                    "blocking": True,
                }
            )
        elif missing_start:
            gaps.append(
                {
                    "field": "preferred_time",
                    "question": "What start time do you need (e.g. 2:00 PM)?",
                    "blocking": True,
                }
            )
        elif missing_duration:
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


ASSUMED_PROVENANCE = {
    Provenance.INFERRED_POLICY.value,
    Provenance.SYSTEM.value,
    Provenance.MASTER.value,
}


def _assumed_fields_from_facts(facts: dict[str, Any]) -> set[str]:
    assumed: set[str] = set()
    for item in facts.get("defaults_applied") or []:
        if isinstance(item, str) and item:
            assumed.add(item)
        elif isinstance(item, dict) and item.get("field"):
            assumed.add(str(item["field"]))
    for item in facts.get("policy_assumptions") or []:
        if isinstance(item, dict):
            field = item.get("field") or item.get("code")
            if field:
                assumed.add(str(field))
    return assumed


def build_field_contract(facts: dict[str, Any] | None) -> dict[str, Any]:
    """
    Operator-facing contract: understood vs assumed vs missing, with per-field status.
    Derived from typed state — never trust a stale checklist alone.
    """
    facts = dict(facts or {})
    state = state_from_facts(facts)
    provenance = dict(state.field_provenance or {})
    assumed_keys = _assumed_fields_from_facts(facts)
    blocking = {g["field"]: g for g in state.blocking_gaps()}
    # duration gap uses field name "duration" while facts use duration_hours/end_time
    if "duration" in blocking:
        if state.duration_hours is not None or _answered(state.end_time):
            blocking.pop("duration", None)

    fields: dict[str, dict[str, Any]] = {}
    understood: list[dict[str, Any]] = []
    assumed: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    display_keys = list(REQUIREMENT_FIELDS) + ["primary_office"]
    for key in display_keys:
        if key == "external_visitors_indicated":
            continue
        value = facts.get(key)
        if key == "duration_hours" and value is None and _answered(facts.get("end_time")):
            # End time satisfies duration — skip empty duration_hours row
            continue
        prov = provenance.get(key) or Provenance.UNKNOWN.value
        # Duration is represented once via blocking["duration"] / preferred_time — not as
        # separate end_time + duration_hours rows with the same question.
        if key in {"duration_hours", "end_time"} and (
            "duration" in blocking or "preferred_time" in blocking
        ):
            if not (_answered(value) or value is True or value is False):
                continue
        is_blocking = key in blocking
        answered = _answered(value) or value is True or value is False

        if is_blocking and not answered:
            status = "blocking"
        elif key in assumed_keys or prov in ASSUMED_PROVENANCE:
            status = "assumed" if answered else "unknown"
        elif answered:
            status = "stated"
        else:
            status = "unknown"

        meta = {
            "field": key,
            "value": value if answered else None,
            "provenance": prov,
            "status": status,
        }
        # Only surface interesting rows
        if status == "unknown" and not answered and key not in blocking and key != "duration_hours":
            # Optional unknowns stay out of the main lists unless operator needs them
            if key in {
                "hybrid_av",
                "presentation_display",
                "catering",
                "dietary",
                "special_access",
                "guest_vehicles",
                "vehicle_numbers",
                "confidentiality",
                "visitor_details",
                "external_visitors",
            }:
                fields[key] = meta
                continue
        fields[key] = meta
        if status == "blocking":
            gap = blocking.get(key) or blocking.get("duration") or {}
            missing.append({**meta, "question": gap.get("question")})
        elif status == "assumed":
            assumed.append(meta)
        elif status == "stated":
            understood.append(meta)

    for field, gap in blocking.items():
        if field == "duration" and any(m["field"] in {"duration_hours", "end_time"} for m in missing):
            continue
        if not any(m["field"] == field for m in missing):
            missing.append(
                {
                    "field": field,
                    "value": None,
                    "provenance": Provenance.UNKNOWN.value,
                    "status": "blocking",
                    "question": gap.get("question"),
                }
            )
            fields[field] = {
                "field": field,
                "value": None,
                "provenance": Provenance.UNKNOWN.value,
                "status": "blocking",
            }

    open_requests = list(facts.get("open_requests") or [])
    for item in open_requests:
        text = item.get("text") if isinstance(item, dict) else str(item)
        if text:
            understood.append(
                {
                    "field": "open_request",
                    "value": text,
                    "provenance": Provenance.EXTRACTED.value,
                    "status": "stated",
                }
            )

    return {
        "understood": understood,
        "assumed": assumed,
        "missing": missing,
        "fields": fields,
        "open_requests": open_requests,
        "complete": len(missing) == 0,
        "stage": state.derive_stage(facts).value,
    }


def attach_field_contract(facts: dict[str, Any]) -> dict[str, Any]:
    """Persist compact per-field status + full contract for API/UI."""
    contract = build_field_contract(facts)
    facts["field_contract"] = contract
    facts["field_status"] = {
        k: {"status": v["status"], "provenance": v["provenance"]}
        for k, v in (contract.get("fields") or {}).items()
    }
    return facts
