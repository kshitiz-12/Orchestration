from typing import Any, Optional

from sqlmodel import Session, select

from app.models.org import (
    Contract,
    Invoice,
    Person,
    PurchaseOrder,
    Receipt,
    Resource,
    Vendor,
)
from app.models.outcome import Outcome


class ContextRetrievalService:
    """Retrieve ONLY relevant organisational context — never dump the DB to the LLM."""

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def for_extraction(
        self,
        event_type: Optional[str],
        requester_email: str,
        entities: Optional[dict] = None,
    ) -> dict[str, Any]:
        entities = entities or {}
        ctx: dict[str, Any] = {}
        person = self.session.exec(
            select(Person).where(Person.email == requester_email.lower())
        ).first()
        if person:
            ctx["requester"] = {
                "person_id": person.person_id,
                "name": person.name,
                "email": person.email,
                "role": person.role,
                "department": person.department,
                "site_id": person.site_id,
            }

        et = (event_type or "").upper()
        if et in {"", "UNKNOWN", "ONBOARDING", "PARKING_CONFLICT", "FURNITURE_ISSUE"}:
            if person:
                resources = self.session.exec(
                    select(Resource).where(
                        Resource.tenant_id == self.tenant_id,
                        Resource.allocated_to_person_id == person.person_id,
                    )
                ).all()
                ctx["allocated_resources"] = [
                    {
                        "resource_id": r.resource_id,
                        "type": r.type,
                        "name": r.name,
                        "status": r.status,
                        "location_id": r.location_id,
                    }
                    for r in resources
                ]
            available_seats = self.session.exec(
                select(Resource).where(
                    Resource.tenant_id == self.tenant_id,
                    Resource.type == "SEAT",
                    Resource.status == "AVAILABLE",
                )
            ).all()
            ctx["available_seats_count"] = len(available_seats)
            ctx["available_seats_sample"] = [
                {"resource_id": s.resource_id, "name": s.name, "location_id": s.location_id}
                for s in available_seats[:5]
            ]

        if et in {"", "UNKNOWN", "MEETING_ROOM"}:
            available_rooms = self.session.exec(
                select(Resource).where(
                    Resource.tenant_id == self.tenant_id,
                    Resource.type == "MEETING_ROOM",
                    Resource.status == "AVAILABLE",
                )
            ).all()
            ctx["available_meeting_rooms"] = [
                {
                    "resource_id": r.resource_id,
                    "name": r.name,
                    "capacity": (r.attributes or {}).get("capacity"),
                    "location_id": r.location_id,
                }
                for r in available_rooms
            ]
            ctx["available_meeting_rooms_count"] = len(available_rooms)

        if et in {"", "UNKNOWN", "VENDOR_ESCALATION", "INVOICE"}:
            vendors = self.session.exec(
                select(Vendor).where(Vendor.tenant_id == self.tenant_id, Vendor.status == "ACTIVE")
            ).all()
            ctx["vendors"] = [
                {"vendor_id": v.vendor_id, "name": v.name, "category": v.category, "email": v.contact_email}
                for v in vendors
            ]

        if et in {"", "UNKNOWN", "INVOICE"}:
            po_number = entities.get("po_number")
            if po_number:
                po = self.session.exec(
                    select(PurchaseOrder).where(PurchaseOrder.po_number == str(po_number))
                ).first()
                if po:
                    ctx["purchase_order"] = {
                        "po_id": po.po_id,
                        "po_number": po.po_number,
                        "vendor_id": po.vendor_id,
                        "quantity": po.quantity,
                        "unit_rate": po.unit_rate,
                        "status": po.status,
                    }
                    receipt = self.session.exec(
                        select(Receipt).where(Receipt.po_id == po.po_id)
                    ).first()
                    if receipt:
                        ctx["receipt"] = {
                            "receipt_id": receipt.receipt_id,
                            "quantity_received": receipt.quantity_received,
                            "status": receipt.status,
                        }
                    contract = None
                    if po.contract_id:
                        contract = self.session.get(Contract, po.contract_id)
                    if contract:
                        ctx["contract"] = {
                            "contract_id": contract.contract_id,
                            "rate_card": contract.rate_card,
                        }
            # Invoice history for duplicate checks (numbers only)
            invoices = self.session.exec(
                select(Invoice).where(Invoice.tenant_id == self.tenant_id)
            ).all()
            ctx["known_invoice_numbers"] = [i.invoice_number for i in invoices]

        return ctx

    def for_outcome(self, outcome: Outcome) -> dict[str, Any]:
        return self.for_extraction(outcome.template_code, outcome.requester_email or "", outcome.facts or {})
