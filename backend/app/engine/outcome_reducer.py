"""Deterministic outcome reducer — AI proposes deltas; platform owns merge."""

from __future__ import annotations

from typing import Any, Optional

from app.domain.meeting import (
    FIELD_PROVENANCE_RANK,
    PLATFORM_KEYS,
    REQUIREMENT_FIELDS,
    FactDelta,
    Provenance,
    attach_field_contract,
    facts_from_state,
    state_from_facts,
)
from app.services.meeting_room import _answered, is_booking_confirmation, is_employee_satisfied


INVENTABLE_COUNTS = frozenset({"attendees", "external_visitors", "guest_vehicles"})


def _rank(prov: str | Provenance | None) -> int:
    try:
        p = Provenance(prov) if not isinstance(prov, Provenance) else prov
    except ValueError:
        p = Provenance.UNKNOWN
    return FIELD_PROVENANCE_RANK.get(p, 0)


def _looks_invented_count(key: str, value: Any, source_text: str) -> bool:
    """Reject heuristic counts that are not grounded in the current message."""
    if key not in INVENTABLE_COUNTS:
        return False
    try:
        n = int(value)
    except (TypeError, ValueError):
        return False
    if n <= 0:
        return False
    text = (source_text or "").lower()
    if str(n) in text:
        return False
    # Defaulting visitors to 1 on "yes visitors" is the classic invention
    if key == "external_visitors" and n == 1 and "1" not in text:
        return True
    return key == "external_visitors" and "visitor" in text


def apply_delta(
    prior_facts: dict[str, Any] | None,
    delta: FactDelta,
    *,
    source_text: str = "",
) -> dict[str, Any]:
    """Merge a fact delta into the snapshot. Never overwrite filled fields with blanks."""
    prior = dict(prior_facts or {})
    provenance = dict(prior.get("field_provenance") or {})
    incoming_rank = _rank(delta.provenance)

    for key in delta.unset:
        if key in PLATFORM_KEYS:
            continue
        current_rank = _rank(provenance.get(key))
        if incoming_rank >= current_rank:
            prior.pop(key, None)
            provenance.pop(key, None)

    for key, value in (delta.set or {}).items():
        if key in {"field_provenance", "checklist_missing", "orchestration_stage"}:
            continue
        if not _answered(value) and value is not True:
            continue
        if delta.provenance == Provenance.CANDIDATE_HEURISTIC and _looks_invented_count(
            key, value, source_text
        ):
            continue
        if key == "external_visitors":
            try:
                n = int(value)
            except (TypeError, ValueError):
                n = None
            if n == 1 and "1" not in (source_text or "") and "one " not in (source_text or "").lower():
                if delta.provenance == Provenance.CANDIDATE_HEURISTIC:
                    prior["external_visitors_indicated"] = True
                    provenance["external_visitors_indicated"] = delta.provenance.value
                    continue
        existing = prior.get(key)
        existing_rank = _rank(provenance.get(key))
        if _answered(existing) and incoming_rank < existing_rank:
            continue
        # Heuristic must not clobber extracted/user values
        if _answered(existing) and incoming_rank <= existing_rank and incoming_rank <= _rank(
            Provenance.CANDIDATE_HEURISTIC
        ):
            if existing != value and existing_rank >= _rank(Provenance.EXTRACTED):
                continue
        prior[key] = value
        provenance[key] = (
            delta.provenance.value if isinstance(delta.provenance, Provenance) else str(delta.provenance)
        )

    if delta.assumptions:
        assumptions = list(prior.get("policy_assumptions") or [])
        for item in delta.assumptions:
            if item and item not in assumptions:
                assumptions.append(item)
        prior["policy_assumptions"] = assumptions

    if delta.speech_acts:
        prior["speech_acts"] = list(delta.speech_acts)

    prior["field_provenance"] = provenance
    state = state_from_facts(prior)
    out = facts_from_state(state)
    # Preserve platform keys that facts_from_state may have dropped if unset in extra
    for key in PLATFORM_KEYS:
        if key not in out and key in prior:
            out[key] = prior[key]
    out["field_provenance"] = provenance
    out["checklist_missing"] = [g["field"] for g in state.blocking_gaps()]
    out["orchestration_stage"] = state.derive_stage(out).value
    return attach_field_contract(out)


def delta_from_entities(
    entities: dict[str, Any] | None,
    *,
    provenance: Provenance = Provenance.EXTRACTED,
    speech_acts: Optional[list[str]] = None,
    reason: str = "",
) -> FactDelta:
    set_fields: dict[str, Any] = {}
    for key, value in (entities or {}).items():
        if key in {"field_provenance", "checklist_missing", "orchestration_stage", "issues"}:
            continue
        if _answered(value) or value is True or value is False:
            set_fields[key] = value
    acts = list(speech_acts or [])
    if not acts:
        acts = ["provide_facts"]
    return FactDelta(set=set_fields, speech_acts=acts, provenance=provenance, reason=reason)


def reduce_meeting_facts(
    prior_facts: dict[str, Any] | None,
    *,
    primary_entities: dict[str, Any] | None = None,
    candidate_entities: dict[str, Any] | None = None,
    source_text: str = "",
    primary_provenance: Provenance = Provenance.EXTRACTED,
    unset: Optional[list[str]] = None,
    speech_acts: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Apply interpreter entities, then optional heuristic candidates for unknown fields only."""
    speech: list[str] = list(speech_acts or [])
    if is_booking_confirmation(source_text) and "confirm" not in speech:
        speech.append("confirm")
    if is_employee_satisfied(source_text) and "satisfied" not in speech:
        speech.append("satisfied")
    if not speech:
        speech.append("provide_facts")

    merged = dict(prior_facts or {})
    if unset:
        merged = apply_delta(
            merged,
            FactDelta(unset=unset, provenance=primary_provenance, speech_acts=speech),
            source_text=source_text,
        )
    if primary_entities:
        delta = delta_from_entities(
            primary_entities, provenance=primary_provenance, speech_acts=speech
        )
        merged = apply_delta(merged, delta, source_text=source_text)

    if candidate_entities:
        # Only fill unknowns
        unknown_only = {}
        for key, value in candidate_entities.items():
            if key in PLATFORM_KEYS and key not in REQUIREMENT_FIELDS:
                continue
            if not _answered(merged.get(key)):
                unknown_only[key] = value
        if unknown_only:
            cand = delta_from_entities(
                unknown_only,
                provenance=Provenance.CANDIDATE_HEURISTIC,
                speech_acts=speech,
            )
            merged = apply_delta(merged, cand, source_text=source_text)

    if "confirm" in speech:
        merged["booking_confirmed"] = True
    elif not is_booking_confirmation(source_text):
        merged.pop("booking_confirmed", None)
    if "satisfied" in speech:
        merged["employee_satisfied"] = True

    state = state_from_facts(merged)
    out = facts_from_state(state)
    for key in PLATFORM_KEYS:
        if key not in out and key in merged:
            out[key] = merged[key]
    out["checklist_missing"] = [g["field"] for g in state.blocking_gaps()]
    out["orchestration_stage"] = state.derive_stage(out).value
    return attach_field_contract(out)


def apply_operator_override(
    prior_facts: dict[str, Any] | None,
    overrides: dict[str, Any],
    *,
    unset: Optional[list[str]] = None,
    actor: str = "operator",
) -> dict[str, Any]:
    """Operator/playbook write with USER_CONFIRMED provenance (highest rank)."""
    cleaned = {k: v for k, v in (overrides or {}).items() if k not in PLATFORM_KEYS}
    return reduce_meeting_facts(
        prior_facts,
        primary_entities=cleaned,
        unset=unset,
        primary_provenance=Provenance.USER_CONFIRMED,
        speech_acts=["operator_override"],
        source_text=f"operator:{actor}",
    )


def snapshot_gaps(facts: dict[str, Any] | None) -> list[dict[str, Any]]:
    state = state_from_facts(facts)
    if (facts or {}).get("booked_room"):
        return []
    if (facts or {}).get("pending_confirmation") and (facts or {}).get("proposed_room"):
        return []
    return state.blocking_gaps()
