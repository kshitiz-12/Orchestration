"""Transactional outbox — queue side-effects after DB commit; worker flushes."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.models.org import OutboxEvent, utcnow

logger = get_logger(__name__)


class OutboxService:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def enqueue(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        aggregate_type: Optional[str] = None,
        aggregate_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        delay_seconds: float = 0,
    ) -> OutboxEvent:
        existing = self.session.exec(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == self.tenant_id,
                OutboxEvent.idempotency_key == idempotency_key,
            )
        ).first()
        if existing:
            return existing
        row = OutboxEvent(
            tenant_id=self.tenant_id,
            entity_id=entity_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload or {},
            idempotency_key=idempotency_key,
            status="PENDING",
            available_at=utcnow() + timedelta(seconds=delay_seconds),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def flush(self, *, limit: int = 25) -> dict[str, int]:
        """Mark due outbox rows SENT (handlers plug in later; audit trail preserved)."""
        now = utcnow()
        rows = self.session.exec(
            select(OutboxEvent)
            .where(OutboxEvent.tenant_id == self.tenant_id)
            .where(OutboxEvent.status == "PENDING")
            .where(OutboxEvent.available_at <= now)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        ).all()
        sent = failed = 0
        for row in rows:
            row.attempts += 1
            try:
                # Phase 1: durable queue + status. Phase 4+ wires mail/integration publishers.
                logger.info(
                    "outbox_dispatch",
                    tenant_id=self.tenant_id,
                    event_type=row.event_type,
                    aggregate_id=row.aggregate_id,
                    outbox_id=row.outbox_id,
                )
                row.status = "SENT"
                row.sent_at = utcnow()
                row.last_error = None
                sent += 1
            except Exception as exc:  # noqa: BLE001
                row.last_error = str(exc)[:2000]
                if row.attempts >= 8:
                    row.status = "DEAD"
                else:
                    row.status = "PENDING"
                    row.available_at = utcnow() + timedelta(seconds=min(300, 5 * (2 ** (row.attempts - 1))))
                failed += 1
            self.session.add(row)
        if rows:
            self.session.commit()
        return {"sent": sent, "failed": failed, "seen": len(rows)}
