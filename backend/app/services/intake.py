from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.audit.service import AuditService
from app.core.enums import AuditAction, JobStatus, JobType, ProcessingStage
from app.core.logging import get_logger
from app.models.intake import DownstreamAction, ProcessingJob, RawEmailEvent
from app.models.org import new_id, utcnow
from app.services.email_utils import (
    compute_idempotency_key,
    safety_scan_email,
    strip_for_ai,
    validate_attachment,
)

logger = get_logger(__name__)


class IntakeService:
    """Receive → store → dedupe → queue. Never lose the original email."""

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.audit = AuditService(session)

    def ingest(
        self,
        *,
        message_id: str,
        thread_id: str,
        sender: str,
        recipients: list[str],
        subject: str,
        body_text: str,
        source: str = "OUTLOOK",
        cc: Optional[list[str]] = None,
        body_html: Optional[str] = None,
        received_at: Optional[datetime] = None,
        attachments: Optional[list[dict[str, Any]]] = None,
        headers: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        idem = compute_idempotency_key(message_id, source)
        existing = self.session.exec(
            select(RawEmailEvent).where(RawEmailEvent.idempotency_key == idem)
        ).first()
        if existing:
            self.audit.record(
                tenant_id=self.tenant_id,
                actor="system",
                action=AuditAction.EMAIL_DEDUPLICATED,
                entity_type="RawEmailEvent",
                entity_id=existing.event_id,
                after={"message_id": message_id},
                source=source,
                correlation_id=existing.processing_id,
            )
            self.session.commit()
            return {
                "status": "deduplicated",
                "event_id": existing.event_id,
                "processing_id": existing.processing_id,
            }

        attachment_meta = []
        for att in attachments or []:
            flags = validate_attachment(
                att.get("filename", "unknown"),
                int(att.get("size", 0)),
                att.get("content_bytes"),
            )
            safe = {k: v for k, v in att.items() if k != "content_bytes"}
            safe["validation"] = flags
            attachment_meta.append(safe)

        safety = safety_scan_email(subject, body_text)
        event = RawEmailEvent(
            tenant_id=self.tenant_id,
            idempotency_key=idem,
            provider=source,
            provider_message_id=message_id,
            provider_conversation_id=thread_id,
            gmail_message_id=message_id,
            gmail_thread_id=thread_id,
            source=source,
            sender=sender,
            recipients=recipients or [],
            cc=cc or [],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            body_for_ai=strip_for_ai(body_text),
            received_at=received_at or utcnow(),
            attachments=attachment_meta,
            headers=headers or {},
            safety_flags=safety,
            processing_stage=ProcessingStage.QUEUED.value
            if not safety.get("quarantine")
            else ProcessingStage.FAILED.value,
        )
        self.session.add(event)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.exec(
                select(RawEmailEvent).where(RawEmailEvent.idempotency_key == idem)
            ).first()
            return {
                "status": "deduplicated",
                "event_id": existing.event_id if existing else None,
                "processing_id": existing.processing_id if existing else None,
            }

        self.audit.record(
            tenant_id=self.tenant_id,
            actor=f"email:{sender}",
            action=AuditAction.EMAIL_RECEIVED,
            entity_type="RawEmailEvent",
            entity_id=event.event_id,
            after={
                "message_id": message_id,
                "thread_id": thread_id,
                "subject": subject,
                "processing_id": event.processing_id,
            },
            source=source,
            correlation_id=event.processing_id,
        )

        if safety.get("quarantine"):
            event.processing_stage = ProcessingStage.FAILED.value
            self.session.add(
                ProcessingJob(
                    tenant_id=self.tenant_id,
                    job_type=JobType.PROCESS_EMAIL.value,
                    status=JobStatus.DEAD_LETTER.value,
                    event_id=event.event_id,
                    payload={"reason": "quarantined_safety"},
                    idempotency_key=f"process:{idem}",
                    stage=ProcessingStage.FAILED.value,
                    last_error="Quarantined due to safety flags",
                )
            )
            self.session.commit()
            return {
                "status": "quarantined",
                "event_id": event.event_id,
                "processing_id": event.processing_id,
            }

        job = ProcessingJob(
            tenant_id=self.tenant_id,
            job_type=JobType.PROCESS_EMAIL.value,
            status=JobStatus.PENDING.value,
            event_id=event.event_id,
            payload={"event_id": event.event_id},
            idempotency_key=f"process:{idem}",
            stage=ProcessingStage.QUEUED.value,
        )
        self.session.add(job)
        self.session.commit()
        logger.info("email_ingested", event_id=event.event_id, message_id=message_id)
        return {
            "status": "queued",
            "event_id": event.event_id,
            "processing_id": event.processing_id,
            "job_id": job.job_id,
        }


class JobQueueService:
    """Database-backed durable queue with leasing and retries."""

    def __init__(self, session: Session, worker_id: Optional[str] = None):
        self.session = session
        self.worker_id = worker_id or new_id("wkr_")

    def enqueue(
        self,
        *,
        tenant_id: str,
        job_type: str,
        idempotency_key: str,
        payload: dict,
        event_id: Optional[str] = None,
        delay_seconds: float = 0,
    ) -> ProcessingJob:
        existing = self.session.exec(
            select(ProcessingJob).where(ProcessingJob.idempotency_key == idempotency_key)
        ).first()
        if existing and existing.status in {
            JobStatus.PENDING.value,
            JobStatus.RUNNING.value,
            JobStatus.SUCCEEDED.value,
        }:
            return existing
        job = ProcessingJob(
            tenant_id=tenant_id,
            job_type=job_type,
            event_id=event_id,
            payload=payload,
            idempotency_key=idempotency_key,
            available_at=utcnow() + timedelta(seconds=delay_seconds),
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def claim_next(self, job_types: Optional[list[str]] = None) -> Optional[ProcessingJob]:
        now = utcnow()
        stmt = (
            select(ProcessingJob)
            .where(ProcessingJob.status == JobStatus.PENDING.value)
            .where(ProcessingJob.available_at <= now)
            .order_by(ProcessingJob.created_at)
        )
        if job_types:
            stmt = stmt.where(ProcessingJob.job_type.in_(job_types))
        job = self.session.exec(stmt).first()
        if not job:
            return None
        job.status = JobStatus.RUNNING.value
        job.locked_at = now
        job.locked_by = self.worker_id
        job.attempts += 1
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def succeed(self, job: ProcessingJob) -> None:
        job.status = JobStatus.SUCCEEDED.value
        job.completed_at = utcnow()
        job.last_error = None
        self.session.add(job)
        self.session.commit()

    def fail(self, job: ProcessingJob, error: str, max_attempts: int = 5, base_delay: float = 5.0) -> None:
        job.last_error = error[:4000]
        if job.attempts >= max_attempts:
            job.status = JobStatus.DEAD_LETTER.value
            job.stage = ProcessingStage.FAILED.value
        else:
            job.status = JobStatus.PENDING.value
            delay = base_delay * (2 ** (job.attempts - 1))
            job.available_at = utcnow() + timedelta(seconds=delay)
            job.locked_at = None
            job.locked_by = None
        self.session.add(job)
        self.session.commit()

    def reprocess(self, job_id: str) -> Optional[ProcessingJob]:
        job = self.session.get(ProcessingJob, job_id)
        if not job:
            return None
        job.status = JobStatus.PENDING.value
        job.available_at = utcnow()
        job.locked_at = None
        job.locked_by = None
        job.last_error = None
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job


class IdempotentActionService:
    def __init__(self, session: Session):
        self.session = session

    def run_once(
        self,
        *,
        tenant_id: str,
        action_type: str,
        idempotency_key: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        execute_fn=None,
    ) -> dict:
        existing = self.session.exec(
            select(DownstreamAction).where(DownstreamAction.idempotency_key == idempotency_key)
        ).first()
        if existing:
            return {"status": "already_done", "action_id": existing.action_id, "result": existing.result}
        result = execute_fn() if execute_fn else {}
        action = DownstreamAction(
            tenant_id=tenant_id,
            action_type=action_type,
            idempotency_key=idempotency_key,
            entity_type=entity_type,
            entity_id=entity_id,
            result=result or {},
        )
        self.session.add(action)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.exec(
                select(DownstreamAction).where(DownstreamAction.idempotency_key == idempotency_key)
            ).first()
            return {
                "status": "already_done",
                "action_id": existing.action_id if existing else None,
                "result": existing.result if existing else {},
            }
        return {"status": "executed", "action_id": action.action_id, "result": result or {}}
