"""0002_gmail_credentials

Revision ID: 0002_gmail
Revises: 0001_initial
"""

from alembic import op
from sqlmodel import SQLModel

from app import models  # noqa: F401
from app.models.integrations import IntegrationCredential

revision = "0002_gmail"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    IntegrationCredential.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    IntegrationCredential.__table__.drop(bind=bind, checkfirst=True)
