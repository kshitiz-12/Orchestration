"""Approval control engine — route from PolicyRule / spend thresholds (no invented approvers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlalchemy import desc
from sqlmodel import Session, select

from app.models.org import PolicyRule


@dataclass
class ApprovalDecision:
    required: bool
    route: list[str] = field(default_factory=list)
    reason: str = ""
    rule_code: Optional[str] = None
    rule_version: Optional[int] = None
    authority_snapshot: dict[str, Any] = field(default_factory=dict)


class ApprovalEngine:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def _active_rules(self, *, on: Optional[date] = None) -> list[PolicyRule]:
        on = on or date.today()
        on_s = on.isoformat()
        rows = self.session.exec(
            select(PolicyRule)
            .where(PolicyRule.tenant_id == self.tenant_id)
            .where(PolicyRule.rule_family == "APPROVAL")
            .where(PolicyRule.is_active == True)  # noqa: E712
            .order_by(PolicyRule.priority, desc(PolicyRule.version))
        ).all()
        out: list[PolicyRule] = []
        for r in rows:
            if self.entity_id and r.entity_id and r.entity_id != self.entity_id:
                continue
            if r.effective_from and r.effective_from > on_s:
                continue
            if r.effective_to and r.effective_to < on_s:
                continue
            out.append(r)
        return out

    def decide(
        self,
        *,
        amount: float = 0.0,
        category: Optional[str] = None,
        requester_email: Optional[str] = None,
        default_approver: Optional[str] = None,
        risk: str = "LOW",
    ) -> ApprovalDecision:
        """Deterministic approval: policy rules first, else threshold fallback (documented)."""
        for rule in self._active_rules():
            cond = rule.condition or {}
            min_amount = float(cond.get("min_amount") or 0)
            cats = {str(c).upper() for c in (cond.get("categories") or [])}
            risks = {str(c).upper() for c in (cond.get("risks") or [])}
            if amount < min_amount:
                continue
            if cats and (category or "").upper() not in cats:
                continue
            if risks and risk.upper() not in risks:
                continue
            decision = rule.decision or {}
            route = list(decision.get("approvers") or [])
            if not route and default_approver:
                route = [default_approver]
            if requester_email:
                route = [a for a in route if a.strip().lower() != requester_email.strip().lower()]
            return ApprovalDecision(
                required=bool(decision.get("required", True)),
                route=route,
                reason=rule.reason_template or f"Matched policy {rule.code} v{rule.version}",
                rule_code=rule.code,
                rule_version=rule.version,
                authority_snapshot={
                    "amount": amount,
                    "category": category,
                    "risk": risk,
                    "condition": cond,
                    "decision": decision,
                },
            )

        # Fallback thresholds (explicit, not invented per-request)
        if amount >= 50000 or risk.upper() in {"HIGH", "CRITICAL"}:
            route = [default_approver] if default_approver else []
            if requester_email and route:
                route = [a for a in route if a.strip().lower() != requester_email.strip().lower()]
            return ApprovalDecision(
                required=True,
                route=route,
                reason="Fallback threshold: amount>=50000 or high risk",
                rule_code="FALLBACK_THRESHOLD",
                rule_version=1,
                authority_snapshot={"amount": amount, "risk": risk},
            )
        return ApprovalDecision(required=False, reason="No approval rule matched; below fallback threshold")
