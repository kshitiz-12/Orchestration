"""Budget engine — reserve / commit / accrue / actual / transfer (not ERP books)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.facilities import BudgetTransfer
from app.models.org import Budget, utcnow


@dataclass
class BudgetCheck:
    ok: bool
    available: float
    budget_id: Optional[str] = None
    reason: str = ""


class BudgetEngine:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def _find(
        self,
        *,
        period: str,
        category: str = "OPEX",
        cost_centre: Optional[str] = None,
    ) -> Optional[Budget]:
        stmt = (
            select(Budget)
            .where(Budget.tenant_id == self.tenant_id)
            .where(Budget.period == period)
            .where(Budget.category == category)
            .where(Budget.status == "ACTIVE")
        )
        if self.entity_id:
            stmt = stmt.where(Budget.entity_id == self.entity_id)
        if cost_centre:
            stmt = stmt.where(Budget.cost_centre == cost_centre)
        return self.session.exec(stmt).first()

    def available(self, budget: Budget) -> float:
        """Available = Revised − commitments − actuals − accruals − reservations (facilities.docx §7.3)."""
        ceiling = budget.revised_amount if budget.revised_amount else budget.original_amount
        used = (
            (budget.reserved_amount or 0)
            + (budget.committed_amount or 0)
            + (budget.actual_amount or 0)
            + (getattr(budget, "accrued_amount", 0) or 0)
        )
        return float(ceiling) - float(used)

    def forecast_at_completion(self, budget: Budget, remaining_forecast: float = 0.0, risks: float = 0.0) -> float:
        return (
            float(budget.actual_amount or 0)
            + float(budget.committed_amount or 0)
            + float(getattr(budget, "accrued_amount", 0) or 0)
            + float(remaining_forecast)
            + float(risks)
        )

    def check(
        self,
        *,
        amount: float,
        period: str,
        category: str = "OPEX",
        cost_centre: Optional[str] = None,
    ) -> BudgetCheck:
        row = self._find(period=period, category=category, cost_centre=cost_centre)
        if not row:
            return BudgetCheck(ok=True, available=0.0, reason="No budget row configured — pass-through")
        avail = self.available(row)
        if amount > avail + 1e-6:
            return BudgetCheck(
                ok=False,
                available=avail,
                budget_id=row.budget_id,
                reason=f"Insufficient budget: need {amount}, available {avail}",
            )
        return BudgetCheck(ok=True, available=avail, budget_id=row.budget_id, reason="Within budget")

    def reserve(
        self,
        *,
        amount: float,
        period: str,
        category: str = "OPEX",
        cost_centre: Optional[str] = None,
        allow_missing: bool = True,
    ) -> BudgetCheck:
        check = self.check(amount=amount, period=period, category=category, cost_centre=cost_centre)
        if not check.ok:
            raise HTTPException(status_code=409, detail=check.reason)
        if not check.budget_id:
            if allow_missing:
                return check
            raise HTTPException(status_code=404, detail="Budget not found")
        row = self.session.get(Budget, check.budget_id)
        assert row is not None
        row.reserved_amount = float(row.reserved_amount or 0) + float(amount)
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        return BudgetCheck(ok=True, available=self.available(row), budget_id=row.budget_id, reason="Reserved")

    def release_reservation(
        self,
        *,
        amount: float,
        budget_id: str,
    ) -> BudgetCheck:
        row = self.session.get(Budget, budget_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Budget not found")
        row.reserved_amount = max(0.0, float(row.reserved_amount or 0) - float(amount))
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        return BudgetCheck(ok=True, available=self.available(row), budget_id=row.budget_id, reason="Released")

    def commit(
        self,
        *,
        amount: float,
        budget_id: Optional[str] = None,
        period: Optional[str] = None,
        category: str = "OPEX",
        cost_centre: Optional[str] = None,
        from_reservation: bool = True,
    ) -> BudgetCheck:
        """Create commitment when PR/PO/contract/WO approved; optionally convert reservation."""
        row = self.session.get(Budget, budget_id) if budget_id else None
        if row is None and period:
            row = self._find(period=period, category=category, cost_centre=cost_centre)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Budget not found")
        if self.available(row) + (float(row.reserved_amount or 0) if from_reservation else 0) + 1e-6 < float(amount):
            # If converting reservation, reserved already counts against available — allow using it
            avail_with_res = self.available(row) + (float(row.reserved_amount or 0) if from_reservation else 0)
            if avail_with_res + 1e-6 < float(amount):
                raise HTTPException(status_code=409, detail=f"Insufficient budget to commit {amount}")
        if from_reservation:
            use = min(float(row.reserved_amount or 0), float(amount))
            row.reserved_amount = max(0.0, float(row.reserved_amount or 0) - use)
        row.committed_amount = float(row.committed_amount or 0) + float(amount)
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        return BudgetCheck(ok=True, available=self.available(row), budget_id=row.budget_id, reason="Committed")

    def relieve_commitment(self, *, amount: float, budget_id: str) -> BudgetCheck:
        row = self.session.get(Budget, budget_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Budget not found")
        row.committed_amount = max(0.0, float(row.committed_amount or 0) - float(amount))
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        return BudgetCheck(ok=True, available=self.available(row), budget_id=row.budget_id, reason="Commitment relieved")

    def post_actual(self, *, amount: float, budget_id: str, from_commitment: bool = True) -> BudgetCheck:
        row = self.session.get(Budget, budget_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Budget not found")
        if from_commitment:
            use = min(float(row.committed_amount or 0), float(amount))
            row.committed_amount = max(0.0, float(row.committed_amount or 0) - use)
        # Clear matching accrual if present
        accrued = float(getattr(row, "accrued_amount", 0) or 0)
        if accrued > 0:
            clear = min(accrued, float(amount))
            row.accrued_amount = max(0.0, accrued - clear)
        row.actual_amount = float(row.actual_amount or 0) + float(amount)
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        return BudgetCheck(ok=True, available=self.available(row), budget_id=row.budget_id, reason="Actual posted")

    def accrue(self, *, amount: float, budget_id: str) -> BudgetCheck:
        """Recognise consumed but unbilled services."""
        row = self.session.get(Budget, budget_id)
        if not row or row.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Budget not found")
        if self.available(row) + 1e-6 < float(amount):
            raise HTTPException(status_code=409, detail=f"Insufficient budget to accrue {amount}")
        row.accrued_amount = float(getattr(row, "accrued_amount", 0) or 0) + float(amount)
        row.updated_at = utcnow()
        self.session.add(row)
        self.session.commit()
        return BudgetCheck(ok=True, available=self.available(row), budget_id=row.budget_id, reason="Accrued")

    def transfer(
        self,
        *,
        source_budget_id: str,
        dest_budget_id: str,
        amount: float,
        justification: str,
        approved_by: Optional[str] = None,
    ) -> BudgetTransfer:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be positive")
        if not (justification or "").strip():
            raise HTTPException(status_code=400, detail="justification required")
        src = self.session.get(Budget, source_budget_id)
        dst = self.session.get(Budget, dest_budget_id)
        if not src or src.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Source budget not found")
        if not dst or dst.tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="Destination budget not found")
        if self.available(src) + 1e-6 < float(amount):
            raise HTTPException(status_code=409, detail="Source budget insufficient for transfer")
        # Reduce revised (or original) on source; increase revised on dest
        src_ceiling = src.revised_amount if src.revised_amount else src.original_amount
        src.revised_amount = float(src_ceiling) - float(amount)
        dst_ceiling = dst.revised_amount if dst.revised_amount else dst.original_amount
        dst.revised_amount = float(dst_ceiling) + float(amount)
        src.updated_at = utcnow()
        dst.updated_at = utcnow()
        xfer = BudgetTransfer(
            tenant_id=self.tenant_id,
            source_budget_id=source_budget_id,
            dest_budget_id=dest_budget_id,
            amount=float(amount),
            justification=justification.strip(),
            approved_by=approved_by,
            status="APPROVED",
        )
        self.session.add(src)
        self.session.add(dst)
        self.session.add(xfer)
        self.session.commit()
        self.session.refresh(xfer)
        return xfer
