"""Shared outcome pattern: delta → reduce → stage → one action → always reply."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from app.domain.meeting import Provenance, attach_field_contract, build_field_contract


class GenericStage(str, Enum):
    REGISTERED = "REGISTERED"
    AWAITING_REQUIREMENTS = "AWAITING_REQUIREMENTS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"
    CLOSED = "CLOSED"


def append_decision_trace(facts: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Append an auditable decision step (model/policy/rule/action)."""
    out = dict(facts or {})
    trace = list(out.get("decision_trace") or [])
    trace.append(entry)
    out["decision_trace"] = trace[-50:]
    out["last_decision"] = entry
    return out


def apply_generic_snapshot(
    prior: dict[str, Any] | None,
    *,
    entities: dict[str, Any] | None = None,
    stage: Optional[str] = None,
    modules: Optional[dict[str, bool]] = None,
    missing: Optional[list[dict[str, Any]]] = None,
    provenance: Provenance = Provenance.EXTRACTED,
    decision: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Lightweight shared contract for non-meeting scenarios.
    Meeting room still uses reduce_meeting_facts; others get the same surface shape.
    """
    out = dict(prior or {})
    for key, value in (entities or {}).items():
        if value is None or value == "":
            continue
        out[key] = value
        prov = dict(out.get("field_provenance") or {})
        if key not in {"field_provenance", "decision_trace", "field_contract", "field_status"}:
            prov[key] = provenance.value if isinstance(provenance, Provenance) else str(provenance)
        out["field_provenance"] = prov

    if missing is not None:
        out["checklist_missing"] = [m.get("field") for m in missing if m.get("field")]
        out["field_contract"] = {
            "understood": [
                {"field": k, "value": v, "status": "stated", "provenance": (out.get("field_provenance") or {}).get(k)}
                for k, v in out.items()
                if k in (entities or {}) and v not in (None, "")
            ],
            "assumed": [],
            "missing": missing,
            "complete": len(missing) == 0,
            "stage": stage or out.get("orchestration_stage"),
        }
    else:
        # Best-effort: reuse meeting contract builder when requirement-shaped
        try:
            out = attach_field_contract(out)
        except Exception:  # noqa: BLE001
            out["field_contract"] = build_field_contract(out) if out else {"understood": [], "assumed": [], "missing": [], "complete": True}

    if stage:
        out["orchestration_stage"] = stage
    if modules is not None:
        out["modules_active"] = modules
    if decision:
        out = append_decision_trace(out, decision)
    return out


def derive_generic_stage(
    *,
    has_blocking_gaps: bool,
    awaiting_approval: bool,
    blocked: bool,
    complete: bool,
    closed: bool,
) -> GenericStage:
    if closed:
        return GenericStage.CLOSED
    if blocked:
        return GenericStage.BLOCKED
    if has_blocking_gaps:
        return GenericStage.AWAITING_REQUIREMENTS
    if awaiting_approval:
        return GenericStage.AWAITING_APPROVAL
    if complete:
        return GenericStage.COMPLETE
    return GenericStage.IN_PROGRESS
