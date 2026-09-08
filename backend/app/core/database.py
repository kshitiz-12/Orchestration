from collections.abc import Generator
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


def run_migrations() -> None:
    """Apply Alembic migrations to head (production-safe schema path)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    logger.info("migrations_applied", revision="head")


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


def ensure_seeded() -> None:
    """Idempotent seed so Render/Postgres boots with demo data."""
    settings = get_settings()
    if not settings.auto_seed:
        return
    from sqlmodel import select

    from app.models.org import Tenant
    from scripts.seed import seed

    with Session(get_engine()) as session:
        existing = session.exec(select(Tenant)).first()
        if existing:
            logger.info("seed_skipped_tenant_exists", tenant_id=existing.tenant_id)
            return
        tid = seed(session)
        logger.info("seed_completed", tenant_id=tid)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def session_scope() -> Session:
    return Session(get_engine())


def format_startup_error(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
