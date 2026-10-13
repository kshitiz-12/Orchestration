"""Vendor sourcing — requirement → RFQ → quotes → award (M16)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, Session, select

from app.models.org import TimestampMixin, Vendor, new_id, utcnow
from app.services.outbox import OutboxService


class SourcingRequirement(TimestampMixin, table=True):
    __tablename__ = "sourcing_requirements"

    requirement_id: str = Field(default_factory=lambda: new_id("srf_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    entity_id: Optional[str] = Field(default=None, index=True)
    outcome_id: Optional[str] = Field(default=None, index=True)
    title: str
    category: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    location_id: Optional[str] = None
    status: str = "OPEN"  # OPEN | RFQ_SENT | EVALUATION | AWARDED | CANCELLED
    award_vendor_id: Optional[str] = None
    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))


class RfqRound(TimestampMixin, table=True):
    __tablename__ = "rfq_rounds"

    rfq_id: str = Field(default_factory=lambda: new_id("rfq_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    requirement_id: str = Field(foreign_key="sourcing_requirements.requirement_id", index=True)
    vendor_ids: list = Field(default_factory=list, sa_column=Column(JSON))
    due_at: Optional[str] = None
    status: str = "OPEN"
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))


class VendorQuote(TimestampMixin, table=True):
    __tablename__ = "vendor_quotes"

    quote_id: str = Field(default_factory=lambda: new_id("qte_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    rfq_id: str = Field(foreign_key="rfq_rounds.rfq_id", index=True)
    vendor_id: str = Field(foreign_key="vendors.vendor_id", index=True)
    amount: float = 0.0
    currency: str = "INR"
    lead_time_days: Optional[int] = None
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    score: Optional[float] = None
    status: str = "SUBMITTED"  # SUBMITTED | SHORTLISTED | REJECTED | AWARDED


class VendorSourcingService:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def create_requirement(
        self,
        *,
        title: str,
        category: str,
        description: Optional[str] = None,
        location_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
    ) -> SourcingRequirement:
        row = SourcingRequirement(
            tenant_id=self.tenant_id,
            entity_id=self.entity_id,
            outcome_id=outcome_id,
            title=title.strip(),
            category=category.strip().upper(),
            description=description,
            location_id=location_id,
            status="OPEN",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def open_rfq(
        self,
        requirement_id: str,
        *,
        vendor_ids: list[str],
        due_at: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> RfqRound:
        req = self.session.get(SourcingRequirement, requirement_id)
        if not req or req.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Sourcing requirement not found")
        if not vendor_ids:
            raise HTTPException(status_code=400, detail="vendor_ids required")
        for vid in vendor_ids:
            v = self.session.get(Vendor, vid)
            if not v or v.tenant_id != self.tenant_id or (v.status or "").upper() != "ACTIVE":
                raise HTTPException(status_code=400, detail=f"Vendor {vid} not ACTIVE")
        rfq = RfqRound(
            tenant_id=self.tenant_id,
            requirement_id=requirement_id,
            vendor_ids=list(vendor_ids),
            due_at=due_at,
            status="OPEN",
            notes=notes,
        )
        req.status = "RFQ_SENT"
        req.updated_at = utcnow()
        self.session.add(rfq)
        self.session.add(req)
        self.session.commit()
        self.session.refresh(rfq)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="SOURCING.RFQ_OPENED",
            payload={"rfq_id": rfq.rfq_id, "requirement_id": requirement_id, "vendors": vendor_ids},
            idempotency_key=f"rfq-{rfq.rfq_id}",
            aggregate_type="RfqRound",
            aggregate_id=rfq.rfq_id,
        )
        return rfq

    def submit_quote(
        self,
        rfq_id: str,
        *,
        vendor_id: str,
        amount: float,
        currency: str = "INR",
        lead_time_days: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> VendorQuote:
        rfq = self.session.get(RfqRound, rfq_id)
        if not rfq or rfq.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="RFQ not found")
        if vendor_id not in (rfq.vendor_ids or []):
            raise HTTPException(status_code=403, detail="Vendor not invited to this RFQ")
        quote = VendorQuote(
            tenant_id=self.tenant_id,
            rfq_id=rfq_id,
            vendor_id=vendor_id,
            amount=float(amount),
            currency=currency,
            lead_time_days=lead_time_days,
            notes=notes,
            status="SUBMITTED",
        )
        # Deterministic score: lower price + faster lead time
        lead = float(lead_time_days or 30)
        quote.score = max(0.0, 100.0 - (float(amount) / 1000.0) - lead)
        req = self.session.get(SourcingRequirement, rfq.requirement_id)
        if req:
            req.status = "EVALUATION"
            req.updated_at = utcnow()
            self.session.add(req)
        self.session.add(quote)
        self.session.commit()
        self.session.refresh(quote)
        return quote

    def compare_quotes(self, rfq_id: str) -> list[dict[str, Any]]:
        rows = self.session.exec(
            select(VendorQuote).where(VendorQuote.tenant_id == self.tenant_id, VendorQuote.rfq_id == rfq_id)
        ).all()
        ranked = sorted(rows, key=lambda q: (-(q.score or 0), q.amount))
        return [
            {
                "quote_id": q.quote_id,
                "vendor_id": q.vendor_id,
                "amount": q.amount,
                "lead_time_days": q.lead_time_days,
                "score": q.score,
                "status": q.status,
            }
            for q in ranked
        ]

    def award(self, rfq_id: str, quote_id: str) -> dict[str, Any]:
        quote = self.session.get(VendorQuote, quote_id)
        rfq = self.session.get(RfqRound, rfq_id)
        if not quote or not rfq or quote.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Quote/RFQ not found")
        if quote.rfq_id != rfq_id:
            raise HTTPException(status_code=400, detail="Quote does not belong to RFQ")
        others = self.session.exec(
            select(VendorQuote).where(VendorQuote.rfq_id == rfq_id, VendorQuote.quote_id != quote_id)
        ).all()
        for o in others:
            o.status = "REJECTED"
            self.session.add(o)
        quote.status = "AWARDED"
        rfq.status = "AWARDED"
        req = self.session.get(SourcingRequirement, rfq.requirement_id)
        if req:
            req.status = "AWARDED"
            req.award_vendor_id = quote.vendor_id
            req.updated_at = utcnow()
            self.session.add(req)
        self.session.add(quote)
        self.session.add(rfq)
        self.session.commit()
        return {
            "awarded": True,
            "vendor_id": quote.vendor_id,
            "quote_id": quote.quote_id,
            "amount": quote.amount,
            "requirement_id": rfq.requirement_id,
        }
