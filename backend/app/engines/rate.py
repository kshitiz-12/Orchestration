"""Rate engine — deterministic unit rates from Contract.rate_card / PolicyRule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, select

from app.models.org import Contract, PolicyRule


@dataclass
class RateQuote:
    unit_rate: float
    currency: str
    source: str
    breakdown: dict[str, Any]
    reason: str


class RateEngine:
    def __init__(self, session: Session, tenant_id: str, entity_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.entity_id = entity_id

    def quote(
        self,
        *,
        item_code: str,
        quantity: float = 1.0,
        vendor_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        geography: Optional[str] = None,
    ) -> RateQuote:
        code = (item_code or "").strip().upper()
        if contract_id:
            contract = self.session.get(Contract, contract_id)
            if contract and contract.tenant_id == self.tenant_id:
                card = contract.rate_card or {}
                hit = self._from_card(card, code, geography)
                if hit is not None:
                    return RateQuote(
                        unit_rate=hit,
                        currency=str(card.get("currency") or "INR"),
                        source=f"contract:{contract.contract_id}",
                        breakdown={"item_code": code, "quantity": quantity, "line_total": hit * quantity},
                        reason="Contract rate card",
                    )

        if vendor_id:
            contracts = self.session.exec(
                select(Contract).where(
                    Contract.tenant_id == self.tenant_id,
                    Contract.vendor_id == vendor_id,
                    Contract.status == "ACTIVE",
                )
            ).all()
            for contract in contracts:
                card = contract.rate_card or {}
                hit = self._from_card(card, code, geography)
                if hit is not None:
                    return RateQuote(
                        unit_rate=hit,
                        currency=str(card.get("currency") or "INR"),
                        source=f"contract:{contract.contract_id}",
                        breakdown={"item_code": code, "quantity": quantity, "line_total": hit * quantity},
                        reason="Vendor active contract rate card",
                    )

        rows = self.session.exec(
            select(PolicyRule)
            .where(PolicyRule.tenant_id == self.tenant_id)
            .where(PolicyRule.rule_family == "RATE")
            .where(PolicyRule.is_active == True)  # noqa: E712
            .order_by(PolicyRule.priority)
        ).all()
        for rule in rows:
            decision = rule.decision or {}
            rates = decision.get("rates") or {}
            if code in {str(k).upper() for k in rates.keys()}:
                # case-insensitive key
                raw = next(v for k, v in rates.items() if str(k).upper() == code)
                unit = float(raw)
                return RateQuote(
                    unit_rate=unit,
                    currency=str(decision.get("currency") or "INR"),
                    source=f"policy:{rule.code}",
                    breakdown={"item_code": code, "quantity": quantity, "line_total": unit * quantity},
                    reason=rule.reason_template or f"Rate policy {rule.code}",
                )

        return RateQuote(
            unit_rate=0.0,
            currency="INR",
            source="unavailable",
            breakdown={"item_code": code},
            reason="No rate configured — do not invent",
        )

    @staticmethod
    def _from_card(card: dict[str, Any], code: str, geography: Optional[str]) -> Optional[float]:
        items = card.get("items") or card.get("rates") or card
        if not isinstance(items, dict):
            return None
        if geography:
            geo = (card.get("by_geography") or {}).get(geography) or {}
            if isinstance(geo, dict) and code in {str(k).upper() for k in geo.keys()}:
                return float(next(v for k, v in geo.items() if str(k).upper() == code))
        if code in {str(k).upper() for k in items.keys()}:
            val = next(v for k, v in items.items() if str(k).upper() == code)
            if isinstance(val, dict):
                return float(val.get("unit_rate") or val.get("rate") or 0)
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
        return None
