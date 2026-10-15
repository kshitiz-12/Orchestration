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
        """Dispatch due outbox rows; failures retry then DEAD (DLQ)."""
        now = utcnow()
        rows = self.session.exec(
            select(OutboxEvent)
            .where(OutboxEvent.tenant_id == self.tenant_id)
            .where(OutboxEvent.status == "PENDING")
            .where(OutboxEvent.available_at <= now)
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        ).all()
        sent = failed = dead = 0
        for row in rows:
            row.attempts += 1
            try:
                self._dispatch(row)
                row.status = "SENT"
                row.sent_at = utcnow()
                row.last_error = None
                sent += 1
            except Exception as exc:  # noqa: BLE001
                row.last_error = str(exc)[:2000]
                if row.attempts >= 8:
                    row.status = "DEAD"
                    dead += 1
                    logger.error(
                        "outbox_dead_letter",
                        tenant_id=self.tenant_id,
                        outbox_id=row.outbox_id,
                        event_type=row.event_type,
                        error=str(exc)[:300],
                    )
                else:
                    row.status = "PENDING"
                    row.available_at = utcnow() + timedelta(seconds=min(300, 5 * (2 ** (row.attempts - 1))))
                    failed += 1
            self.session.add(row)
        if rows:
            self.session.commit()
        return {"sent": sent, "failed": failed, "dead": dead, "seen": len(rows)}

    def _dispatch(self, row: OutboxEvent) -> None:
        """Route by event_type; ERP posts go through connector with idempotency."""
        et = (row.event_type or "").upper()
        logger.info(
            "outbox_dispatch",
            tenant_id=self.tenant_id,
            event_type=row.event_type,
            aggregate_id=row.aggregate_id,
            outbox_id=row.outbox_id,
        )
        if et.startswith("ERP.") or et in {"INVOICE.POST", "COST.POST"}:
            from app.connectors.erp_http import get_erp_connector

            connector = get_erp_connector(self.session, self.tenant_id)
            payload = dict(row.payload or {})
            payload["idempotency_key"] = row.idempotency_key
            # Durable queue acknowledgment — connector posts when invoice payload present
            if payload.get("invoice") and hasattr(connector, "post_invoice"):
                connector.post_invoice(payload["invoice"], idempotency_key=row.idempotency_key)

    def dead_letters(self, *, limit: int = 50) -> list[OutboxEvent]:
        rows = list(
            self.session.exec(
                select(OutboxEvent).where(
                    OutboxEvent.tenant_id == self.tenant_id,
                    OutboxEvent.status == "DEAD",
                )
            ).all()
        )
        rows.sort(key=lambda r: r.updated_at or r.created_at or utcnow(), reverse=True)
        return rows[:limit]

    def requeue_dead(self, outbox_id: str) -> OutboxEvent:
        row = self.session.get(OutboxEvent, outbox_id)
        if not row or row.tenant_id != self.tenant_id:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Outbox event not found")
        if row.status != "DEAD":
            from fastapi import HTTPException

            raise HTTPException(status_code=409, detail="Only DEAD events can be requeued")
        row.status = "PENDING"
        row.attempts = 0
        row.last_error = None
        row.available_at = utcnow()
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def reconcile_erp_handoffs(self) -> dict[str, int]:
        """Scan ErpHandoff NOT_STARTED/QUEUED and enqueue idempotent posts."""
        from app.models.finance import ErpHandoff

        all_h = self.session.exec(select(ErpHandoff).where(ErpHandoff.tenant_id == self.tenant_id)).all()
        rows = [h for h in all_h if h.status in {"NOT_STARTED", "QUEUED", "FAILED"}]
        queued = 0
        for h in rows:
            self.enqueue(
                event_type="ERP.RECONCILE",
                payload={"handoff_id": h.handoff_id, "invoice_id": h.invoice_id, "cost_id": h.cost_id},
                idempotency_key=f"erp-recon-{h.handoff_id}-{h.attempts if hasattr(h, 'attempts') else 0}",
                aggregate_type="ErpHandoff",
                aggregate_id=h.handoff_id,
            )
            if h.status == "NOT_STARTED":
                h.status = "QUEUED"
                self.session.add(h)
                queued += 1
        if queued:
            self.session.commit()
        return {"queued": queued, "seen": len(rows)}
