"""Durable worker: process queued jobs. CloudMailin is push-based (no poll)."""

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

logger = get_logger(__name__)


def run_forever() -> None:
    settings = get_settings()
    setup_logging(settings.debug)
    init_db()
    engine = get_engine()
    last_email_poll = 0.0
    provider_name = (settings.email_provider or "cloudmailin").strip().lower()
    poll_enabled = provider_name not in {"cloudmailin", "cloud_mailin", "cmi"}

    while True:
        with Session(engine) as session:
            tenant = session.exec(select(Tenant)).first()
            if not tenant:
                logger.warning("no_tenant_seeded")
                time.sleep(settings.worker_poll_interval_seconds)
                continue

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

            # Outlook/Gmail poll only — CloudMailin pushes via webhook
            if poll_enabled:
                now = time.time()
                interval = max(15, int(settings.email_poll_interval_seconds or 60))
                if now - last_email_poll >= interval:
                    try:
                        result = poll_and_process(session, tenant.tenant_id, max_results=10, process=True)
                        logger.info(
                            "email_poll_tick",
                            provider=result.get("provider"),
                            ok=result.get("ok"),
                            fetched=result.get("fetched"),
                            error=result.get("error"),
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("email_poll_failed", error=str(exc))
                    last_email_poll = now

        time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    run_forever()
