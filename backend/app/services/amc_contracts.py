"""AMC / contract maintenance obligations (M04 / M18)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, Session, select

from app.models.org import Contract, TimestampMixin, new_id, utcnow
from app.services.outbox import OutboxService


class AmcObligation(TimestampMixin, table=True):
    __tablename__ = "amc_obligations"

    obligation_id: str = Field(default_factory=lambda: new_id("amc_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    contract_id: str = Field(foreign_key="contracts.contract_id", index=True)
    asset_id: Optional[str] = Field(default=None, foreign_key="assets.asset_id", index=True)
    title: str
    coverage: dict = Field(default_factory=dict, sa_column=Column(JSON))
    sla_hours: int = 24
    inclusions: list = Field(default_factory=list, sa_column=Column(JSON))
    exclusions: list = Field(default_factory=list, sa_column=Column(JSON))
    next_pm_due: Optional[str] = None
    status: str = "ACTIVE"
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class ProjectRecord(TimestampMixin, table=True):
    __tablename__ = "project_records"

    project_id: str = Field(default_factory=lambda: new_id("prj_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    code: str = Field(index=True)
    name: str
    project_type: str = "FITOUT"  # FITOUT | PROPERTY | INSURANCE | OTHER
    status: str = "PLANNED"  # PLANNED | ACTIVE | HANDOVER | CLOSED
    budget_amount: float = 0.0
    currency: str = "INR"
    location_id: Optional[str] = None
    vendor_id: Optional[str] = None
    milestones: list = Field(default_factory=list, sa_column=Column(JSON))
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class AmcContractsService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def link_obligation(
        self,
        *,
        contract_id: str,
        title: str,
        asset_id: Optional[str] = None,
        sla_hours: int = 24,
        inclusions: Optional[list] = None,
        exclusions: Optional[list] = None,
        coverage: Optional[dict] = None,
        next_pm_due: Optional[str] = None,
    ) -> AmcObligation:
        contract = self.session.get(Contract, contract_id)
        if not contract or contract.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Contract not found")
        row = AmcObligation(
            tenant_id=self.tenant_id,
            contract_id=contract_id,
            asset_id=asset_id,
            title=title.strip(),
            sla_hours=sla_hours,
            inclusions=inclusions or [],
            exclusions=exclusions or [],
            coverage=coverage or {},
            next_pm_due=next_pm_due,
            status="ACTIVE",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_obligations(self, contract_id: Optional[str] = None) -> list[AmcObligation]:
        stmt = select(AmcObligation).where(AmcObligation.tenant_id == self.tenant_id)
        if contract_id:
            stmt = stmt.where(AmcObligation.contract_id == contract_id)
        return list(self.session.exec(stmt).all())

    def create_project(
        self,
        *,
        code: str,
        name: str,
        project_type: str = "FITOUT",
        budget_amount: float = 0.0,
        location_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        milestones: Optional[list] = None,
    ) -> ProjectRecord:
        existing = self.session.exec(
            select(ProjectRecord).where(
                ProjectRecord.tenant_id == self.tenant_id,
                ProjectRecord.code == code.strip().upper(),
            )
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Project code exists")
        row = ProjectRecord(
            tenant_id=self.tenant_id,
            entity_id=entity_id,
            code=code.strip().upper(),
            name=name.strip(),
            project_type=project_type.strip().upper(),
            budget_amount=budget_amount,
            location_id=location_id,
            vendor_id=vendor_id,
            milestones=milestones or [],
            status="PLANNED",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="PROJECT.CREATED",
            payload={"project_id": row.project_id, "code": row.code},
            idempotency_key=f"prj-{row.project_id}",
            aggregate_type="Project",
            aggregate_id=row.project_id,
        )
        return row

    def advance_project(self, project_id: str, status: str) -> ProjectRecord:
        row = self.session.get(ProjectRecord, project_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Project not found")
        allowed = {"PLANNED", "ACTIVE", "HANDOVER", "CLOSED"}
        st = status.strip().upper()
        if st not in allowed:
            raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")
        row.status = st
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row
