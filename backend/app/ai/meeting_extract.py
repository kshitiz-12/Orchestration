"""Meeting-room extraction refine: Gemini leads; heuristic fills gaps; never invent counts."""

from __future__ import annotations

from typing import Any, Optional

from app.domain.meeting import REQUIREMENT_FIELDS
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
You are reading a workplace email the way ChatGPT / Gemini would in chat.

People type however they want. Fragments, typos, mixed Hindi/English, "pls find the
same", answers written after our questions, extra asks that are not booking fields.
There is no form. Understand the intent of THIS message, then emit JSON.

You will receive:
  this_message — new text they typed
  answers_they_typed_on_our_questions — text after our '?' (may be incomplete)
  read_as — cleaned requester text for convenience
  quoted_thread.excerpt — mostly OUR previous outbound mail; they may have answered
    inline or edited bullets. Extract what THEY added. Do not copy our
    "already have on file" lines, example times in parentheses, or sample answers.
  already_on_file — compact known state. Return a DELTA only. Do not restate the
    whole form and do not blank known fields.
  still_asking — questions we still need

Job:
  1. Understand EVERYTHING they want. Map what you can onto meeting-room fields.
  2. Put every other ask in open_requests (photographer, extra chairs, signage,
     translator, cake, specific floor, markers, parking escort, …). Never drop an
     ask because it is "not in the schema".
  3. summary = one human sentence of what they want, including those extra asks.

Same facts can look like anything. Illustrations, not an exhaustive list:
  • "expected participants is around 20" / "20 ppl" / "12-13 emplyees" → attendees
    (use the upper bound of a range). Do not invent a number that never appears.
  • "from 10 to 1ish" / "9.30 a. M to 6 p. M" → start and end times.
  • "pls find the same" + answers after questions = they are answering. Extract
    those answers. That is NOT booking confirmation unless already_on_file has a
    proposed room / pending_confirmation.
  • A number on a Special access line ("5 employee") is not a new headcount if they
    already said ~20. Do not replace attendees unless they clearly change the count.
  • "1 more visitor: Priya" ADDS to prior visitors; do not replace the prior count
    with 1. Names go in visitor_details.
  • "yes" in a requirements list is not confirm. Confirm only if they are accepting
    a proposed room.

fact_delta: { "set": {}, "unset": [], "assumptions": [],
  "speech_acts": ["provide_facts"|"confirm"|"cancel"|"satisfied"] }
Put newly found fields in fact_delta.set AND entities.
event_type=MEETING_ROOM for room-booking threads (including INFORMATION REQUIRED).
Do NOT set human_review_required for ordinary meeting-room replies.
missing_information = blocking fields still unknown AFTER merge with already_on_file.
Catering without dietary → leave dietary unset (platform will ask).
If office is omitted and already_on_file.primary_office exists, you MAY set
location_preference to that office (do not invent a different site).
""".strip()


_INTERPRETER_STATE_KEYS = REQUIREMENT_FIELDS + (
    "open_requests",
    "primary_office",
    "pending_confirmation",
    "proposed_room",
    "booked_room",
    "orchestration_stage",
    "checklist_missing",
    "field_status",
)


def compact_interpreter_state(prior_facts: Optional[dict]) -> dict[str, Any]:
    """Small known-state blob for the chat model — not the whole outcome snapshot."""
    prior = prior_facts or {}
    out: dict[str, Any] = {}
    for key in _INTERPRETER_STATE_KEYS:
        value = prior.get(key)
        if value is None or value == "" or value == [] or value == {}:
            continue
        if key in {"proposed_room", "booked_room"} and isinstance(value, dict):
            slim = {
                k: value.get(k)
                for k in ("name", "id", "capacity", "location")
                if value.get(k) is not None
            }
            if slim:
                out[key] = slim
            continue
        if key == "field_status" and isinstance(value, dict):
            slim = {k: v for k, v in value.items() if k in REQUIREMENT_FIELDS and v}
            if slim:
                out[key] = slim
            continue
        out[key] = value
    last = prior.get("last_outbound")
    if isinstance(last, dict) and last.get("questions"):
        out["last_questions_we_sent"] = last.get("questions")
    return out


def build_interpreter_payload(
    *,
    subject: str,
    interpreter_view: dict[str, Any],
    prior_facts: Optional[dict] = None,
    allowed_context: Optional[dict] = None,
    attachment_summaries: Optional[list[str]] = None,
) -> dict[str, Any]:
    prior = prior_facts or {}
    return {
        "task": (
            "Read this workplace email the way ChatGPT or Gemini would in chat. "
            "Typing will be messy. Understand everything they want."
        ),
        "subject": subject,
        "this_message": interpreter_view.get("this_message") or "",
        "answers_they_typed_on_our_questions": interpreter_view.get(
            "answers_typed_on_quoted_questions"
        )
        or [],
        "read_as": interpreter_view.get("combined_for_parsers") or "",
        "quoted_thread": {
            "excerpt": interpreter_view.get("quoted_thread_excerpt") or "",
            "note": (
                "This is mostly OUR previous outbound email. Extract answers they typed "
                "onto it. Do not copy our examples or already-on-file bullets as new facts."
            ),
        },
        "already_on_file": compact_interpreter_state(prior),
        "still_asking": prior.get("checklist_missing") or [],
        "attachments": attachment_summaries or [],
        "allowed_context": allowed_context or {},
        "instructions": MEETING_ROOM_AI_INSTRUCTIONS,
    }


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
    from app.ai.messy_meeting_parse import looks_like_headcount_as_access, parse_messy_meeting_signals
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
    if extraction.open_requests and not primary.get("open_requests"):
        primary["open_requests"] = list(extraction.open_requests)
    unset = list(fd.get("unset") or [])
    speech = list(fd.get("speech_acts") or [])

    # Grounded fill for fields Gemini left blank. Reducer only writes unknowns —
    # it will not overwrite an answered Gemini value.
    if looks_like_headcount_as_access(primary.get("special_access")):
        primary.pop("special_access", None)

    messy = parse_messy_meeting_signals(source)
    candidates: dict = dict(messy)
    if heuristic_entities:
        for key, value in heuristic_entities.items():
            if not _answered(candidates.get(key)) and _answered(value):
                candidates[key] = value
    if looks_like_headcount_as_access(candidates.get("special_access")):
        candidates.pop("special_access", None)

    # Heuristic path: grounded parse beats regex copies of our outbound (e.g.
    # "Corporate Office" vs "down town Gurugram" typed after the question).
    # Gemini path: model leads; grounded parse only fills blanks.
    for key in ("attendees", "preferred_time", "end_time", "duration_hours", "location_preference"):
        if not _answered(messy.get(key)):
            continue
        if primary_is_heuristic or not _answered(primary.get(key)):
            primary[key] = messy[key]

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

    merged["raw_reply"] = body[:4000]
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
