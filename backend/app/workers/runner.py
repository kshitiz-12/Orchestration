"""Durable DB-backed worker loop — survives process restart via job leasing."""

from __future__ import annotations

import time

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.database import get_engine, init_db
from app.core.logging import get_logger, setup_logging
from app.engine.pipeline import process_claimed_job
from app.models.org import Tenant
from app.services.intake import JobQueueService

logger = get_logger(__name__)


def run_forever() -> None:
    settings = get_settings()
    setup_logging(settings.debug)
    init_db()
    engine = get_engine()
    while True:
        with Session(engine) as session:
            tenant = session.exec(select(Tenant)).first()
            if not tenant:
                logger.warning("no_tenant_seeded")
                time.sleep(settings.worker_poll_interval_seconds)
                continue
            # Simple concurrency: claim up to N jobs sequentially per tick
            claimed = 0
            queue = JobQueueService(session)
            while claimed < settings.worker_max_concurrent_ai_jobs:
                job = queue.claim_next(["PROCESS_EMAIL"])
                if not job:
                    break
                process_claimed_job(session, job, tenant.tenant_id)
                claimed += 1
            if claimed:
                logger.info("worker_tick", claimed=claimed)
        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
