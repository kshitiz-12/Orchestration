"""initial_schema — create all Outcome Orchestration tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-08
"""

from __future__ import annotations

from alembic import op
from sqlmodel import SQLModel

# Import models so metadata is populated
from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
