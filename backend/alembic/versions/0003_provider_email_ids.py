"""0003_provider_email_ids

Revision ID: 0003_provider
Revises: 0002_gmail
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_provider"
down_revision = "0002_gmail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("raw_email_events")}

    if "provider" not in cols:
        op.add_column("raw_email_events", sa.Column("provider", sa.String(), nullable=True))
    if "provider_message_id" not in cols:
        op.add_column("raw_email_events", sa.Column("provider_message_id", sa.String(), nullable=True))
    if "provider_conversation_id" not in cols:
        op.add_column(
            "raw_email_events",
            sa.Column("provider_conversation_id", sa.String(), nullable=True),
        )

    # Backfill from legacy Gmail columns
    op.execute(
        """
        UPDATE raw_email_events
        SET provider = COALESCE(provider, source, 'GMAIL'),
            provider_message_id = COALESCE(provider_message_id, gmail_message_id),
            provider_conversation_id = COALESCE(provider_conversation_id, gmail_thread_id)
        """
    )

    # communications.provider_message_id
    comm_cols = {c["name"] for c in inspector.get_columns("communications")}
    if "provider_message_id" not in comm_cols:
        op.add_column("communications", sa.Column("provider_message_id", sa.String(), nullable=True))
        op.execute(
            "UPDATE communications SET provider_message_id = gmail_message_id WHERE provider_message_id IS NULL"
        )


def downgrade() -> None:
    op.drop_column("communications", "provider_message_id")
    op.drop_column("raw_email_events", "provider_conversation_id")
    op.drop_column("raw_email_events", "provider_message_id")
    op.drop_column("raw_email_events", "provider")
