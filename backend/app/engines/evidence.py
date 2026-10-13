"""Evidence / closure engine — block verified close without required proof."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import Session, select

from app.models.outcome import Evidence, Outcome, Task


@dataclass
class EvidenceGate:
    can_verify_close: bool
    missing: list[str] = field(default_factory=list)
    reason: str = ""


class EvidenceEngine:
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    def gate_for_outcome(self, outcome_id: str) -> EvidenceGate:
        outcome = self.session.get(Outcome, outcome_id)
        if not outcome or outcome.tenant_id != self.tenant_id:
            return EvidenceGate(can_verify_close=False, missing=["outcome"], reason="Outcome not found")

        tasks = self.session.exec(
            select(Task).where(Task.outcome_id == outcome_id, Task.tenant_id == self.tenant_id)
        ).all()
        missing: list[str] = []
        for task in tasks:
            if not task.evidence_required:
                continue
            if (task.status or "").upper() in {"CANCELLED", "WAIVED"}:
                continue
            ev = self.session.exec(
                select(Evidence).where(
                    Evidence.tenant_id == self.tenant_id,
                    Evidence.task_id == task.task_id,
                )
            ).first()
            if not ev:
                missing.append(f"task:{task.code or task.task_id}")
                continue
            if (ev.status or "").upper() not in {"ACCEPTED", "VERIFIED", "APPROVED"}:
                # Submitted but not accepted still blocks verified close
                if (ev.status or "").upper() in {"SUBMITTED", "PENDING"}:
                    missing.append(f"task:{task.code or task.task_id}:pending_verification")
                else:
                    missing.append(f"task:{task.code or task.task_id}:evidence_status={ev.status}")

        if missing:
            return EvidenceGate(
                can_verify_close=False,
                missing=missing,
                reason="Mandatory evidence missing or unverified — cannot mark verified closure",
            )
        return EvidenceGate(can_verify_close=True, reason="Evidence requirements satisfied")
