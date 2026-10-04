"""0006_lock_down_api_access

Turn on row-level security for every table we own in the public schema, so Supabase's auto-generated REST API
(reachable with the project's anon key) can't read or write them. The backend connects as the table owner and is not
affected. Tenant isolation policies will build on this. No-op on SQLite.

Revision ID: 0006_lock_down_api_access
Revises: 0005_schema_sync
"""

from alembic import op

revision = "0006_lock_down_api_access"
down_revision = "0005_schema_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.schema_sync import lock_down

    lock_down(op.get_bind())


def downgrade() -> None:
    # Re-opening tables to the public API is never something to do automatically.
    pass
