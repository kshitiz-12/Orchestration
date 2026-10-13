"""Facilities enterprise masters — catalogue, space, compliance, BCP, chargeback, inventory controls.

Scope: facilities.docx §§2–11 excluding real-estate/lease and mobile/IoT field capture.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.facilities import (
    BcpPlan,
    ChargebackRule,
    ComplianceRequirement,
    EmergencyDrill,
    EnterpriseServiceItem,
    EsgMetric,
    InventoryCycleCount,
    ItemEntitlement,
    PmJobPlan,
    SoftServiceSchedule,
    SpaceUnit,
    WorkOrder,
    RiskRegisterItem,
)
from app.models.org import Asset, Location, StockSku, utcnow
from app.services.amc_gate import amc_coverage_hint
from app.services.outbox import OutboxService


_SOFT_TYPES = {"HOUSEKEEPING", "HYGIENE", "PEST", "LANDSCAPING", "WASTE"}
_WO_STATUSES = {
    "OPEN",
    "TRIAGED",
    "APPROVED",
    "ASSIGNED",
    "IN_PROGRESS",
    "PENDING_PARTS",
    "PENDING_ACCEPTANCE",
    "CLOSED",
    "CANCELLED",
}


class FacilitiesEnterpriseService:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    # ── Location master (§2.3) ──────────────────────────────────────────────

    def upsert_location_profile(
        self,
        location_id: str,
        *,
        address: Optional[str] = None,
        cost_centre: Optional[str] = None,
        owner_email: Optional[str] = None,
        criticality: Optional[str] = None,
        service_bundle: Optional[list] = None,
        timezone: Optional[str] = None,
        operating_hours: Optional[str] = None,
        headcount: Optional[int] = None,
        area_sqft: Optional[float] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> Location:
        loc = self.session.get(Location, location_id)
        if not loc or loc.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Location not found")
        attrs = dict(loc.attributes or {})
        patch = {
            "address": address,
            "cost_centre": cost_centre,
            "owner_email": owner_email,
            "criticality": criticality,
            "service_bundle": service_bundle,
            "timezone": timezone,
            "operating_hours": operating_hours,
            "headcount": headcount,
            "area_sqft": area_sqft,
        }
        for k, v in patch.items():
            if v is not None:
                attrs[k] = v
        if extra:
            attrs.update(extra)
        # Strip any lease/real-estate keys if callers slip them in
        for banned in ("lease_id", "rent", "landlord", "lease_end", "security_deposit"):
            attrs.pop(banned, None)
        loc.attributes = attrs
        loc.updated_at = utcnow()
        self.session.add(loc)
        self.session.commit()
        self.session.refresh(loc)
        return loc

    def location_completeness(self, location_id: str) -> dict[str, Any]:
        loc = self.session.get(Location, location_id)
        if not loc or loc.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Location not found")
        attrs = loc.attributes or {}
        required = ["address", "cost_centre", "owner_email", "criticality", "service_bundle"]
        missing = [k for k in required if not attrs.get(k)]
        return {
            "location_id": location_id,
            "complete": not missing,
            "missing": missing,
            "attributes": attrs,
        }

    # ── Space master (§3.3) ─────────────────────────────────────────────────

    def upsert_space(
        self,
        *,
        code: str,
        name: str,
        space_type: str = "ROOM",
        location_id: Optional[str] = None,
        parent_space_id: Optional[str] = None,
        room_type: Optional[str] = None,
        capacity_seats: int = 0,
        area_sqft: float = 0.0,
        amenities: Optional[list] = None,
        accessibility: Optional[list] = None,
        hvac_zone: Optional[str] = None,
        fire_zone: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> SpaceUnit:
        code_u = code.strip().upper()
        existing = self.session.exec(
            select(SpaceUnit).where(
                SpaceUnit.tenant_id == self.tenant_id,
                SpaceUnit.code == code_u,
            )
        ).first()
        if existing:
            row = existing
            row.name = name.strip()
            row.space_type = space_type.strip().upper()
            row.location_id = location_id or row.location_id
            row.parent_space_id = parent_space_id
            row.room_type = room_type
            row.capacity_seats = capacity_seats
            row.area_sqft = area_sqft
            row.amenities = amenities or row.amenities or []
            row.accessibility = accessibility or row.accessibility or []
            row.hvac_zone = hvac_zone
            row.fire_zone = fire_zone
            if attributes:
                row.attributes = {**(row.attributes or {}), **attributes}
            row.updated_at = utcnow()
        else:
            row = SpaceUnit(
                tenant_id=self.tenant_id,
                location_id=location_id,
                parent_space_id=parent_space_id,
                code=code_u,
                name=name.strip(),
                space_type=space_type.strip().upper(),
                room_type=room_type,
                capacity_seats=capacity_seats,
                area_sqft=area_sqft,
                amenities=amenities or [],
                accessibility=accessibility or [],
                hvac_zone=hvac_zone,
                fire_zone=fire_zone,
                attributes=attributes or {},
            )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_spaces(self, location_id: Optional[str] = None) -> list[SpaceUnit]:
        stmt = select(SpaceUnit).where(SpaceUnit.tenant_id == self.tenant_id, SpaceUnit.status == "ACTIVE")
        if location_id:
            stmt = stmt.where(SpaceUnit.location_id == location_id)
        return list(self.session.exec(stmt.order_by(SpaceUnit.code)).all())

    # ── Service catalogue (§4.1) ────────────────────────────────────────────

    def upsert_service_item(self, *, service_code: str, service_family: str, service_item: str, **kwargs: Any) -> EnterpriseServiceItem:
        code = service_code.strip().upper()
        existing = self.session.exec(
            select(EnterpriseServiceItem).where(
                EnterpriseServiceItem.tenant_id == self.tenant_id,
                EnterpriseServiceItem.service_code == code,
            )
        ).first()
        fields = {
            "service_family": service_family.strip().upper(),
            "service_item": service_item.strip(),
            "description": kwargs.get("description"),
            "inclusions": kwargs.get("inclusions") or [],
            "exclusions": kwargs.get("exclusions") or [],
            "dependencies": kwargs.get("dependencies") or [],
            "eligible_requesters": kwargs.get("eligible_requesters") or ["EMPLOYEE"],
            "applicable_site_types": kwargs.get("applicable_site_types") or ["BRANCH", "BUILDING"],
            "criticality": (kwargs.get("criticality") or "MEDIUM").upper(),
            "operating_window": kwargs.get("operating_window") or "BUSINESS_HOURS",
            "mandatory_fields": kwargs.get("mandatory_fields") or [],
            "attachment_requirements": kwargs.get("attachment_requirements") or [],
            "approval_conditions": kwargs.get("approval_conditions") or [],
            "fulfilment_checklist": kwargs.get("fulfilment_checklist") or [],
            "sla_response_hours": float(kwargs.get("sla_response_hours") or 4),
            "sla_attendance_hours": float(kwargs.get("sla_attendance_hours") or 8),
            "sla_resolution_hours": float(kwargs.get("sla_resolution_hours") or 48),
            "sla_restoration_hours": kwargs.get("sla_restoration_hours"),
            "pause_rules": kwargs.get("pause_rules") or [],
            "business_calendar": kwargs.get("business_calendar") or "DEFAULT",
            "owner_team": kwargs.get("owner_team") or "FACILITIES",
            "primary_vendor_id": kwargs.get("primary_vendor_id"),
            "backup_vendor_id": kwargs.get("backup_vendor_id"),
            "escalation_chain": kwargs.get("escalation_chain") or [],
            "after_hours_contact": kwargs.get("after_hours_contact"),
            "unit_of_measure": kwargs.get("unit_of_measure") or "each",
            "rate": float(kwargs.get("rate") or 0),
            "currency": (kwargs.get("currency") or "INR").upper(),
            "tax_code": kwargs.get("tax_code"),
            "minimum_billing": float(kwargs.get("minimum_billing") or 0),
            "escalation_formula": kwargs.get("escalation_formula"),
            "free_entitlement": float(kwargs.get("free_entitlement") or 0),
            "chargeback_rule_code": kwargs.get("chargeback_rule_code"),
            "closure_codes": kwargs.get("closure_codes") or ["RESOLVED", "DUPLICATE", "CANCELLED"],
            "evidence_retention_days": int(kwargs.get("evidence_retention_days") or 365),
            "reopen_window_hours": int(kwargs.get("reopen_window_hours") or 72),
            "status": "ACTIVE",
            "attributes": kwargs.get("attributes") or {},
        }
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.updated_at = utcnow()
            row = existing
        else:
            row = EnterpriseServiceItem(tenant_id=self.tenant_id, service_code=code, **fields)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def list_service_items(self, family: Optional[str] = None) -> list[EnterpriseServiceItem]:
        stmt = select(EnterpriseServiceItem).where(
            EnterpriseServiceItem.tenant_id == self.tenant_id,
            EnterpriseServiceItem.status == "ACTIVE",
        )
        if family:
            stmt = stmt.where(EnterpriseServiceItem.service_family == family.strip().upper())
        return list(self.session.exec(stmt.order_by(EnterpriseServiceItem.service_code)).all())

    def get_service_item(self, service_code: str) -> Optional[EnterpriseServiceItem]:
        return self.session.exec(
            select(EnterpriseServiceItem).where(
                EnterpriseServiceItem.tenant_id == self.tenant_id,
                EnterpriseServiceItem.service_code == service_code.strip().upper(),
            )
        ).first()

    # ── Asset completeness (§5.2) ───────────────────────────────────────────

    ASSET_REQUIRED = [
        "make",
        "model",
        "serial",
        "criticality",
        "commissioned_on",
        "warranty_end",
        "owner_email",
    ]

    def enrich_asset(self, asset_id: str, profile: dict[str, Any]) -> Asset:
        asset = self.session.get(Asset, asset_id)
        if not asset or asset.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Asset not found")
        attrs = dict(asset.attributes or {})
        attrs.update({k: v for k, v in profile.items() if v is not None})
        asset.attributes = attrs
        asset.updated_at = utcnow()
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        return asset

    def asset_completeness(self, asset_id: str) -> dict[str, Any]:
        asset = self.session.get(Asset, asset_id)
        if not asset or asset.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Asset not found")
        attrs = asset.attributes or {}
        missing = [k for k in self.ASSET_REQUIRED if not attrs.get(k)]
        if not asset.tag:
            missing.append("tag")
        if not asset.location_id:
            missing.append("location_id")
        return {
            "asset_id": asset_id,
            "complete": not missing,
            "missing": missing,
            "amc": amc_coverage_hint(
                self.session,
                self.tenant_id,
                category=(attrs.get("maintenance_category") or asset.type or "maintenance").lower(),
                asset_id=asset_id,
                location_id=asset.location_id,
            ),
        }

    def resolve_amc_vendor_call(
        self,
        *,
        category: str,
        asset_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> dict[str, Any]:
        hint = amc_coverage_hint(
            self.session,
            self.tenant_id,
            category=category,
            asset_id=asset_id,
            location_id=location_id,
        )
        if hint.get("has_coverage") and hint.get("obligations"):
            top = hint["obligations"][0]
            OutboxService(self.session, self.tenant_id).enqueue(
                event_type="AMC.VENDOR_CALL",
                payload={
                    "obligation_id": top["obligation_id"],
                    "vendor_id": top.get("vendor_id"),
                    "vendor_email": top.get("vendor_email"),
                    "asset_id": asset_id,
                    "category": category,
                },
                idempotency_key=f"amc-call-{top['obligation_id']}-{asset_id or 'na'}-{utcnow().date().isoformat()}",
                aggregate_type="AmcObligation",
                aggregate_id=top["obligation_id"],
            )
            return {**hint, "action": "VENDOR_CALLED", "called": top}
        return {**hint, "action": "NO_COVERAGE", "called": None}

    # ── PM job plans (§5.4) ─────────────────────────────────────────────────

    def upsert_job_plan(
        self,
        *,
        code: str,
        title: str,
        asset_types: Optional[list] = None,
        tasks: Optional[list] = None,
        parts: Optional[list] = None,
        estimated_hours: float = 1.0,
        safety_permit: Optional[str] = None,
        competency: Optional[str] = None,
        evidence_required: Optional[list] = None,
    ) -> PmJobPlan:
        code_u = code.strip().upper()
        existing = self.session.exec(
            select(PmJobPlan).where(PmJobPlan.tenant_id == self.tenant_id, PmJobPlan.code == code_u)
        ).first()
        if existing:
            row = existing
            row.title = title.strip()
            row.asset_types = asset_types or row.asset_types or []
            row.tasks = tasks or row.tasks or []
            row.parts = parts or row.parts or []
            row.estimated_hours = estimated_hours
            row.safety_permit = safety_permit
            row.competency = competency
            row.evidence_required = evidence_required or row.evidence_required or []
            row.updated_at = utcnow()
        else:
            row = PmJobPlan(
                tenant_id=self.tenant_id,
                code=code_u,
                title=title.strip(),
                asset_types=asset_types or [],
                tasks=tasks or [],
                parts=parts or [],
                estimated_hours=estimated_hours,
                safety_permit=safety_permit,
                competency=competency,
                evidence_required=evidence_required or [],
            )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # ── Soft-service schedules → rounds (§4/§9) ─────────────────────────────

    def create_soft_schedule(
        self,
        *,
        service_type: str,
        frequency_days: int = 1,
        location_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        checklist: Optional[list] = None,
    ) -> SoftServiceSchedule:
        st = service_type.strip().upper()
        if st not in _SOFT_TYPES:
            raise HTTPException(status_code=400, detail=f"service_type must be one of {sorted(_SOFT_TYPES)}")
        row = SoftServiceSchedule(
            tenant_id=self.tenant_id,
            location_id=location_id,
            service_type=st,
            frequency_days=max(1, int(frequency_days)),
            vendor_id=vendor_id,
            contract_id=contract_id,
            checklist=checklist or [],
            next_due_at=utcnow(),
            status="ACTIVE",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def generate_due_soft_rounds(self) -> list[dict[str, Any]]:
        from app.models.facilities import SoftServiceRound

        now = utcnow()
        due = self.session.exec(
            select(SoftServiceSchedule).where(
                SoftServiceSchedule.tenant_id == self.tenant_id,
                SoftServiceSchedule.status == "ACTIVE",
            )
        ).all()
        created: list[dict[str, Any]] = []
        for sched in due:
            if sched.next_due_at and sched.next_due_at > now:
                continue
            rnd = SoftServiceRound(
                tenant_id=self.tenant_id,
                schedule_id=sched.schedule_id,
                location_id=sched.location_id,
                service_type=sched.service_type,
                scheduled_for=now,
                status="SCHEDULED",
            )
            self.session.add(rnd)
            sched.next_due_at = now + timedelta(days=sched.frequency_days or 1)
            sched.updated_at = now
            self.session.add(sched)
            self.session.flush()
            created.append({"round_id": rnd.round_id, "schedule_id": sched.schedule_id, "service_type": sched.service_type})
        self.session.commit()
        return created

    def complete_soft_round_with_ses(
        self,
        round_id: str,
        *,
        score: Optional[float] = None,
        findings: Optional[list] = None,
        evidence_ids: Optional[list] = None,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        from app.models.facilities import SoftServiceRound
        from app.models.finance import ServiceEntry

        rnd = self.session.get(SoftServiceRound, round_id)
        if not rnd or rnd.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Soft round not found")
        today = utcnow().date().isoformat()
        ses = ServiceEntry(
            tenant_id=self.tenant_id,
            quantity=1.0,
            unit_rate=0.0,
            amount=0.0,
            period_from=today,
            period_to=today,
            status="DRAFT",
            notes=f"Soft service {rnd.service_type} round {rnd.round_id}; score={score}",
        )
        self.session.add(ses)
        self.session.flush()
        rnd.completed_at = utcnow()
        rnd.score = score
        rnd.findings = findings or []
        rnd.evidence_ids = evidence_ids or []
        rnd.status = "DONE"
        rnd.notes = notes
        rnd.ses_id = ses.ses_id
        self.session.add(rnd)
        self.session.commit()
        self.session.refresh(rnd)
        return {"round_id": rnd.round_id, "status": rnd.status, "ses_id": rnd.ses_id, "score": rnd.score}

    # ── Work orders (§9.3) ──────────────────────────────────────────────────

    def create_work_order(
        self,
        *,
        title: str,
        priority: str = "P3",
        description: Optional[str] = None,
        location_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        service_code: Optional[str] = None,
        requester_email: Optional[str] = None,
        outcome_id: Optional[str] = None,
    ) -> WorkOrder:
        svc = self.get_service_item(service_code) if service_code else None
        now = utcnow()
        sla_resp = timedelta(hours=float(svc.sla_response_hours if svc else 4))
        sla_res = timedelta(hours=float(svc.sla_resolution_hours if svc else 48))
        amc = None
        if asset_id or service_code:
            cat = (svc.service_family if svc else "maintenance") or "maintenance"
            amc = amc_coverage_hint(
                self.session,
                self.tenant_id,
                category=cat.lower(),
                asset_id=asset_id,
                location_id=location_id,
            )
        vendor_id = None
        amc_id = None
        if amc and amc.get("has_coverage") and amc.get("obligations"):
            vendor_id = amc["obligations"][0].get("vendor_id")
            amc_id = amc["obligations"][0].get("obligation_id")
        elif svc and svc.primary_vendor_id:
            vendor_id = svc.primary_vendor_id

        # Duplicate detection: open WO same asset+title
        dup = None
        if asset_id:
            recent = self.session.exec(
                select(WorkOrder).where(
                    WorkOrder.tenant_id == self.tenant_id,
                    WorkOrder.asset_id == asset_id,
                )
            ).all()
            for r in recent:
                if r.status in {"CLOSED", "CANCELLED"}:
                    continue
                if (r.title or "").strip().lower() == title.strip().lower():
                    dup = r
                    break

        row = WorkOrder(
            tenant_id=self.tenant_id,
            entity_id=self.entity_id,
            outcome_id=outcome_id,
            location_id=location_id,
            asset_id=asset_id,
            service_code=service_code.strip().upper() if service_code else None,
            title=title.strip(),
            description=description,
            priority=priority.strip().upper(),
            status="OPEN" if not dup else "TRIAGED",
            requester_email=(requester_email or "").strip().lower() or None,
            vendor_id=vendor_id,
            amc_obligation_id=amc_id,
            sla_response_at=now + sla_resp,
            sla_resolve_at=now + sla_res,
            duplicate_of=dup.work_order_id if dup else None,
            attributes={"amc_hint": amc} if amc else {},
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        OutboxService(self.session, self.tenant_id).enqueue(
            event_type="WO.CREATED",
            payload={"work_order_id": row.work_order_id, "priority": row.priority, "duplicate_of": row.duplicate_of},
            idempotency_key=f"wo-{row.work_order_id}",
            aggregate_type="WorkOrder",
            aggregate_id=row.work_order_id,
        )
        return row

    def advance_work_order(
        self,
        work_order_id: str,
        status: str,
        *,
        assignee_email: Optional[str] = None,
        closure_code: Optional[str] = None,
        evidence_ids: Optional[list] = None,
        parts_used: Optional[list] = None,
        labour_hours: Optional[float] = None,
        cost_amount: Optional[float] = None,
    ) -> WorkOrder:
        row = self.session.get(WorkOrder, work_order_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Work order not found")
        st = status.strip().upper()
        if st not in _WO_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {sorted(_WO_STATUSES)}")
        now = utcnow()
        row.status = st
        if assignee_email:
            row.assignee_email = assignee_email.strip().lower()
        if st == "ASSIGNED" and not row.acknowledged_at:
            row.acknowledged_at = now
        if st == "IN_PROGRESS" and not row.attended_at:
            row.attended_at = now
        if st in {"PENDING_ACCEPTANCE", "CLOSED"} and not row.resolved_at:
            row.resolved_at = now
        if st == "CLOSED":
            row.closed_at = now
            row.closure_code = closure_code or row.closure_code or "RESOLVED"
        if evidence_ids is not None:
            row.evidence_ids = evidence_ids
        if parts_used is not None:
            row.parts_used = parts_used
        if labour_hours is not None:
            row.labour_hours = labour_hours
        if cost_amount is not None:
            row.cost_amount = cost_amount
        row.updated_at = now
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # ── Inventory (§6) ──────────────────────────────────────────────────────

    def upsert_item_master(
        self,
        *,
        sku_code: str,
        name: str,
        location_id: Optional[str] = None,
        **kwargs: Any,
    ) -> StockSku:
        code = sku_code.strip().upper()
        stmt = select(StockSku).where(StockSku.tenant_id == self.tenant_id, StockSku.sku_code == code)
        if location_id:
            stmt = stmt.where(StockSku.location_id == location_id)
        existing = self.session.exec(stmt).first()
        fields = {
            "name": name.strip(),
            "category": kwargs.get("category"),
            "qty_on_hand": float(kwargs.get("qty_on_hand", existing.qty_on_hand if existing else 0) or 0),
            "reorder_min": float(kwargs.get("reorder_min") or 0),
            "reorder_qty": float(kwargs.get("reorder_qty") or 0),
            "safety_stock": float(kwargs.get("safety_stock") or 0),
            "max_stock": float(kwargs.get("max_stock") or 0),
            "unit": kwargs.get("unit") or "each",
            "pack_size": float(kwargs.get("pack_size") or 1),
            "bin_code": kwargs.get("bin_code"),
            "batch_code": kwargs.get("batch_code"),
            "expires_on": kwargs.get("expires_on"),
            "controlled_item": bool(kwargs.get("controlled_item") or False),
            "hazardous": bool(kwargs.get("hazardous") or False),
            "standard_item": bool(kwargs.get("standard_item", True)),
            "contracted_rate": float(kwargs.get("contracted_rate") or 0),
            "lead_time_days": int(kwargs.get("lead_time_days") or 0),
            "min_order_qty": float(kwargs.get("min_order_qty") or 0),
            "substitute_sku_code": kwargs.get("substitute_sku_code"),
            "gl_account": kwargs.get("gl_account"),
            "budget_head": kwargs.get("budget_head"),
            "chargeback_rule_code": kwargs.get("chargeback_rule_code"),
            "vendor_id": kwargs.get("vendor_id"),
            "status": "ACTIVE",
            "attributes": kwargs.get("attributes") or (existing.attributes if existing else {}) or {},
        }
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.updated_at = utcnow()
            row = existing
        else:
            row = StockSku(tenant_id=self.tenant_id, location_id=location_id, sku_code=code, **fields)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def set_entitlement(
        self,
        *,
        sku_code: str,
        monthly_qty: float,
        role: str = "*",
        location_type: str = "*",
        max_per_request: float = 0.0,
        requires_approval_above: Optional[float] = None,
    ) -> ItemEntitlement:
        code = sku_code.strip().upper()
        existing = self.session.exec(
            select(ItemEntitlement).where(
                ItemEntitlement.tenant_id == self.tenant_id,
                ItemEntitlement.sku_code == code,
                ItemEntitlement.role == role,
                ItemEntitlement.location_type == location_type,
            )
        ).first()
        if existing:
            existing.monthly_qty = monthly_qty
            existing.max_per_request = max_per_request
            existing.requires_approval_above = requires_approval_above
            existing.status = "ACTIVE"
            existing.updated_at = utcnow()
            row = existing
        else:
            row = ItemEntitlement(
                tenant_id=self.tenant_id,
                sku_code=code,
                role=role,
                location_type=location_type,
                monthly_qty=monthly_qty,
                max_per_request=max_per_request,
                requires_approval_above=requires_approval_above,
            )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def check_issue_entitlement(
        self,
        *,
        sku_code: str,
        qty: float,
        role: str = "*",
        location_type: str = "*",
    ) -> dict[str, Any]:
        code = sku_code.strip().upper()
        rows = self.session.exec(
            select(ItemEntitlement).where(
                ItemEntitlement.tenant_id == self.tenant_id,
                ItemEntitlement.sku_code == code,
                ItemEntitlement.status == "ACTIVE",
            )
        ).all()
        match = None
        for r in rows:
            if r.role in {role, "*"} and r.location_type in {location_type, "*"}:
                match = r
                break
        if not match:
            return {"ok": True, "requires_approval": False, "reason": "No entitlement configured — pass-through"}
        if match.max_per_request and qty > match.max_per_request:
            return {"ok": False, "requires_approval": True, "reason": f"Exceeds max_per_request {match.max_per_request}"}
        if match.requires_approval_above is not None and qty > match.requires_approval_above:
            return {"ok": True, "requires_approval": True, "reason": "Above approval threshold"}
        return {"ok": True, "requires_approval": False, "reason": "Within entitlement", "monthly_qty": match.monthly_qty}

    def record_cycle_count(
        self,
        *,
        sku_id: str,
        counted_qty: float,
        counted_by: Optional[str] = None,
        notes: Optional[str] = None,
        adjust: bool = False,
    ) -> InventoryCycleCount:
        sku = self.session.get(StockSku, sku_id)
        if not sku or sku.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="SKU not found")
        system_qty = float(sku.qty_on_hand or 0)
        variance = float(counted_qty) - system_qty
        row = InventoryCycleCount(
            tenant_id=self.tenant_id,
            location_id=sku.location_id,
            sku_id=sku_id,
            counted_qty=counted_qty,
            system_qty=system_qty,
            variance=variance,
            counted_by=counted_by,
            status="ADJUSTED" if adjust else "RECORDED",
            notes=notes,
        )
        if adjust:
            sku.qty_on_hand = float(counted_qty)
            sku.updated_at = utcnow()
            self.session.add(sku)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def expiring_batches(self, within_days: int = 30) -> list[dict[str, Any]]:
        cutoff = (date.today() + timedelta(days=within_days)).isoformat()
        rows = self.session.exec(
            select(StockSku).where(StockSku.tenant_id == self.tenant_id, StockSku.status == "ACTIVE")
        ).all()
        out = []
        for sku in rows:
            if sku.expires_on and sku.expires_on <= cutoff:
                out.append(
                    {
                        "sku_id": sku.sku_id,
                        "sku_code": sku.sku_code,
                        "expires_on": sku.expires_on,
                        "qty_on_hand": sku.qty_on_hand,
                        "batch_code": sku.batch_code,
                    }
                )
        return out

    # ── Chargeback (§7.5) ───────────────────────────────────────────────────

    def upsert_chargeback_rule(
        self,
        *,
        code: str,
        name: str,
        method: str,
        drivers: Optional[dict] = None,
        allocations: Optional[list] = None,
        subsidy_pct: float = 0.0,
    ) -> ChargebackRule:
        code_u = code.strip().upper()
        allowed = {"DIRECT", "SHARED_FIXED", "AREA", "HEADCOUNT", "METERED", "TRANSACTION", "HYBRID", "CENTRAL"}
        method_u = method.strip().upper()
        if method_u not in allowed:
            raise HTTPException(status_code=400, detail=f"method must be one of {sorted(allowed)}")
        existing = self.session.exec(
            select(ChargebackRule).where(ChargebackRule.tenant_id == self.tenant_id, ChargebackRule.code == code_u)
        ).first()
        if existing:
            existing.name = name.strip()
            existing.method = method_u
            existing.drivers = drivers or existing.drivers or {}
            existing.allocations = allocations or existing.allocations or []
            existing.subsidy_pct = subsidy_pct
            existing.updated_at = utcnow()
            row = existing
        else:
            row = ChargebackRule(
                tenant_id=self.tenant_id,
                code=code_u,
                name=name.strip(),
                method=method_u,
                drivers=drivers or {},
                allocations=allocations or [],
                subsidy_pct=subsidy_pct,
            )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def allocate_chargeback(self, rule_code: str, amount: float) -> dict[str, Any]:
        rule = self.session.exec(
            select(ChargebackRule).where(
                ChargebackRule.tenant_id == self.tenant_id,
                ChargebackRule.code == rule_code.strip().upper(),
                ChargebackRule.status == "ACTIVE",
            )
        ).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Chargeback rule not found")
        net = float(amount) * (1.0 - float(rule.subsidy_pct or 0) / 100.0)
        lines: list[dict[str, Any]] = []
        if rule.method == "DIRECT":
            target = (rule.drivers or {}).get("cost_centre") or (rule.allocations[0] if rule.allocations else None)
            lines.append({"target": target, "amount": net, "method": "DIRECT"})
        elif rule.method == "CENTRAL":
            lines.append({"target": "CENTRAL", "amount": net, "method": "CENTRAL"})
        elif rule.method in {"SHARED_FIXED", "AREA", "HEADCOUNT", "METERED", "TRANSACTION", "HYBRID"}:
            allocs = rule.allocations or []
            if not allocs:
                raise HTTPException(status_code=400, detail="Rule has no allocations")
            total_weight = sum(float(a.get("weight") or a.get("pct") or 0) for a in allocs) or 1.0
            for a in allocs:
                w = float(a.get("weight") or a.get("pct") or 0)
                lines.append(
                    {
                        "target": a.get("cost_centre") or a.get("location_id") or a.get("target"),
                        "amount": round(net * (w / total_weight), 2),
                        "weight": w,
                        "method": rule.method,
                    }
                )
        return {"rule_code": rule.code, "method": rule.method, "gross": amount, "net": net, "lines": lines}

    # ── Compliance / risk / BCP (§10) ───────────────────────────────────────

    def upsert_compliance(self, *, requirement_code: str, law_or_standard: str, **kwargs: Any) -> ComplianceRequirement:
        code = requirement_code.strip().upper()
        existing = self.session.exec(
            select(ComplianceRequirement).where(
                ComplianceRequirement.tenant_id == self.tenant_id,
                ComplianceRequirement.requirement_code == code,
            )
        ).first()
        payload = {
            "law_or_standard": law_or_standard,
            "jurisdiction": kwargs.get("jurisdiction") or "IN",
            "applicability": kwargs.get("applicability") or {},
            "location_ids": kwargs.get("location_ids") or [],
            "asset_ids": kwargs.get("asset_ids") or [],
            "licence_type": kwargs.get("licence_type"),
            "authority": kwargs.get("authority"),
            "certificate_number": kwargs.get("certificate_number"),
            "issue_date": kwargs.get("issue_date"),
            "expiry_date": kwargs.get("expiry_date"),
            "renewal_lead_days": int(kwargs.get("renewal_lead_days") or 30),
            "owner_email": kwargs.get("owner_email"),
            "reviewer_email": kwargs.get("reviewer_email"),
            "approver_email": kwargs.get("approver_email"),
            "provider": kwargs.get("provider"),
            "evidence_refs": kwargs.get("evidence_refs") or [],
            "inspection_frequency_days": kwargs.get("inspection_frequency_days"),
            "findings": kwargs.get("findings") or [],
            "corrective_actions": kwargs.get("corrective_actions") or [],
            "retention_days": int(kwargs.get("retention_days") or 2555),
            "status": (kwargs.get("status") or "COMPLIANT").upper(),
            "risk_rating": (kwargs.get("risk_rating") or "MEDIUM").upper(),
            "grace_days": int(kwargs.get("grace_days") or 0),
            "business_restriction": kwargs.get("business_restriction"),
            "attributes": kwargs.get("attributes") or {},
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            existing.updated_at = utcnow()
            row = existing
        else:
            row = ComplianceRequirement(tenant_id=self.tenant_id, requirement_code=code, **payload)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def compliance_due(self, within_days: int = 30) -> list[ComplianceRequirement]:
        today = date.today()
        rows = self.session.exec(
            select(ComplianceRequirement).where(ComplianceRequirement.tenant_id == self.tenant_id)
        ).all()
        due = []
        for r in rows:
            if not r.expiry_date:
                continue
            try:
                exp = date.fromisoformat(r.expiry_date[:10])
            except ValueError:
                continue
            lead = timedelta(days=int(r.renewal_lead_days or 30))
            grace = timedelta(days=int(r.grace_days or 0))
            if exp - lead <= today:
                if today > exp + grace:
                    r.status = "OVERDUE"
                elif r.status not in {"OVERDUE", "WAIVED"}:
                    r.status = "DUE"
                self.session.add(r)
                due.append(r)
        self.session.commit()
        return due

    def upsert_risk(self, *, title: str, **kwargs: Any) -> RiskRegisterItem:
        row = RiskRegisterItem(
            tenant_id=self.tenant_id,
            location_id=kwargs.get("location_id"),
            title=title.strip(),
            category=(kwargs.get("category") or "OPERATIONAL").upper(),
            likelihood=(kwargs.get("likelihood") or "MEDIUM").upper(),
            impact=(kwargs.get("impact") or "MEDIUM").upper(),
            inherent_score=float(kwargs.get("inherent_score") or 0),
            residual_score=float(kwargs.get("residual_score") or 0),
            controls=kwargs.get("controls") or [],
            owner_email=kwargs.get("owner_email"),
            treatment=(kwargs.get("treatment") or "MITIGATE").upper(),
            status=(kwargs.get("status") or "OPEN").upper(),
            next_review_date=kwargs.get("next_review_date"),
            attributes=kwargs.get("attributes") or {},
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def upsert_bcp_plan(
        self,
        *,
        plan_type: str,
        title: str,
        location_id: Optional[str] = None,
        **kwargs: Any,
    ) -> BcpPlan:
        pt = plan_type.strip().upper()
        existing = self.session.exec(
            select(BcpPlan).where(
                BcpPlan.tenant_id == self.tenant_id,
                BcpPlan.location_id == location_id,
                BcpPlan.plan_type == pt,
            )
        ).first()
        payload = {
            "title": title.strip(),
            "bia": kwargs.get("bia") or {},
            "dependencies": kwargs.get("dependencies") or [],
            "contact_tree": kwargs.get("contact_tree") or [],
            "command_roles": kwargs.get("command_roles") or {},
            "assembly_points": kwargs.get("assembly_points") or [],
            "alternate_workspace": kwargs.get("alternate_workspace"),
            "vendor_mobilisation": kwargs.get("vendor_mobilisation") or [],
            "critical_spares": kwargs.get("critical_spares") or [],
            "status": "ACTIVE",
            "attributes": kwargs.get("attributes") or {},
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            existing.updated_at = utcnow()
            row = existing
        else:
            row = BcpPlan(tenant_id=self.tenant_id, location_id=location_id, plan_type=pt, **payload)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def record_drill(
        self,
        plan_id: str,
        *,
        score: Optional[float] = None,
        lessons: Optional[list] = None,
        actions: Optional[list] = None,
        participants: Optional[list] = None,
        notes: Optional[str] = None,
    ) -> EmergencyDrill:
        plan = self.session.get(BcpPlan, plan_id)
        if not plan or plan.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="BCP plan not found")
        drill = EmergencyDrill(
            tenant_id=self.tenant_id,
            plan_id=plan_id,
            location_id=plan.location_id,
            score=score,
            lessons=lessons or [],
            actions=actions or [],
            participants=participants or [],
            notes=notes,
            status="COMPLETED",
        )
        plan.last_drill_at = utcnow()
        plan.updated_at = utcnow()
        self.session.add(drill)
        self.session.add(plan)
        self.session.commit()
        self.session.refresh(drill)
        return drill

    def record_esg_metric(
        self,
        *,
        metric_type: str,
        period: str,
        value: float,
        location_id: Optional[str] = None,
        unit: str = "",
        source: str = "MANUAL",
    ) -> EsgMetric:
        row = EsgMetric(
            tenant_id=self.tenant_id,
            location_id=location_id,
            metric_type=metric_type.strip().upper(),
            period=period.strip(),
            value=float(value),
            unit=unit,
            source=source,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    # ── Control tower slice ─────────────────────────────────────────────────

    def facilities_dashboard(self) -> dict[str, Any]:
        from app.models.facilities import IncidentRecord, PreventiveSchedule, SoftServiceRound

        now = utcnow()
        overdue_pm = [
            r
            for r in self.session.exec(
                select(PreventiveSchedule).where(
                    PreventiveSchedule.tenant_id == self.tenant_id,
                    PreventiveSchedule.status == "ACTIVE",
                )
            ).all()
            if r.next_due_at and r.next_due_at <= now
        ]
        open_incidents = list(
            self.session.exec(
                select(IncidentRecord).where(
                    IncidentRecord.tenant_id == self.tenant_id,
                    IncidentRecord.status != "CLOSED",
                )
            ).all()
        )
        open_wo = [
            w
            for w in self.session.exec(select(WorkOrder).where(WorkOrder.tenant_id == self.tenant_id)).all()
            if w.status not in {"CLOSED", "CANCELLED"}
        ]
        compliance_due = self.compliance_due(30)
        return {
            "overdue_pm": len(overdue_pm),
            "open_incidents": len(open_incidents),
            "urgent_incidents": sum(1 for i in open_incidents if i.deterministic_urgent),
            "open_work_orders": len(open_wo),
            "compliance_due": len(compliance_due),
            "soft_rounds_scheduled": len(
                list(
                    self.session.exec(
                        select(SoftServiceRound).where(
                            SoftServiceRound.tenant_id == self.tenant_id,
                            SoftServiceRound.status == "SCHEDULED",
                        )
                    ).all()
                )
            ),
            "expiring_batches": len(self.expiring_batches(30)),
        }
