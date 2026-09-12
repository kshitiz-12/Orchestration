from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.engine.pipeline import ProcessingPipeline, process_claimed_job
from app.models.intake import RawEmailEvent
from app.schemas.api import EmailIngestRequest
from app.services.intake import IntakeService, JobQueueService

router = APIRouter(prefix="/intake", tags=["intake"])


@router.post("/emails")
def ingest_email(
    payload: EmailIngestRequest,
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
):
    service = IntakeService(session, tenant_id)
    return service.ingest(
        message_id=payload.message_id,
        thread_id=payload.thread_id,
        sender=str(payload.sender),
        recipients=[str(r) for r in payload.recipients],
        cc=[str(c) for c in payload.cc],
        subject=payload.subject,
        body_text=payload.body_text,
        source="API",
        received_at=payload.received_at,
        attachments=payload.attachments,
        headers=payload.headers,
    )


@router.post("/emails/{event_id}/process")
def process_email_now(
    event_id: str,
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
    force: bool = False,
):
    event = session.get(RawEmailEvent, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    pipeline = ProcessingPipeline(session, tenant_id)
    return pipeline.process_event(event_id, force=force)


@router.get("/emails")
def list_emails(session: SessionDep, tenant_id: TenantDep, _user: UserDep, limit: int = 50):
    rows = session.exec(
        select(RawEmailEvent)
        .where(RawEmailEvent.tenant_id == tenant_id)
        .order_by(RawEmailEvent.created_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    ).all()
    return rows


@router.post("/worker/tick")
def worker_tick(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    """Process one queued job — useful for demo without separate worker process."""
    queue = JobQueueService(session)
    job = queue.claim_next(["PROCESS_EMAIL"])
    if not job:
        return {"processed": False}
    process_claimed_job(session, job, tenant_id)
    return {"processed": True, "job_id": job.job_id, "status": job.status}
