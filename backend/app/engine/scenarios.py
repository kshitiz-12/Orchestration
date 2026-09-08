from typing import Any, Optional

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.engine.outcome_engine import OutcomeEngine
from app.models.org import Invoice, PurchaseOrder, Receipt, Resource, Vendor
from app.models.outcome import Outcome, Task
from app.schemas.ai import ExtractionResult
from app.services.communication import CommunicationService

logger = get_logger(__name__)

EVENT_TO_TEMPLATE = {
    "ONBOARDING": "ONBOARDING",
    "PARKING_CONFLICT": "PARKING_CONFLICT",
    "FURNITURE_ISSUE": "FURNITURE_ISSUE",
    "VENDOR_ESCALATION": "VENDOR_ESCALATION",
    "INVOICE": "INVOICE",
    "GENERAL": "GENERAL",
}


class ScenarioOrchestrator:
    """Applies scenario-specific deterministic rules after AI extraction."""

    def __init__(self, session: Session, tenant_id: str, communications: Optional[CommunicationService] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.engine = OutcomeEngine(session, tenant_id)
        self.comms = communications or CommunicationService(session, tenant_id)

    def orchestrate(
        self,
        *,
        extraction: ExtractionResult,
        requester_email: str,
        conversation_id: str,
        business_event_id: str,
        context: dict[str, Any],
    ) -> Outcome:
        template = EVENT_TO_TEMPLATE.get(extraction.event_type, "GENERAL")
        facts = dict(extraction.entities)
        facts["issues"] = [i.model_dump() for i in extraction.issues]
        outcome = self.engine.create_outcome_from_template(
            template_code=template,
            title=extraction.summary[:200] or extraction.event_type,
            summary=extraction.summary,
            requester_email=requester_email,
            conversation_id=conversation_id,
            business_event_id=business_event_id,
            facts=facts,
            priority=extraction.recommended_priority,
        )

        if template == "ONBOARDING":
            self._scenario_a(outcome, facts, context)
        elif template == "PARKING_CONFLICT":
            self._scenario_b_parking(outcome, facts, context)
        elif template == "FURNITURE_ISSUE":
            self._scenario_b_chair(outcome, facts, context)
        elif template == "VENDOR_ESCALATION":
            self._scenario_c(outcome, extraction)
        elif template == "INVOICE":
            self._scenario_d(outcome, facts, context, extraction)

        self.session.commit()
        self.session.refresh(outcome)
        return outcome

    def _scenario_a(self, outcome: Outcome, facts: dict, context: dict) -> None:
        available = context.get("available_seats_count", 0)
        if facts.get("permanent_seat_available") is False or available == 0:
            self.engine.create_exception(
                outcome=outcome,
                exception_type="NO_PERMANENT_SEAT",
                title="No permanent seat available",
                description="Permanent seating unavailable. Temporary alternatives require workplace manager decision.",
                options=[
                    {"code": "TEMP_HOTDESK", "label": "Reserve temporary hot-desk"},
                    {"code": "TEMP_VISITOR", "label": "Visitor seating for day-1"},
                    {"code": "DEFER_ONSITE", "label": "Defer onsite until permanent seat"},
                ],
                owner_role="WORKPLACE",
            )
            self.engine.apply_blocker(
                outcome,
                blocker_code="NO_PERMANENT_SEAT",
                blocked_task_codes=["SEAT_PERMANENT"],
                reason="No permanent seat available",
            )
            self.engine.request_approval(
                outcome=outcome,
                approval_type="SEATING_ALTERNATIVE",
                approver_role="WORKPLACE",
                payload={"options": ["TEMP_HOTDESK", "TEMP_VISITOR", "DEFER_ONSITE"]},
            )
            # Ensure independent tasks continue (laptop, ID, access, induction)
            tasks = self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
            for t in tasks:
                if t.code != "SEAT_PERMANENT" and not t.is_blocked:
                    if t.status == "NOT_STARTED":
                        t.status = "ASSIGNED"
                        self.session.add(t)

    def _scenario_b_parking(self, outcome: Outcome, facts: dict, context: dict) -> None:
        allocated = context.get("allocated_resources") or []
        parking = next((r for r in allocated if r["type"] == "PARKING_SLOT"), None)
        if parking:
            facts["verified_allocation"] = parking
            outcome.facts = {**(outcome.facts or {}), **facts}
            res = self.session.get(Resource, parking["resource_id"])
            if res:
                res.status = "CONFLICT"
                self.session.add(res)
        # Find temporary alternative
        alt = self.session.exec(
            select(Resource).where(
                Resource.tenant_id == self.tenant_id,
                Resource.type == "PARKING_SLOT",
                Resource.status == "AVAILABLE",
            )
        ).first()
        if alt:
            outcome.facts = {
                **(outcome.facts or {}),
                "temporary_alternative": {
                    "resource_id": alt.resource_id,
                    "name": alt.name,
                },
            }
            alt.status = "RESERVED"
            self.session.add(alt)
        self.engine.request_approval(
            outcome=outcome,
            approval_type="TEMP_PARKING",
            approver_role="SECURITY",
            payload={"temporary": outcome.facts.get("temporary_alternative")},
        )

    def _scenario_b_chair(self, outcome: Outcome, facts: dict, context: dict) -> None:
        # Immediate restoration + separate root cause already in template tasks
        self.engine.create_exception(
            outcome=outcome,
            exception_type="MISSING_CHAIR",
            title="Chair missing",
            description="Immediate temporary restoration and separate root-cause corrective action required.",
            severity="MEDIUM",
            owner_role="ADMIN",
        )

    def _scenario_c(self, outcome: Outcome, extraction: ExtractionResult) -> None:
        issues = [i.model_dump() for i in extraction.issues] or [
            {"issue_type": "QUALITY", "summary": extraction.summary, "severity": "MEDIUM"}
        ]
        self.engine.add_vendor_issues(outcome, issues)
        # Never auto-sanction
        if extraction.vendor_sanction:
            self.engine.request_approval(
                outcome=outcome,
                approval_type="VENDOR_SANCTION",
                approver_role="PROCUREMENT",
                payload={"recommended": False, "note": "Allegations remain UNVERIFIED"},
            )

    def _scenario_d(
        self,
        outcome: Outcome,
        facts: dict,
        context: dict,
        extraction: ExtractionResult,
    ) -> None:
        invoice_number = str(facts.get("invoice_number") or facts.get("invoice_no") or "")
        amount = float(facts.get("amount") or 0)
        quantity = float(facts.get("quantity") or 0)
        unit_rate = float(facts.get("unit_rate") or facts.get("rate") or 0)
        po_number = facts.get("po_number")
        bank_changed = bool(facts.get("bank_details_changed")) or extraction.entities.get("bank_details_changed")

        # Duplicate invoice check
        if invoice_number:
            dup = self.session.exec(
                select(Invoice).where(
                    Invoice.tenant_id == self.tenant_id,
                    Invoice.invoice_number == invoice_number,
                )
            ).first()
            if dup:
                inv = Invoice(
                    tenant_id=self.tenant_id,
                    invoice_number=invoice_number,
                    amount=amount,
                    quantity=quantity,
                    unit_rate=unit_rate,
                    match_status="DUPLICATE",
                    outcome_id=outcome.outcome_id,
                    bank_details_changed=bool(bank_changed),
                    attributes={"duplicate_of": dup.invoice_id},
                )
                # Use unique constraint carefully — append suffix for record
                inv.invoice_number = f"{invoice_number}#DUP#{outcome.case_reference}"
                self.session.add(inv)
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="DUPLICATE_INVOICE",
                    title="Duplicate invoice detected",
                    description=f"Invoice {invoice_number} already exists ({dup.invoice_id})",
                    severity="HIGH",
                    owner_role="FINANCE",
                )
                self.engine.apply_blocker(
                    outcome,
                    "DUPLICATE_INVOICE",
                    ["ERP_HANDOFF", "PAYMENT_APPROVAL"],
                    "Duplicate invoice — settlement blocked",
                )
                return

        po = None
        if po_number:
            po = self.session.exec(
                select(PurchaseOrder).where(PurchaseOrder.po_number == str(po_number))
            ).first()
        receipt = None
        if po:
            receipt = self.session.exec(select(Receipt).where(Receipt.po_id == po.po_id)).first()

        match_status = "PENDING_REVIEW"
        if bank_changed:
            match_status = "BANK_CHANGE_FLAGGED"
            self.engine.create_exception(
                outcome=outcome,
                exception_type="BANK_DETAILS_CHANGE",
                title="Bank details change requested",
                description="Independent authorised verification required. No automatic update.",
                severity="CRITICAL",
                owner_role="FINANCE",
            )
            self.engine.request_approval(
                outcome=outcome,
                approval_type="BANK_DETAILS_VERIFICATION",
                approver_role="FINANCE",
                payload={"source": "email", "auto_update": False},
            )
        elif not po:
            match_status = "MISSING_PO"
            self.engine.create_exception(
                outcome=outcome,
                exception_type="MISSING_PO",
                title="Purchase order missing",
                description="Invoice cannot be matched without PO",
                owner_role="PROCUREMENT",
            )
        elif not receipt:
            match_status = "MISSING_RECEIPT"
            self.engine.create_exception(
                outcome=outcome,
                exception_type="MISSING_RECEIPT",
                title="Goods receipt / service entry missing",
                description="Three-way match requires receipt/service entry",
                owner_role="PROCUREMENT",
            )
        else:
            # Deterministic three-way match with prototype tolerances
            qty_tol = 0.0
            rate_tol = 0.01
            if quantity and abs(quantity - receipt.quantity_received) > qty_tol:
                match_status = "QUANTITY_MISMATCH"
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="QUANTITY_MISMATCH",
                    title="Invoice quantity mismatch",
                    description=f"Invoice qty {quantity} vs receipt {receipt.quantity_received}",
                    owner_role="PROCUREMENT",
                )
            elif unit_rate and abs(unit_rate - po.unit_rate) > rate_tol:
                match_status = "RATE_MISMATCH"
                self.engine.create_exception(
                    outcome=outcome,
                    exception_type="RATE_MISMATCH",
                    title="Invoice rate mismatch",
                    description=f"Invoice rate {unit_rate} vs PO {po.unit_rate}",
                    owner_role="FINANCE",
                )
            else:
                expected = po.quantity * po.unit_rate
                if amount and abs(amount - expected) > 1.0:
                    match_status = "RATE_MISMATCH"
                    self.engine.create_exception(
                        outcome=outcome,
                        exception_type="AMOUNT_MISMATCH",
                        title="Invoice amount mismatch",
                        description=f"Invoice amount {amount} vs expected {expected}",
                        owner_role="FINANCE",
                    )
                else:
                    match_status = "MATCHED"
                    self.engine.request_approval(
                        outcome=outcome,
                        approval_type="INVOICE_PAYMENT_APPROVAL",
                        approver_role="FINANCE",
                        payload={
                            "invoice_number": invoice_number,
                            "amount": amount,
                            "po_number": po.po_number,
                            "auto_payment": False,
                        },
                    )

        vendor_id = po.vendor_id if po else None
        if not vendor_id and facts.get("vendor_name"):
            vendor = self.session.exec(
                select(Vendor).where(Vendor.name == facts["vendor_name"])
            ).first()
            vendor_id = vendor.vendor_id if vendor else None

        inv = Invoice(
            tenant_id=self.tenant_id,
            vendor_id=vendor_id,
            po_id=po.po_id if po else None,
            receipt_id=receipt.receipt_id if receipt else None,
            invoice_number=invoice_number or f"UNKNOWN-{outcome.case_reference}",
            amount=amount,
            quantity=quantity,
            unit_rate=unit_rate,
            match_status=match_status,
            bank_details_changed=bool(bank_changed),
            outcome_id=outcome.outcome_id,
            erp_handoff_status="NOT_STARTED",
            attributes={"note": "LLM must not approve payment"},
        )
        self.session.add(inv)
        # Never auto-release payment
        outcome.facts = {
            **(outcome.facts or {}),
            "invoice_match_status": match_status,
            "payment_auto_approved": False,
        }
        self.session.add(outcome)
