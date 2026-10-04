"""0005_schema_sync

Catches the database up with everything added since 0004 (departments, knowledge, site services, cost centres,
service tickets, visitor passes, learning records, handover info, branches/places ...), whatever state it is in.
Additive only. New schema changes from here on get their own migration.

Revision ID: 0005_schema_sync
Revises: 0004_room_bookings
"""

from alembic import op

revision = "0005_schema_sync"
down_revision = "0004_room_bookings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.schema_sync import apply

    apply(op.get_bind())


def downgrade() -> None:
    # Additive catch-up: nothing safe to undo automatically.
    pass
