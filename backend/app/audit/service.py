from typing import Any, Optional

from sqlmodel import Session

from app.core.enums import AuditAction
from app.core.logging import get_logger
from app.models.outcome import AuditLog

logger = get_logger(__name__)


class AuditService:
    """Append-only audit logging. Never mutate prior rows."""

    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: AuditAction | str,
        entity_type: str,
        entity_id: str,
        before: Optional[dict[str, Any]] = None,
        after: Optional[dict[str, Any]] = None,
        source: str = "SYSTEM",
        correlation_id: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            tenant_id=tenant_id,
            actor=actor,
            action=action.value if isinstance(action, AuditAction) else action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            source=source,
            correlation_id=correlation_id,
        )
        self.session.add(entry)
        self.session.flush()
        logger.info(
            "audit",
            action=entry.action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
        )
        return entry
