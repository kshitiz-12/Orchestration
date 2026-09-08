from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.connectors.mocks import MockERPConnector
from app.models.intake import ProcessingJob
from app.models.org import Invoice, PurchaseOrder, Receipt, Resource, Vendor
from app.models.org import BusinessRule, NotificationTemplate, OutcomeTemplate
from app.services.intake import JobQueueService
from app.audit.service import AuditService
from app.core.enums import AuditAction

router = APIRouter(tags=["ops"])


@router.get("/resources")
def list_resources(
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
    type: str | None = None,
    status: str | None = None,
):
    stmt = select(Resource).where(Resource.tenant_id == tenant_id)
    if type:
        stmt = stmt.where(Resource.type == type)
    if status:
        stmt = stmt.where(Resource.status == status)
    return session.exec(stmt).all()


@router.get("/invoices")
def list_invoices(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    invoices = session.exec(select(Invoice).where(Invoice.tenant_id == tenant_id)).all()
    result = []
    for inv in invoices:
        po = session.get(PurchaseOrder, inv.po_id) if inv.po_id else None
        receipt = session.get(Receipt, inv.receipt_id) if inv.receipt_id else None
        vendor = session.get(Vendor, inv.vendor_id) if inv.vendor_id else None
        result.append({"invoice": inv, "po": po, "receipt": receipt, "vendor": vendor})
    return result


@router.post("/invoices/{invoice_id}/erp-handoff")
def erp_handoff(invoice_id: str, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    inv = session.get(Invoice, invoice_id)
    if not inv or inv.tenant_id != tenant_id:
        raise HTTPException(404, "Invoice not found")
    from app.models.outcome import Approval

    approved = session.exec(
        select(Approval).where(
            Approval.outcome_id == inv.outcome_id,
            Approval.approval_type == "INVOICE_PAYMENT_APPROVAL",
            Approval.decision == "APPROVED",
        )
    ).first()
    result = MockERPConnector().handoff_invoice(
        {
            "invoice_number": inv.invoice_number,
            "match_status": inv.match_status,
            "approved": bool(approved),
        }
    )
    inv.erp_handoff_status = result["status"]
    session.add(inv)
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action="ERP_HANDOFF",
        entity_type="Invoice",
        entity_id=inv.invoice_id,
        after=result,
        correlation_id=inv.outcome_id,
    )
    session.commit()
    return {"invoice": inv, "handoff": result}


@router.get("/failures")
def list_failures(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    jobs = session.exec(
        select(ProcessingJob)
        .where(
            ProcessingJob.tenant_id == tenant_id,
            ProcessingJob.status.in_(["FAILED", "DEAD_LETTER"]),  # type: ignore
        )
        .order_by(ProcessingJob.updated_at.desc())  # type: ignore
    ).all()
    return jobs


@router.post("/failures/{job_id}/reprocess")
def reprocess_failure(job_id: str, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    queue = JobQueueService(session)
    job = queue.reprocess(job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(404, "Job not found")
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=AuditAction.AUTOMATION_RETRIED,
        entity_type="ProcessingJob",
        entity_id=job.job_id,
        after={"status": job.status},
    )
    session.commit()
    return job


@router.get("/config/templates")
def list_templates(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    return session.exec(
        select(OutcomeTemplate).where(OutcomeTemplate.tenant_id == tenant_id)
    ).all()


@router.get("/config/rules")
def list_rules(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    return session.exec(select(BusinessRule).where(BusinessRule.tenant_id == tenant_id)).all()


@router.get("/config/notifications")
def list_notification_templates(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    return session.exec(
        select(NotificationTemplate).where(NotificationTemplate.tenant_id == tenant_id)
    ).all()


@router.get("/vendors")
def list_vendors(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    return session.exec(select(Vendor).where(Vendor.tenant_id == tenant_id)).all()
