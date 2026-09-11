from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field

from app.models.org import TimestampMixin, new_id, utcnow


class IntegrationCredential(TimestampMixin, table=True):
    """OAuth tokens for external channels (Gmail, etc). Survives Render redeploys via DB."""

    __tablename__ = "integration_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_provider"),
    )

    credential_id: str = Field(default_factory=lambda: new_id("cred_"), primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.tenant_id", index=True)
    provider: str = Field(index=True)  # GMAIL
    account_email: Optional[str] = None
    token_json: str = Field(sa_column=Column(Text))
    scopes: Optional[str] = None
    status: str = "ACTIVE"
    last_synced_at: Optional[datetime] = None
