from collections.abc import Generator
from pathlib import Path
import traceback

from sqlalchemy import event, text
from sqlalchemy.pool import NullPool, QueuePool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings
from app.core.logging import get_logger

_engine = None
logger = get_logger(__name__)


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict = {}
        if settings.is_sqlite:
            connect_args["check_same_thread"] = False

        kwargs: dict = {
            "echo": bool(settings.debug) and not settings.is_production,
            "connect_args": connect_args,
            "pool_pre_ping": True,
        }

        if settings.is_sqlite:
            pass
        elif settings.uses_transaction_pooler:
            # PgBouncer transaction mode — avoid sticky/server-side session state
            kwargs["poolclass"] = NullPool
            logger.info("db_pool_mode", mode="nullpool_transaction_pooler")
        else:
            # Session pooler / direct Postgres — bounded pool for concurrent API workers
            kwargs["poolclass"] = QueuePool
            kwargs["pool_size"] = settings.db_pool_size
            kwargs["max_overflow"] = settings.db_max_overflow
            kwargs["pool_timeout"] = settings.db_pool_timeout
            kwargs["pool_recycle"] = 1800
            logger.info(
                "db_pool_mode",
                mode="queuepool",
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
            )

        _engine = create_engine(settings.database_url, **kwargs)
        if settings.is_sqlite:

            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _engine


def check_database() -> None:
    """Fail fast with a clear message if Postgres/Supabase is unreachable."""
    settings = get_settings()
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        hint = ""
        if "supabase" in settings.database_url.lower() or "could not connect" in str(exc).lower():
            hint = (
                " For Supabase from Render, use the Session pooler URI "
                "(host like aws-0-....pooler.supabase.com, port 5432), "
                "not the direct db.*.supabase.co host (often IPv6-only)."
            )
        raise RuntimeError(f"Database connection failed: {exc}.{hint}") from exc


BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def run_migrations() -> None:
    """Apply Alembic migrations to head (production schema path)."""
    from alembic import command

    command.upgrade(alembic_config(), "head")
    logger.info("migrations_applied", revision="head")


def ensure_schema_compat() -> None:
    """Add any tables, columns and indexes the models have and the database lacks (additive, idempotent).

    create_all never alters existing tables; without this a database created by older code breaks on new fields.
    """
    from app.core.schema_sync import apply

    with get_engine().begin() as conn:
        changes = apply(conn)
    logger.info("schema_compat_ensured", changes=len(changes.describe()))


def init_db() -> None:
    from app import models  # noqa: F401

    settings = get_settings()
    check_database()

    if settings.run_migrations_on_startup:
        run_migrations()
    elif settings.schema_auto_create:
        SQLModel.metadata.create_all(get_engine())
        logger.info("schema_auto_create_done")
    else:
        logger.info("schema_bootstrap_skipped", hint="set RUN_MIGRATIONS_ON_STARTUP or SCHEMA_AUTO_CREATE")

    # Catches up anything newer than the last migration (safe / idempotent)
    try:
        ensure_schema_compat()
    except Exception as exc:  # noqa: BLE001
        logger.error("schema_compat_failed", error=str(exc))
        raise


def ensure_seeded() -> None:
    """Boot with an empty company shell (login + dept stubs). Company data is uploaded from Setup."""
    settings = get_settings()
    if not settings.auto_seed:
        return
    from sqlmodel import select

    from app.engine.meeting_scenario import ensure_meeting_room_template
    from app.models.org import Tenant

    with Session(get_engine()) as session:
        existing = session.exec(select(Tenant)).first()
        if existing:
            from app.agent.company_seed import ensure_company_seed

            ensure_meeting_room_template(session, existing.tenant_id)
            ensure_company_seed(session, existing.tenant_id)
            session.commit()
            logger.info("seed_skipped_tenant_exists", tenant_id=existing.tenant_id)
            return
        from scripts.bootstrap_empty_company import bootstrap_empty

        tid = bootstrap_empty(session)
        logger.info("empty_company_bootstrapped", tenant_id=tid)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def session_scope() -> Session:
    return Session(get_engine())


def format_startup_error(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
