"""Versioned meeting-room policy — platform-owned rules, not hard-coded ad-hoc."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from sqlmodel import Session, select

POLICY_CODE = "MEETING_ROOM_POLICY"
POLICY_VERSION = "2026.09.1"


@dataclass
class MeetingRoomPolicy:
    """Single versioned policy bundle for capacity, buffers, VC, catering, auto-book."""

    version: str = POLICY_VERSION
    code: str = POLICY_CODE
    vc_policy_code: str = "MP-INT-006"
    setup_buffer_internal_minutes: int = 10
    release_buffer_internal_minutes: int = 10
    setup_buffer_complex_minutes: int = 30
    release_buffer_complex_minutes: int = 15
    auto_book_min_score: int = 90
    auto_book_require_internal: bool = True
    auto_book_forbid_visitors: bool = True
    auto_book_forbid_catering: bool = True
    catering_requires_dietary: bool = True
    capacity_hard_fail: bool = True
    display_hard_fail: bool = True
    no_resource_offer_split: bool = True
    no_resource_offer_later: bool = True
    no_resource_offer_larger: bool = True
    task_sla_hours_default: int = 48
    escalate_overdue_after_hours: int = 4
    modules: dict[str, bool] = field(
        default_factory=lambda: {
            "visitors": True,
            "parking": True,
            "av": True,
            "catering": True,
            "invoice": True,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MeetingRoomPolicy":
        base = cls()
        if not data:
            return base
        known = {f.name for f in base.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known and k != "modules"}
        pol = cls(**{**asdict(base), **kwargs})
        if isinstance(data.get("modules"), dict):
            pol.modules = {**base.modules, **data["modules"]}
        return pol


def default_meeting_policy() -> MeetingRoomPolicy:
    return MeetingRoomPolicy()


def load_meeting_policy(session: Optional[Session] = None, tenant_id: Optional[str] = None) -> MeetingRoomPolicy:
    """Load active MEETING_ROOM_POLICY BusinessRule, else baked-in defaults."""
    if session is None or not tenant_id:
        return default_meeting_policy()
    from app.models.org import BusinessRule

    row = session.exec(
        select(BusinessRule).where(
            BusinessRule.tenant_id == tenant_id,
            BusinessRule.code == POLICY_CODE,
            BusinessRule.is_active == True,  # noqa: E712
        )
    ).first()
    if not row:
        return default_meeting_policy()
    cfg = dict(row.config or {})
    cfg.setdefault("version", row.config.get("version") if row.config else POLICY_VERSION)
    return MeetingRoomPolicy.from_dict(cfg)


def ensure_meeting_policy_rule(session: Session, tenant_id: str) -> MeetingRoomPolicy:
    """Upsert versioned policy into BusinessRule so Config UI can show/edit it."""
    from app.models.org import BusinessRule

    pol = default_meeting_policy()
    row = session.exec(
        select(BusinessRule).where(
            BusinessRule.tenant_id == tenant_id,
            BusinessRule.code == POLICY_CODE,
        )
    ).first()
    payload = pol.to_dict()
    if row:
        # Preserve operator overrides; refresh version metadata if missing
        merged = {**payload, **(row.config or {})}
        merged["version"] = (row.config or {}).get("version") or pol.version
        row.config = merged
        row.description = f"Meeting room capacity, buffers, VC, auto-book (v{merged['version']})"
        row.is_active = True
        session.add(row)
        return MeetingRoomPolicy.from_dict(merged)
    session.add(
        BusinessRule(
            tenant_id=tenant_id,
            code=POLICY_CODE,
            category="MEETING_ROOM",
            description=f"Meeting room capacity, buffers, VC, auto-book (v{pol.version})",
            config=payload,
            is_active=True,
        )
    )
    return pol


def build_no_resource_alternatives(
    facts: dict[str, Any],
    *,
    max_capacity: int,
    room_scores: list[dict[str, Any]] | None = None,
    policy: Optional[MeetingRoomPolicy] = None,
) -> list[dict[str, Any]]:
    """Structured alternatives when inventory cannot satisfy the request."""
    policy = policy or default_meeting_policy()
    try:
        needed = int(facts.get("attendees") or 0)
    except (TypeError, ValueError):
        needed = 0
    alts: list[dict[str, Any]] = []
    if policy.no_resource_offer_larger and max_capacity and needed > max_capacity:
        alts.append(
            {
                "code": "REDUCE_HEADCOUNT",
                "label": f"Reduce in-person headcount to {max_capacity} or fewer",
                "payload": {"max_capacity": max_capacity, "requested": needed},
            }
        )
    if policy.no_resource_offer_later:
        alts.append(
            {
                "code": "DIFFERENT_TIME",
                "label": "Try a different date or start time",
                "payload": {
                    "date": facts.get("date"),
                    "preferred_time": facts.get("preferred_time"),
                },
            }
        )
    if policy.no_resource_offer_larger:
        alts.append(
            {
                "code": "LARGER_VENUE",
                "label": "Escalate for a larger venue / off-site option",
                "payload": {"inventory_max_capacity": max_capacity},
            }
        )
    if policy.no_resource_offer_split and needed > 0:
        half = max(1, needed // 2)
        alts.append(
            {
                "code": "SPLIT_ROOMS",
                "label": f"Split into two rooms (~{half} + {needed - half})",
                "payload": {"split_a": half, "split_b": needed - half},
            }
        )
    # Near-miss rooms (score 0 only due to capacity/equipment) stay visible for ops
    near = [r for r in (room_scores or []) if r.get("score", 0) == 0][:3]
    if near:
        alts.append(
            {
                "code": "REVIEW_NEAR_MISS",
                "label": "Ops review near-miss rooms",
                "payload": {"rooms": near},
            }
        )
    return alts


def active_modules(facts: dict[str, Any], policy: Optional[MeetingRoomPolicy] = None) -> dict[str, bool]:
    """Which post-book modules should run for this snapshot."""
    policy = policy or default_meeting_policy()
    from app.services.meeting_room import (
        catering_needed,
        external_visitor_count,
        guest_vehicle_count,
        hybrid_needed,
        presentation_needed,
    )

    enabled = policy.modules
    return {
        "visitors": bool(enabled.get("visitors")) and external_visitor_count(facts) > 0,
        "parking": bool(enabled.get("parking")) and guest_vehicle_count(facts) > 0,
        "av": bool(enabled.get("av")) and (hybrid_needed(facts) or presentation_needed(facts)),
        "catering": bool(enabled.get("catering")) and catering_needed(facts),
        "invoice": bool(enabled.get("invoice")) and catering_needed(facts),
    }
