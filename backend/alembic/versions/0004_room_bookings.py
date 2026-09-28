"""0004_room_bookings

Revision ID: 0004_room_bookings
Revises: 0003_provider
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_room_bookings"
down_revision = "0003_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlmodel import SQLModel

    from app.models.org import RoomBooking

    SQLModel.metadata.create_all(bind=op.get_bind(), tables=[RoomBooking.__table__])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "room_bookings" in inspector.get_table_names():
        op.drop_table("room_bookings")
