"""Facilities ops — PM schedules, soft-service rounds, incidents (M06/M07/M22)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.facilities import IncidentRecord, PreventiveSchedule, SoftServiceRound
from app.models.org import utcnow
from app.services.outbox import OutboxService


class FacilitiesOpsService:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def create_pm_schedule(
        self,
        *,
        title: str,
        frequency_days: int = 30,
        asset_id: Optional[str] = None,
        location_id: Optional[str] = None,
        checklist: Optional[list] = None,
        owner_role: str = "FACILITIES",
    ) -> PreventiveSchedule:
        row = PreventiveSchedule(
            tenant_id=self.tenant_id,
            entity_id=self.entity_id,
            asset_id=asset_id,
            location_id=location_id,
            title=title.strip(),
            checklist=checklist or [],
            frequency_days=max(1, int(frequency_days)),
            next_due_at=utcnow() + timedelta(days=max(1, int(frequency_days))),
            owner_role=owner_role,
            status="ACTIVE",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def complete_pm(self, schedule_id: str, *, notes: Optional[str] = None) -> PreventiveSchedule:
        row = self.session.get(PreventiveSchedule, schedule_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="PM schedule not found")
        now = utcnow()
        row.last_completed_at = now
        row.next_due_at = now + timedelta(days=row.frequency_days or 30)
        attrs = dict(row.attributes or {})
        attrs["last_notes"] = notes
        row.attributes = attrs
        row.updated_at = now
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def overdue_pm(self) -> list[PreventiveSchedule]:
        now = utcnow()
        rows = self.session.exec(
            select(PreventiveSchedule).where(
                PreventiveSchedule.tenant_id == self.tenant_id,
                PreventiveSchedule.status == "ACTIVE",
                PreventiveSchedule.next_due_at != None,  # noqa: E711
            )
        ).all()
        return [r for r in rows if r.next_due_at and r.next_due_at <= now]

    def log_soft_round(
        self,
        *,
        service_type: str,
        location_id: Optional[str] = None,
        score: Optional[float] = None,
        findings: Optional[list] = None,
        notes: Optional[str] = None,
    ) -> SoftServiceRound:
        st = service_type.strip().upper()
        allowed = {"HOUSEKEEPING", "HYGIENE", "PEST", "LANDSCAPING", "WASTE"}
        if st not in allowed:
            raise HTTPException(status_code=400, detail=f"service_type must be one of {sorted(allowed)}")
        row = SoftServiceRound(
            tenant_id=self.tenant_id,
            location_id=location_id,
            service_type=st,
            scheduled_for=utcnow(),
            completed_at=utcnow(),
            score=score,
            findings=findings or [],
            status="DONE",
            notes=notes,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def raise_incident(
        self,
        *,
        incident_type: str,
        title: str,
        severity: str = "MEDIUM",
        description: Optional[str] = None,
        location_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
        reported_by: Optional[str] = None,
        deterministic_urgent: bool = False,
    ) -> IncidentRecord:
        itype = incident_type.strip().upper()
        if deterministic_urgent or itype in {"FIRE", "MEDICAL"} or severity.upper() == "CRITICAL":
            deterministic_urgent = True
        fanout: list[str] = []
        if deterministic_urgent or itype in {"FIRE", "MEDICAL", "SECURITY", "BCP"} or severity.strip().upper() == "CRITICAL":
            deterministic_urgent = True
            fanout = self._emergency_fanout(itype, location_id=location_id)
        row = IncidentRecord(
            tenant_id=self.tenant_id,
            entity_id=self.entity_id,
            outcome_id=outcome_id,
            location_id=location_id,
            incident_type=itype,
            severity=severity.strip().upper(),
            title=title.strip(),
            description=description,
            status="OPEN",
            reported_by=reported_by,
            deterministic_urgent=deterministic_urgent,
            fanout_notified=fanout,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="INCIDENT.RAISED",
            payload={
                "incident_id": row.incident_id,
                "type": row.incident_type,
                "severity": row.severity,
                "urgent": row.deterministic_urgent,
                "fanout": fanout,
            },
            idempotency_key=f"incident-{row.incident_id}",
            aggregate_type="Incident",
            aggregate_id=row.incident_id,
        )
        for channel in fanout:
            OutboxService(self.session, self.tenant_id).enqueue(
                event_type="INCIDENT.EMERGENCY_FANOUT",
                payload={"incident_id": row.incident_id, "channel": channel, "type": itype},
                idempotency_key=f"incident-fanout-{row.incident_id}-{channel}",
                aggregate_type="Incident",
                aggregate_id=row.incident_id,
            )
        return row

    def _emergency_fanout(self, incident_type: str, *, location_id: Optional[str] = None) -> list[str]:
        """Notify command tree channels for emergency incidents (no mobile/sensor path)."""
        channels = ["FACILITIES_ONCALL", "SECURITY_CONTROL", "SITE_ADMIN"]
        if incident_type in {"FIRE", "MEDICAL"}:
            channels.append("EMERGENCY_SERVICES_DESK")
        if incident_type == "BCP":
            channels.append("BCP_COMMAND")
        if location_id:
            channels.append(f"SITE:{location_id}")
        return channels

    def close_incident(self, incident_id: str, *, capa: Optional[list] = None) -> IncidentRecord:
        row = self.session.get(IncidentRecord, incident_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Incident not found")
        row.status = "CLOSED"
        row.capa = capa or row.capa or []
        row.closed_at = utcnow()
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row
