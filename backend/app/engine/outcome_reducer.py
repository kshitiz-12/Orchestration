"""Deterministic outcome reducer — AI proposes deltas; platform owns merge."""

from __future__ import annotations

import re
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
from app.services.meeting_room import (
    _answered,
    is_booking_confirmation,
    is_employee_satisfied,
    looks_like_requirement_update,
)


INVENTABLE_COUNTS = frozenset({"attendees", "external_visitors", "guest_vehicles"})

_INT_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def _word_for_int(value: Any) -> str:
    try:
        return _INT_WORDS.get(int(value), "")
    except (TypeError, ValueError):
        return ""

def _rank(prov: str | Provenance | None) -> int:
    try:
        p = Provenance(prov) if not isinstance(prov, Provenance) else prov
    except ValueError:
        p = Provenance.UNKNOWN
    return FIELD_PROVENANCE_RANK.get(p, 0)


def _strong_headcount_restatement(n: int, source_text: str) -> bool:
    text = source_text or ""
    if re.search(
        rf"(?i)\b(?:only|now|change(?:d)?(?:\s+to)?|update(?:d)?(?:\s+to)?)\s+{n}\b",
        text,
    ):
        return True
    if re.search(
        rf"(?i)\b{n}\s*(?:people|participants|attendees|pax|members|persons?)\b",
        text,
    ):
        return True
    if re.search(
        rf"(?i)(?:people|participants|attendees|expected|around|about).{{0,24}}\b{n}\b",
        text,
    ):
        return True
    if re.search(rf"(?i)(?:for|of)\s+{n}\s+[a-z']{{0,4}}emp", text):
        return True
    return False


def _weak_employee_label_only(n: int, source_text: str) -> bool:
    """True when N only appears as 'N employee' on an access line / outbound label."""
    text = source_text or ""
    if _strong_headcount_restatement(n, text):
        return False
    if re.search(rf"(?i)(?:special access|security)[^\n]{{0,60}}{n}\s*emp", text):
        return True
    if re.search(rf"(?i)^[-*]\s*special access[^\n]*{n}\s*emp", text, re.M):
        return True
    return False


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
    if key == "attendees" and _weak_employee_label_only(n, source_text):
        return True
    if str(n) in text:
        return False
    # "12-13 emplyees" → attendees=13 is grounded even if only the range appears
    if key == "attendees" and re.search(rf"\b{n}\s*[-–]\s*\d{{1,2}}\b|\b\d{{1,2}}\s*[-–]\s*{n}\b", text):
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
        if key == "special_access":
            from app.ai.messy_meeting_parse import looks_like_headcount_as_access

            if looks_like_headcount_as_access(value):
                continue
        if key == "attendees":
            try:
                new_n = int(value)
            except (TypeError, ValueError):
                new_n = None
            if new_n is not None and _weak_employee_label_only(new_n, source_text):
                continue
            if new_n is not None and _answered(existing):
                try:
                    old_n = int(existing)
                except (TypeError, ValueError):
                    old_n = None
                if (
                    old_n is not None
                    and old_n != new_n
                    and not _strong_headcount_restatement(new_n, source_text)
                    and re.search(rf"(?i)\b{new_n}\s*employees?\b", source_text or "")
                ):
                    continue
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
        if key in {
            "field_provenance",
            "checklist_missing",
            "orchestration_stage",
            "issues",
            "external_visitors_add",
            "visitor_details_append",
        }:
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
    can_confirm = bool(
        (prior_facts or {}).get("pending_confirmation") or (prior_facts or {}).get("proposed_room")
    )
    speech: list[str] = list(speech_acts or [])
    if can_confirm and is_booking_confirmation(source_text) and "confirm" not in speech:
        speech.append("confirm")
    if "confirm" in speech and not can_confirm:
        speech = [s for s in speech if s != "confirm"]
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
        # Fill unknowns; also allow grounded updates for operational fields on reply
        updatable = {
            "dietary",
            "guest_vehicles",
            "vehicle_numbers",
            "visitor_details",
            "catering",
            "hybrid_av",
            "presentation_display",
            "location_preference",
            "preferred_time",
            "end_time",
        }
        unknown_only = {}
        src = (source_text or "").lower()
        for key, value in candidate_entities.items():
            if key in PLATFORM_KEYS and key not in REQUIREMENT_FIELDS:
                continue
            if not _answered(merged.get(key)):
                unknown_only[key] = value
                continue
            if key in updatable and _answered(value) and value != merged.get(key):
                # Must be grounded in this message (digit or keyword present)
                grounded = False
                if key == "guest_vehicles":
                    grounded = bool(
                        re.search(r"\b(parking|vehicle|car)s?\b", src)
                        and (str(value) in src or _word_for_int(value) in src)
                    )
                elif key == "dietary":
                    grounded = bool(re.search(r"\b(veg|non[-\s]?veg|dietary)\b", src))
                elif key == "vehicle_numbers":
                    grounded = str(value).lower() in src
                elif key == "location_preference":
                    grounded = bool(re.search(r"\bdown\s*-?\s*town\b", src)) or str(value).lower()[:12] in src
                elif key in {"preferred_time", "end_time"}:
                    grounded = bool(re.search(r"\d", str(value))) and str(value).split()[0][:4] in src.replace(" ", "")
                else:
                    grounded = str(value).lower()[:12] in src if value else False
                if grounded:
                    unknown_only[key] = value
        if unknown_only:
            cand = delta_from_entities(
                unknown_only,
                provenance=Provenance.CANDIDATE_HEURISTIC,
                speech_acts=speech,
            )
            # Elevate reply updates so they can replace earlier heuristic fills
            if any(k in updatable for k in unknown_only) and (
                "confirm" in speech or looks_like_requirement_update(source_text)
            ):
                cand.provenance = Provenance.EXTRACTED
            merged = apply_delta(merged, cand, source_text=source_text)

    if can_confirm and "confirm" in speech:
        merged["booking_confirmed"] = True
    else:
        merged.pop("booking_confirmed", None)
    if "satisfied" in speech:
        merged["employee_satisfied"] = True

    from app.ai.messy_meeting_parse import apply_grounded_reply_signals
    from app.domain.open_requests import merge_open_requests

    merged = apply_grounded_reply_signals(
        merged, prior_facts=prior_facts, source_text=source_text
    )
    incoming_for_open = {}
    for bag in (primary_entities, candidate_entities):
        if bag:
            incoming_for_open.update(bag)
    merged["open_requests"] = merge_open_requests(merged, incoming_for_open)

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
