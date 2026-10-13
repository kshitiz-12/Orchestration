"""Administration modules — mailroom, employee lifecycle workplace, ESG readings (M14/M24/M23)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field

from app.models.org import Person, TimestampMixin, new_id, utcnow
from app.services.outbox import OutboxService


class MailItem(TimestampMixin, table=True):
    __tablename__ = "mail_items"

    mail_id: str = Field(default_factory=lambda: new_id("mail_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    direction: str  # INWARD | OUTWARD
    carrier: Optional[str] = None
    tracking_ref: Optional[str] = Field(default=None, index=True)
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    sender_name: Optional[str] = None
    location_id: Optional[str] = None
    status: str = "RECEIVED"  # RECEIVED | WITH_RECIPIENT | DISPATCHED | RETURNED
    outcome_id: Optional[str] = None
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class WorkplaceLifecycleCase(TimestampMixin, table=True):
    __tablename__ = "workplace_lifecycle_cases"

    case_id: str = Field(default_factory=lambda: new_id("wlc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    person_id: Optional[str] = Field(default=None, foreign_key="persons.person_id", index=True)
    person_email: str = Field(index=True)
    event_type: str  # JOINER | MOVER | LEAVER
    site_id: Optional[str] = None
    outcome_id: Optional[str] = None
    checklist: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "OPEN"  # OPEN | IN_PROGRESS | DONE | BLOCKED
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class UtilityReading(TimestampMixin, table=True):
    __tablename__ = "utility_readings"

    reading_id: str = Field(default_factory=lambda: new_id("utl_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    meter_code: str = Field(index=True)
    utility_type: str  # ELECTRICITY | WATER | GAS | FUEL | WASTE
    reading_value: float
    unit: str = "kWh"
    reading_at: Optional[str] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


_DEFAULT_JOINER = [
    {"code": "SEAT", "title": "Allocate seat", "done": False},
    {"code": "ACCESS", "title": "Access card", "done": False},
    {"code": "PARKING", "title": "Parking if needed", "done": False},
    {"code": "IT_KIT", "title": "IT kit / laptop", "done": False},
]
_DEFAULT_LEAVER = [
    {"code": "ACCESS_REVOKE", "title": "Revoke access", "done": False},
    {"code": "ASSET_RETURN", "title": "Return assets", "done": False},
    {"code": "NO_DUES", "title": "No-dues clearance", "done": False},
]


class AdminModulesService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def log_mail(
        self,
        *,
        direction: str,
        tracking_ref: Optional[str] = None,
        carrier: Optional[str] = None,
        recipient_name: Optional[str] = None,
        recipient_email: Optional[str] = None,
        sender_name: Optional[str] = None,
        location_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> MailItem:
        d = direction.strip().upper()
        if d not in {"INWARD", "OUTWARD"}:
            raise HTTPException(status_code=400, detail="direction must be INWARD or OUTWARD")
        row = MailItem(
            tenant_id=self.tenant_id,
            direction=d,
            tracking_ref=tracking_ref,
            carrier=carrier,
            recipient_name=recipient_name,
            recipient_email=(recipient_email or "").strip().lower() or None,
            sender_name=sender_name,
            location_id=location_id,
            status="RECEIVED" if d == "INWARD" else "DISPATCHED",
            notes=notes,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def start_lifecycle(
        self,
        *,
        event_type: str,
        person_email: str,
        site_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
    ) -> WorkplaceLifecycleCase:
        et = event_type.strip().upper()
        if et not in {"JOINER", "MOVER", "LEAVER"}:
            raise HTTPException(status_code=400, detail="event_type must be JOINER|MOVER|LEAVER")
        email = person_email.strip().lower()
        person = self.session.exec(
            select(Person).where(Person.tenant_id == self.tenant_id, Person.email == email)
        ).first()
        checklist = list(_DEFAULT_JOINER if et == "JOINER" else _DEFAULT_LEAVER if et == "LEAVER" else [
            {"code": "SEAT", "title": "Update seat", "done": False},
            {"code": "ACCESS", "title": "Update access", "done": False},
        ])
        row = WorkplaceLifecycleCase(
            tenant_id=self.tenant_id,
            person_id=person.person_id if person else None,
            person_email=email,
            event_type=et,
            site_id=site_id,
            outcome_id=outcome_id,
            checklist=checklist,
            status="OPEN",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type=f"LIFECYCLE.{et}",
            payload={"case_id": row.case_id, "email": email},
            idempotency_key=f"wlc-{row.case_id}",
            aggregate_type="WorkplaceLifecycle",
            aggregate_id=row.case_id,
        )
        return row

    def complete_checklist_item(self, case_id: str, code: str) -> WorkplaceLifecycleCase:
        row = self.session.get(WorkplaceLifecycleCase, case_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Lifecycle case not found")
        items = list(row.checklist or [])
        found = False
        for item in items:
            if str(item.get("code") or "").upper() == code.strip().upper():
                item["done"] = True
                found = True
        if not found:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        row.checklist = items
        if all(bool(i.get("done")) for i in items):
            row.status = "DONE"
        else:
            row.status = "IN_PROGRESS"
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def record_utility(
        self,
        *,
        meter_code: str,
        utility_type: str,
        reading_value: float,
        unit: str = "kWh",
        location_id: Optional[str] = None,
        reading_at: Optional[str] = None,
    ) -> UtilityReading:
        ut = utility_type.strip().upper()
        allowed = {"ELECTRICITY", "WATER", "GAS", "FUEL", "WASTE"}
        if ut not in allowed:
            raise HTTPException(status_code=400, detail=f"utility_type must be one of {sorted(allowed)}")
        row = UtilityReading(
            tenant_id=self.tenant_id,
            location_id=location_id,
            meter_code=meter_code.strip(),
            utility_type=ut,
            reading_value=float(reading_value),
            unit=unit,
            reading_at=reading_at or utcnow().isoformat(),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row
