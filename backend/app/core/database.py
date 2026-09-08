from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.is_sqlite else {}
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug and settings.app_env != "production",
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        if settings.is_sqlite:

            @event.listens_for(_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _engine


def init_db() -> None:
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


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
            return
        seed(session)


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def session_scope() -> Session:
    return Session(get_engine())
