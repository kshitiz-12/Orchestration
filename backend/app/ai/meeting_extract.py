"""Meeting-room extraction refine: Gemini leads; heuristic fills gaps; never invent counts."""

from __future__ import annotations

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
    "registration_ack_deferred",
    "clarification_sent",
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
    "orchestration_stage",
    "last_action",
    "outbound_required",
    "last_outbound",
    "inventory_max_capacity",
    "interpretation_path",
    "interpretation_endpoint",
    "requester_display_name",
    "field_status",
    "field_contract",
    "outbound_suppressions",
}


MEETING_ROOM_AI_INSTRUCTIONS = """
MEETING ROOM INTERPRETER (delta extraction):

Return entities AND fact_delta as a DELTA for THIS email only. Do not copy the entire
prior_facts snapshot into entities. The platform reducer merges your delta onto prior state.

fact_delta schema:
  { "set": {field: value}, "unset": [], "assumptions": [],
    "speech_acts": ["provide_facts"|"confirm"|"cancel"|"satisfied"] }

NORMALIZE informal / noisy text that IS present — that is extraction, not invention:
  • "12-13 emplyees" / "12-13 employees" (even across a newline) → attendees=13 (use upper bound)
  • "from 10 to 1ish" / "10 to 1ish" / "10-1" in a booking context → preferred_time=10:00 AM,
    end_time=1:00 PM, duration_hours=3 (business-hours noon-crossing is allowed)
  • "2 extrnal visitors" / "2 external visitors" → external_visitors=2 + names into visitor_details
  • "tea/cofee , 2 veg n rest non veg" → catering=requested, dietary=2 vegetarian, rest non-vegetarian
  • typos (emplyees, extrnal, gurugram, tomorow) still count as stated facts

1. Do NOT invent numbers that never appear. If visitors are mentioned with no count, set
   external_visitors_indicated=true and omit external_visitors.
2. Map synonyms: participants/people/attendees/members/pax/employees → attendees (integer).
3. Informal answers count: "internal" / "internal review" → meeting_type=internal meeting;
   "non veg" → dietary=non-vegetarian; names after visitors → visitor_details.
4. "yes" in a requirements list is NOT booking_confirmed / speech_acts confirm.
5. If office is omitted and prior_facts.primary_office exists, you MAY set location_preference
   to that office (do not invent a different site).
6. Catering without dietary → leave dietary unset (platform will ask).
7. missing_information = blocking fields still unknown AFTER merge with prior_facts.
8. Do NOT set human_review_required for ordinary meeting-room replies.
9. event_type=MEETING_ROOM for room booking threads (including INFORMATION REQUIRED replies).
10. Speech: confirm a proposal → speech_acts=["confirm"]; satisfied after meeting → ["satisfied"].
11. Prefer putting newly found fields in fact_delta.set AND entities.
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
    primary_is_heuristic: bool = False,
) -> ExtractionResult:
    """Reducer-backed merge: Gemini (or primary) delta + grounded messy + heuristic fill."""
    from app.ai.messy_meeting_parse import parse_messy_meeting_signals
    from app.domain.meeting import Provenance
    from app.engine.outcome_reducer import reduce_meeting_facts

    extraction.event_type = "MEETING_ROOM"
    extraction.category = "MEETING_ROOM"
    source = f"{subject}\n{body}"
    primary = dict(extraction.entities or {})
    # If primary already copied the whole prior snapshot, strip platform-only keys from delta
    for k in _PRESERVE_KEYS:
        primary.pop(k, None)
    fd = extraction.fact_delta if isinstance(extraction.fact_delta, dict) else {}
    if fd.get("set"):
        primary.update({k: v for k, v in fd["set"].items() if v is not None and v != ""})
    unset = list(fd.get("unset") or [])
    speech = list(fd.get("speech_acts") or [])

    # Grounded fill for fields Gemini left blank. Reducer only writes unknowns —
    # it will not overwrite an answered Gemini value.
    messy = parse_messy_meeting_signals(source)
    candidates: dict = dict(messy)
    if heuristic_entities:
        for key, value in heuristic_entities.items():
            if not _answered(candidates.get(key)) and _answered(value):
                candidates[key] = value

    merged = reduce_meeting_facts(
        prior_facts,
        primary_entities=primary,
        candidate_entities=candidates or None,
        source_text=source,
        primary_provenance=Provenance.CANDIDATE_HEURISTIC
        if primary_is_heuristic
        else Provenance.EXTRACTED,
        unset=unset,
        speech_acts=speech or None,
    )

    extraction.entities = merged
    gaps = meeting_room_gaps(merged)
    extraction.missing_information = [MissingInformation(**g) for g in gaps]
    extraction.clarification_questions = [g["question"] for g in gaps]
    extraction.human_review_required = False
    extraction.access_control_action = False
    if gaps:
        extraction.recommended_next_action = "clarification"
        extraction.confidence = max(float(extraction.confidence or 0), 0.78)
        extraction.reason = (extraction.reason or "") + " | reducer: awaiting blocking fields"
    else:
        extraction.recommended_next_action = "route_to_outcome_engine"
        extraction.confidence = max(float(extraction.confidence or 0), 0.9)
        extraction.reason = (extraction.reason or "") + " | reducer: facts complete"
    return extraction
