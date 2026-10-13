"""Continuous operational memory — who did what, spend, stock, assets, repairs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field

from app.models.org import TimestampMixin, new_id, utcnow


class OpsLedgerEvent(TimestampMixin, table=True):
    __tablename__ = "ops_ledger_events"

    event_id: str = Field(default_factory=lambda: new_id("led_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    occurred_at: datetime = Field(default_factory=utcnow, index=True)

    actor_email: Optional[str] = Field(default=None, index=True)
    actor_role: str = "system"  # employee | team | admin | vendor | system

    department_code: Optional[str] = Field(default=None, index=True)
    location_id: Optional[str] = Field(default=None, index=True)
    category: Optional[str] = Field(default=None, index=True)

    outcome_id: Optional[str] = Field(default=None, index=True)
    case_reference: Optional[str] = Field(default=None, index=True)

    event_type: str = Field(index=True)
    amount: Optional[float] = None
    currency: str = "INR"
    quantity: Optional[float] = None
    unit: Optional[str] = None
    sku_code: Optional[str] = None
    asset_tag: Optional[str] = None

    summary: str = ""
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
