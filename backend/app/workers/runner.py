"""Durable worker: process queued jobs per tenant. CloudMailin is push-based (no poll)."""

from __future__ import annotations

import time

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine, init_db
from app.core.logging import get_logger, setup_logging
from app.engine.pipeline import process_claimed_job
from app.models.org import Tenant
from app.services.email_poll import poll_and_process
from app.services.intake import JobQueueService
from app.services.outbox import OutboxService

logger = get_logger(__name__)


def _active_tenants(session: Session) -> list[Tenant]:
    rows = session.exec(select(Tenant).where(Tenant.status == "ACTIVE")).all()
    return list(rows or [])


def run_forever() -> None:
    settings = get_settings()
    setup_logging(settings.debug)
    init_db()
    engine = get_engine()
    last_email_poll: dict[str, float] = {}
    provider_name = (settings.email_provider or "cloudmailin").strip().lower()
    poll_enabled = provider_name not in {"cloudmailin", "cloud_mailin", "cmi"}

    while True:
        with Session(engine) as session:
            tenants = _active_tenants(session)
            if not tenants:
                logger.warning("no_tenant_seeded")
                time.sleep(settings.worker_poll_interval_seconds)
                continue

            queue = JobQueueService(session)
            claimed = 0
            # Claim jobs using each job's own tenant_id — never pin to "first tenant".
            while claimed < settings.worker_max_concurrent_ai_jobs:
                job = queue.claim_next(["PROCESS_EMAIL"])
                if not job:
                    break
                process_claimed_job(session, job, job.tenant_id)
                claimed += 1
            if claimed:
                logger.info("worker_tick", claimed=claimed, tenants=len(tenants))

            for tenant in tenants:
                tid = tenant.tenant_id
                try:
                    from app.services.hold_sweeper import run_all_sweeps

                    sweeps = run_all_sweeps(session, tid)
                    desk = sweeps.get("desk") or {}
                    sla = sweeps.get("sla") or {}
                    if any(desk.get(k) for k in ("reminded", "escalated", "nudged", "auto_closed", "approval_reminders")):
                        logger.info("desk_sweep", tenant_id=tid, **{k: v for k, v in desk.items() if v})
                    if sla.get("overdue_tasks") or sla.get("escalated_tasks"):
                        logger.info("sla_tick", tenant_id=tid, **sla)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    logger.warning("worker_sweeps_failed", tenant_id=tid, error=str(exc))

                try:
                    flushed = OutboxService(session, tid).flush(limit=25)
                    if flushed.get("sent") or flushed.get("failed"):
                        logger.info("outbox_flush", tenant_id=tid, **flushed)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    logger.warning("outbox_flush_failed", tenant_id=tid, error=str(exc))

                if poll_enabled:
                    now = time.time()
                    interval = max(15, int(settings.email_poll_interval_seconds or 60))
                    last = last_email_poll.get(tid, 0.0)
                    if now - last >= interval:
                        try:
                            result = poll_and_process(session, tid, max_results=10, process=True)
                            logger.info(
                                "email_poll_tick",
                                tenant_id=tid,
                                provider=result.get("provider"),
                                ok=result.get("ok"),
                                fetched=result.get("fetched"),
                                error=result.get("error"),
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("email_poll_failed", tenant_id=tid, error=str(exc))
                        last_email_poll[tid] = now

        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
