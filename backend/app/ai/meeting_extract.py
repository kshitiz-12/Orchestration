"""Meeting-room extraction refine: Gemini leads; heuristic fills gaps; never invent counts."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.schemas.ai import ExtractionResult, MissingInformation
from app.services.meeting_room import (
    is_booking_confirmation,
    is_employee_satisfied,
    meeting_room_gaps,
)

# System/platform keys that must not be wiped by extraction
_PRESERVE_KEYS = {
    "registration_ack_sent",
    "primary_office",
    "operational_status",
    "financial_status",
    "operational_readiness_pct",
    "pending_confirmation",
    "proposed_room",
    "booked_room",
    "checklist_missing",
    "policy_assumptions",
    "defaults_applied",
    "execution_plan",
    "auto_booked_low_risk",
}


MEETING_ROOM_AI_INSTRUCTIONS = """
MEETING ROOM / BOOKING EXTRACTION RULES (strict):

You are a careful interpreter. Prefer understanding natural language over keywords.

1. NEVER invent numeric facts. If the user says visitors will attend but does not give a count,
   set entities.external_visitors_indicated=true and leave external_visitors unset.
   Add missing_information asking how many visitors and for names/orgs/emails.
2. Map synonyms: participants/people/attendees/members/pax → attendees (integer).
3. "confidential" as meeting type → meeting_type=confidential and confidentiality=business confidential.
4. "yes" alone in a long requirements list is NOT booking confirmation.
   Only set booking_confirmed=true for clear confirm/yes-to-book replies to a proposal.
5. Merge with prior_facts: keep known date/time/attendees; fill only new or corrected fields from this email.
6. If office/building is omitted but prior_facts.primary_office exists, you MAY set
   location_preference to that primary office and note it in reason — do not invent a different site.
7. For catering without dietary split → missing dietary (blocking).
8. missing_information must list ONLY still-unknown blocking fields after merging prior_facts + this email.
9. Do NOT set human_review_required for ordinary meeting-room clarification replies
   (visitors, catering, VC, confidential rooms are handled by platform modules).
10. Set event_type=MEETING_ROOM for room booking threads (including replies to INFORMATION REQUIRED).
11. Extract when present: attendees, date, preferred_time, end_time, duration_hours, meeting_type,
    hybrid_av, presentation_display, location_preference, catering, dietary, special_access,
    external_visitors (only if a number is stated), external_visitors_indicated, visitor_details,
    guest_vehicles, vehicle_numbers, confidentiality, booking_confirmed, employee_satisfied, new_request.
""".strip()


def _answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    return bool(str(value).strip())


def merge_meeting_entities(
    *,
    prior: dict[str, Any],
    primary: dict[str, Any],
    secondary: dict[str, Any],
) -> dict[str, Any]:
    """prior < secondary < primary. Primary wins when answered; secondary fills blanks."""
    out: dict[str, Any] = {}
    for source in (prior, secondary, primary):
        for key, value in (source or {}).items():
            if key in _PRESERVE_KEYS and key in out and _answered(out.get(key)):
                # keep earlier preserve unless primary explicitly sets
                if source is primary and _answered(value):
                    out[key] = value
                continue
            if _answered(value):
                # Do not let secondary invent visitor count over "indicated only"
                if (
                    key == "external_visitors"
                    and source is secondary
                    and primary.get("external_visitors_indicated")
                    and not _answered(primary.get("external_visitors"))
                ):
                    continue
                out[key] = value
            elif key not in out:
                out[key] = value
    # Preserve platform flags from prior
    for key in _PRESERVE_KEYS:
        if key in prior and key not in out:
            out[key] = prior[key]
        elif key in prior and _answered(prior.get(key)) and not _answered(out.get(key)):
            out[key] = prior[key]
    return out


def sanitize_meeting_confirmation_flags(entities: dict[str, Any], *, subject: str, body: str) -> dict[str, Any]:
    out = dict(entities or {})
    blob = f"{subject}\n{body}"
    if is_booking_confirmation(blob):
        out["booking_confirmed"] = True
    else:
        out.pop("booking_confirmed", None)
    if is_employee_satisfied(blob):
        out["employee_satisfied"] = True
    return out


def recompute_meeting_gaps(entities: dict[str, Any]) -> list[dict[str, Any]]:
    if entities.get("booked_room"):
        return []
    if entities.get("pending_confirmation") and entities.get("proposed_room"):
        return []
    return meeting_room_gaps(entities)


def refine_meeting_room_extraction(
    extraction: ExtractionResult,
    *,
    subject: str,
    body: str,
    prior_facts: Optional[dict] = None,
    heuristic_entities: Optional[dict] = None,
) -> ExtractionResult:
    """Normalize Gemini (or heuristic) meeting-room output into consistent entities + gaps."""
    prior = dict(prior_facts or {})
    primary = dict(extraction.entities or {})
    secondary = dict(heuristic_entities or {})

    # If model omitted event type but thread is meeting-room, force it
    extraction.event_type = "MEETING_ROOM"
    extraction.category = "MEETING_ROOM"

    merged = merge_meeting_entities(prior=prior, primary=primary, secondary=secondary)
    merged = sanitize_meeting_confirmation_flags(merged, subject=subject, body=body)

    # Strip invented visitor count when only indication exists
    if merged.get("external_visitors_indicated") and not _answered(primary.get("external_visitors")):
        # Keep count only if prior already had a real count or heuristic/primary stated a number in this mail
        body_l = (body or "").lower()
        if not re.search(r"\d+\s*(?:client|external|visitor|guests?)", body_l):
            if not _answered(prior.get("external_visitors")):
                merged.pop("external_visitors", None)

    gaps = recompute_meeting_gaps(merged)
    extraction.entities = merged
    extraction.missing_information = [MissingInformation(**g) for g in gaps]
    extraction.clarification_questions = [g["question"] for g in gaps]

    # Meeting-room operational path — modules handle visitors/catering/confidential
    extraction.human_review_required = False
    extraction.access_control_action = False
    if gaps:
        extraction.recommended_next_action = "clarification"
        extraction.confidence = max(float(extraction.confidence or 0), 0.78)
        extraction.reason = (extraction.reason or "") + " | meeting refine: awaiting blocking fields"
    else:
        extraction.recommended_next_action = "route_to_outcome_engine"
        extraction.confidence = max(float(extraction.confidence or 0), 0.9)
        extraction.reason = (extraction.reason or "") + " | meeting refine: facts complete"

    return extraction
