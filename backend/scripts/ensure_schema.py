"""One-off: ensure provider_* columns exist on current DATABASE_URL."""

from app.core.config import get_settings
from app.core.database import check_database, ensure_schema_compat, get_engine
from sqlalchemy import text

if __name__ == "__main__":
    get_settings.cache_clear()
    check_database()
    ensure_schema_compat()
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'raw_email_events' "
                "AND column_name LIKE '%provider%' OR "
                "(table_name = 'raw_email_events' AND column_name LIKE 'gmail%') "
                "ORDER BY column_name"
            )
        ).fetchall()
        print("provider_related_cols:", [r[0] for r in rows])
    print("done")
