"""SLA engine — calendar-aware targets from PolicyRule / service defaults."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models.org import PolicyRule, ServiceCatalog, utcnow


@dataclass
class SlaTarget:
    response_hours: float
    resolution_hours: float
    due_at: datetime
    rule_code: Optional[str] = None
    pause_allowed: bool = True
    reason: str = ""


class SlaEngine:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def target_for(
        self,
        *,
        category: Optional[str] = None,
        priority: str = "MEDIUM",
        service_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> SlaTarget:
        started = started_at or utcnow()
        on_s = date.today().isoformat()

        if service_id:
            svc = self.session.get(ServiceCatalog, service_id)
            if svc and svc.tenant_id == self.tenant_id:
                hours = float(svc.sla_hours or 48)
                return SlaTarget(
                    response_hours=max(1.0, hours / 4),
                    resolution_hours=hours,
                    due_at=started + timedelta(hours=hours),
                    rule_code=f"SERVICE:{svc.service_id}",
                    reason=f"Service catalogue SLA {hours}h",
                )

        rows = self.session.exec(
            select(PolicyRule)
            .where(PolicyRule.tenant_id == self.tenant_id)
            .where(PolicyRule.rule_family == "SLA")
            .where(PolicyRule.is_active == True)  # noqa: E712
            .order_by(PolicyRule.priority)
        ).all()
        for rule in rows:
            if rule.effective_from and rule.effective_from > on_s:
                continue
            if rule.effective_to and rule.effective_to < on_s:
                continue
            cond = rule.condition or {}
            cats = {str(c).upper() for c in (cond.get("categories") or [])}
            pris = {str(c).upper() for c in (cond.get("priorities") or [])}
            if cats and (category or "").upper() not in cats:
                continue
            if pris and priority.upper() not in pris:
                continue
            decision = rule.decision or {}
            resolution = float(decision.get("resolution_hours") or 48)
            response = float(decision.get("response_hours") or max(1.0, resolution / 4))
            return SlaTarget(
                response_hours=response,
                resolution_hours=resolution,
                due_at=started + timedelta(hours=resolution),
                rule_code=rule.code,
                pause_allowed=bool(decision.get("pause_allowed", True)),
                reason=rule.reason_template or f"SLA policy {rule.code}",
            )

        # Priority fallback (explicit)
        hours = {"CRITICAL": 4, "HIGH": 8, "MEDIUM": 24, "LOW": 48}.get(priority.upper(), 24)
        return SlaTarget(
            response_hours=max(1.0, hours / 4),
            resolution_hours=float(hours),
            due_at=started + timedelta(hours=hours),
            rule_code="FALLBACK_PRIORITY",
            reason=f"Fallback priority SLA {hours}h",
        )
