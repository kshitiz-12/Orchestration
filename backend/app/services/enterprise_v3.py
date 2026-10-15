"""Enterprise V3 closers — contracts, vendor workspace, sealed RFQ, ESG, governed learning.

Excludes lease/real-estate commercial masters and mobile/IoT field capture.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, Session, select

from app.models.org import Contract, TimestampMixin, Vendor, new_id, utcnow
from app.services.outbox import OutboxService


class ContractAmendment(TimestampMixin, table=True):
    __tablename__ = "contract_amendments"

    amendment_id: str = Field(default_factory=lambda: new_id("cam_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    contract_id: str = Field(foreign_key="contracts.contract_id", index=True)
    version: int = 1
    change_summary: str
    rate_card_delta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    sla_credits: list = Field(default_factory=list, sa_column=Column(JSON))
    penalties: list = Field(default_factory=list, sa_column=Column(JSON))
    effective_from: Optional[str] = None
    approved_by: Optional[str] = None
    status: str = "APPROVED"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class VendorWorkspaceItem(TimestampMixin, table=True):
    """Day-2 vendor workspace — quote / evidence / invoice upload (not a separate portal app)."""

    __tablename__ = "vendor_workspace_items"

    item_id: str = Field(default_factory=lambda: new_id("vwi_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    vendor_id: str = Field(foreign_key="vendors.vendor_id", index=True)
    # QUOTE | EVIDENCE | INVOICE | PROGRESS
    item_type: str = Field(index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    rfq_id: Optional[str] = Field(default=None, index=True)
    title: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    amount: float = 0.0
    currency: str = "INR"
    file_refs: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = "SUBMITTED"  # SUBMITTED | ACCEPTED | REJECTED | WITHDRAWN
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class WasteManifest(TimestampMixin, table=True):
    __tablename__ = "waste_manifests"

    manifest_id: str = Field(default_factory=lambda: new_id("wst_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    waste_type: str  # HAZARDOUS | E_WASTE | ORGANIC | RECYCLABLE | GENERAL
    quantity_kg: float = 0.0
    disposer: Optional[str] = None
    manifest_no: Optional[str] = None
    disposed_on: Optional[str] = None
    certificate_ref: Optional[str] = None
    status: str = "LOGGED"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class CarbonInventory(TimestampMixin, table=True):
    __tablename__ = "carbon_inventory"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id", "period", "scope", name="uq_carbon_scope"),)

    carbon_id: str = Field(default_factory=lambda: new_id("co2_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    period: str
    scope: str  # SCOPE1 | SCOPE2 | SCOPE3
    tco2e: float = 0.0
    methodology: str = "MANUAL"
    factors: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "DRAFT"
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class MeterReading(TimestampMixin, table=True):
    __tablename__ = "meter_readings"

    reading_id: str = Field(default_factory=lambda: new_id("mtr_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    meter_code: str = Field(index=True)
    utility_type: str  # ENERGY | WATER | GAS
    reading_value: float
    previous_value: float = 0.0
    delta: float = 0.0
    rolled_over: bool = False
    reading_at: Optional[str] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class LearningSignOff(TimestampMixin, table=True):
    """Governed AI learning — only verified human corrections after sign-off enter the loop (M26)."""

    __tablename__ = "learning_signoffs"

    signoff_id: str = Field(default_factory=lambda: new_id("lso_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    record_id: str = Field(index=True)  # LearningRecord.record_id
    signed_by: str
    decision: str = "APPROVE"  # APPROVE | REJECT
    notes: Optional[str] = None
    status: str = "SIGNED"


class EnterpriseV3Service:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    # ── Contracts (M18) ─────────────────────────────────────────────────────

    def amend_contract(
        self,
        contract_id: str,
        *,
        change_summary: str,
        rate_card_delta: Optional[dict] = None,
        sla_credits: Optional[list] = None,
        penalties: Optional[list] = None,
        effective_from: Optional[str] = None,
        approved_by: Optional[str] = None,
    ) -> ContractAmendment:
        contract = self.session.get(Contract, contract_id)
        if not contract or contract.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Contract not found")
        prior = self.session.exec(
            select(ContractAmendment).where(
                ContractAmendment.tenant_id == self.tenant_id,
                ContractAmendment.contract_id == contract_id,
            )
        ).all()
        version = max([p.version for p in prior], default=0) + 1
        if rate_card_delta:
            card = dict(contract.rate_card or {})
            card.update(rate_card_delta)
            contract.rate_card = card
            contract.updated_at = utcnow()
            self.session.add(contract)
        row = ContractAmendment(
            tenant_id=self.tenant_id,
            contract_id=contract_id,
            version=version,
            change_summary=change_summary.strip(),
            rate_card_delta=rate_card_delta or {},
            sla_credits=sla_credits or [],
            penalties=penalties or [],
            effective_from=effective_from or date.today().isoformat(),
            approved_by=approved_by,
            status="APPROVED",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="CONTRACT.AMENDED",
            payload={"contract_id": contract_id, "amendment_id": row.amendment_id, "version": version},
            idempotency_key=f"cam-{row.amendment_id}",
            aggregate_type="Contract",
            aggregate_id=contract_id,
        )
        return row

    def terminate_contract(self, contract_id: str, *, reason: str, approved_by: Optional[str] = None) -> Contract:
        contract = self.session.get(Contract, contract_id)
        if not contract or contract.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Contract not found")
        contract.status = "TERMINATED"
        contract.end_date = date.today().isoformat()
        contract.updated_at = utcnow()
        self.session.add(contract)
        self.amend_contract(
            contract_id,
            change_summary=f"TERMINATED: {reason}",
            approved_by=approved_by,
            penalties=[{"type": "TERMINATION", "reason": reason}],
        )
        self.session.refresh(contract)
        return contract

    # ── Vendor workspace (day-2) ────────────────────────────────────────────

    def vendor_submit(
        self,
        vendor_id: str,
        *,
        item_type: str,
        title: str,
        payload: Optional[dict] = None,
        amount: float = 0.0,
        outcome_id: Optional[str] = None,
        rfq_id: Optional[str] = None,
        file_refs: Optional[list] = None,
        notes: Optional[str] = None,
    ) -> VendorWorkspaceItem:
        vendor = self.session.get(Vendor, vendor_id)
        if not vendor or vendor.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Vendor not found")
        if (vendor.status or "").upper() != "ACTIVE":
            raise HTTPException(status_code=409, detail="Only ACTIVE vendors may submit workspace items")
        itype = item_type.strip().upper()
        if itype not in {"QUOTE", "EVIDENCE", "INVOICE", "PROGRESS"}:
            raise HTTPException(status_code=400, detail="item_type must be QUOTE|EVIDENCE|INVOICE|PROGRESS")
        row = VendorWorkspaceItem(
            tenant_id=self.tenant_id,
            vendor_id=vendor_id,
            item_type=itype,
            outcome_id=outcome_id,
            rfq_id=rfq_id,
            title=title.strip(),
            payload=payload or {},
            amount=float(amount or 0),
            file_refs=file_refs or [],
            status="SUBMITTED",
            notes=notes,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type=f"VENDOR_WS.{itype}",
            payload={"item_id": row.item_id, "vendor_id": vendor_id, "outcome_id": outcome_id},
            idempotency_key=f"vwi-{row.item_id}",
            aggregate_type="VendorWorkspaceItem",
            aggregate_id=row.item_id,
        )
        return row

    def vendor_ws_decide(self, item_id: str, *, status: str, notes: Optional[str] = None) -> VendorWorkspaceItem:
        row = self.session.get(VendorWorkspaceItem, item_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Workspace item not found")
        st = status.strip().upper()
        if st not in {"ACCEPTED", "REJECTED", "WITHDRAWN"}:
            raise HTTPException(status_code=400, detail="status must be ACCEPTED|REJECTED|WITHDRAWN")
        row.status = st
        if notes:
            row.notes = notes
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # ── M16 sealed scoring ──────────────────────────────────────────────────

    def score_quotes_sealed(self, rfq_id: str, *, unseal: bool = False) -> dict[str, Any]:
        from app.services.vendor_sourcing import RfqRound, VendorQuote

        rfq = self.session.get(RfqRound, rfq_id)
        if not rfq or rfq.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="RFQ not found")
        quotes = list(
            self.session.exec(
                select(VendorQuote).where(
                    VendorQuote.tenant_id == self.tenant_id,
                    VendorQuote.rfq_id == rfq_id,
                )
            ).all()
        )
        due = (rfq.due_at or "").strip()
        if not unseal and due and due > utcnow().isoformat():
            return {
                "rfq_id": rfq_id,
                "sealed": True,
                "count": len(quotes),
                "message": "Bids sealed until due_at — commercial scores hidden",
                "items": [{"quote_id": q.quote_id, "vendor_id": q.vendor_id, "status": q.status} for q in quotes],
            }
        # Technical vs commercial split (weights configurable on RFQ notes/attrs later)
        scored = []
        for q in quotes:
            tech = float((q.score or 0) if q.score is not None else 50)
            # Inverse price rank as commercial score
            commercial = 100.0
            scored.append(
                {
                    "quote_id": q.quote_id,
                    "vendor_id": q.vendor_id,
                    "amount": q.amount,
                    "technical_score": tech,
                    "commercial_score": commercial,
                    "combined": round(0.6 * tech + 0.4 * commercial, 2),
                    "lead_time_days": getattr(q, "lead_time_days", None),
                }
            )
        if scored:
            amounts = sorted(set(float(s["amount"] or 0) for s in scored))
            for s in scored:
                # Cheaper = higher commercial score
                rank = amounts.index(float(s["amount"] or 0)) if amounts else 0
                s["commercial_score"] = round(100 - (rank * (100 / max(len(amounts), 1))), 2)
                s["combined"] = round(0.6 * s["technical_score"] + 0.4 * s["commercial_score"], 2)
            scored.sort(key=lambda x: x["combined"], reverse=True)
        rfq.status = "EVALUATED"
        self.session.add(rfq)
        self.session.commit()
        return {"rfq_id": rfq_id, "sealed": False, "items": scored, "winner_hint": scored[0] if scored else None}

    # ── M23 utilities / ESG ─────────────────────────────────────────────────

    def record_meter(
        self,
        *,
        meter_code: str,
        utility_type: str,
        reading_value: float,
        location_id: Optional[str] = None,
        max_dial: float = 999999.0,
    ) -> MeterReading:
        prior_rows = list(
            self.session.exec(
                select(MeterReading).where(
                    MeterReading.tenant_id == self.tenant_id,
                    MeterReading.meter_code == meter_code.strip().upper(),
                )
            ).all()
        )
        prev = max(prior_rows, key=lambda r: r.created_at or utcnow(), default=None)
        previous = float(prev.reading_value) if prev else 0.0
        current = float(reading_value)
        rolled = False
        if prev and current < previous:
            # Rollover: assume dial wrapped
            rolled = True
            delta = (max_dial - previous) + current + 1
        else:
            delta = max(0.0, current - previous)
        row = MeterReading(
            tenant_id=self.tenant_id,
            location_id=location_id,
            meter_code=meter_code.strip().upper(),
            utility_type=utility_type.strip().upper(),
            reading_value=current,
            previous_value=previous,
            delta=delta,
            rolled_over=rolled,
            reading_at=utcnow().isoformat(),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def log_waste(self, *, waste_type: str, quantity_kg: float, **kwargs: Any) -> WasteManifest:
        row = WasteManifest(
            tenant_id=self.tenant_id,
            location_id=kwargs.get("location_id"),
            waste_type=waste_type.strip().upper(),
            quantity_kg=float(quantity_kg),
            disposer=kwargs.get("disposer"),
            manifest_no=kwargs.get("manifest_no"),
            disposed_on=kwargs.get("disposed_on") or date.today().isoformat(),
            certificate_ref=kwargs.get("certificate_ref"),
            status="LOGGED",
            attributes=kwargs.get("attributes") or {},
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def upsert_carbon(
        self,
        *,
        period: str,
        scope: str,
        tco2e: float,
        location_id: Optional[str] = None,
        methodology: str = "MANUAL",
        factors: Optional[dict] = None,
    ) -> CarbonInventory:
        scope_u = scope.strip().upper()
        if scope_u not in {"SCOPE1", "SCOPE2", "SCOPE3"}:
            raise HTTPException(status_code=400, detail="scope must be SCOPE1|SCOPE2|SCOPE3")
        existing = self.session.exec(
            select(CarbonInventory).where(
                CarbonInventory.tenant_id == self.tenant_id,
                CarbonInventory.location_id == location_id,
                CarbonInventory.period == period,
                CarbonInventory.scope == scope_u,
            )
        ).first()
        if existing:
            existing.tco2e = float(tco2e)
            existing.methodology = methodology
            existing.factors = factors or existing.factors or {}
            existing.updated_at = utcnow()
            row = existing
        else:
            row = CarbonInventory(
                tenant_id=self.tenant_id,
                location_id=location_id,
                period=period,
                scope=scope_u,
                tco2e=float(tco2e),
                methodology=methodology,
                factors=factors or {},
                status="DRAFT",
            )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # ── M26 governed learning ───────────────────────────────────────────────

    def sign_off_learning(
        self,
        record_id: str,
        *,
        signed_by: str,
        decision: str = "APPROVE",
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        from app.models.company import LearningRecord

        rec = self.session.get(LearningRecord, record_id)
        if not rec or rec.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Learning record not found")
        dec = decision.strip().upper()
        if dec not in {"APPROVE", "REJECT"}:
            raise HTTPException(status_code=400, detail="decision must be APPROVE|REJECT")
        # Only verified + human-corrected records may enter the eligible pool
        if dec == "APPROVE":
            if not rec.verified:
                raise HTTPException(status_code=409, detail="Record must be verified before learning sign-off")
            if not (rec.corrections or []):
                raise HTTPException(
                    status_code=409,
                    detail="Governed learning requires human corrections — automatic prompt mutation forbidden",
                )
            rec.learning_eligible = True
        else:
            rec.learning_eligible = False
        rec.updated_at = utcnow()
        sign = LearningSignOff(
            tenant_id=self.tenant_id,
            record_id=record_id,
            signed_by=signed_by.strip().lower(),
            decision=dec,
            notes=notes,
            status="SIGNED",
        )
        self.session.add(rec)
        self.session.add(sign)
        self.session.commit()
        self.session.refresh(sign)
        return {
            "signoff_id": sign.signoff_id,
            "record_id": record_id,
            "learning_eligible": rec.learning_eligible,
            "decision": dec,
        }
