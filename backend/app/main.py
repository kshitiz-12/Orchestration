from contextlib import asynccontextmanager
from pathlib import Path
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import ensure_seeded, format_startup_error, get_engine, init_db
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestIdMiddleware

# Render health-checks the open port before FastAPI lifespan finishes if DB init is slow.
# Bind first; finish schema/seed in a background thread. /health = liveness, /ready = DB.
_db_ready = threading.Event()
_db_error: str | None = None
_db_lock = threading.Lock()


def _set_db_error(msg: str) -> None:
    global _db_error
    with _db_lock:
        _db_error = msg


def _get_db_error() -> str | None:
    with _db_lock:
        return _db_error


def _boot_database(settings, logger) -> None:
    global _db_error
    try:
        init_db()
        ensure_seeded()
        with _db_lock:
            _db_error = None
        _db_ready.set()
        logger.info("database_ready", auto_seed=settings.auto_seed)
    except Exception as exc:  # noqa: BLE001
        _set_db_error(str(exc))
        logger.error("startup_failed", error=str(exc), traceback=format_startup_error(exc))
        # Leave _db_ready unset — /ready stays 503; process stays up for Render port check


_WEAK_ADMIN_PASSWORDS = {"", "admin123", "password", "changeme", "change-me", "secret"}


def _is_weak_admin_password(password: str | None) -> bool:
    return (password or "").strip().lower() in _WEAK_ADMIN_PASSWORDS


def _validate_production(settings, logger) -> None:
    """Hard-fail only on secrets that every request needs. Weak ADMIN_PASSWORD is enforced
    when creating a new seeded admin — not when the tenant already exists (common on Render redeploy).
    """
    if not settings.is_production:
        return
    if not (settings.admin_ops_email or "").strip():
        raise RuntimeError(
            "ADMIN_OPS_EMAIL is required in production — set the company admin mailbox used for ops mail."
        )
    sk = (settings.secret_key or "").strip()
    if not sk or sk in {"change-me-to-a-long-random-string", "secret", "changeme"}:
        raise RuntimeError("SECRET_KEY must be set to a long random value in production.")
    if settings.auto_seed and _is_weak_admin_password(settings.admin_password):
        # Do not crash lifespan — that blocks Render port bind. Seed path refuses weak PW on create.
        logger.warning(
            "weak_admin_password",
            hint="Set a strong ADMIN_PASSWORD on Render. Ignored when tenant already exists.",
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(settings.debug)
    logger = get_logger("startup")
    backend_root = Path(__file__).resolve().parent.parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    Path("./secrets").mkdir(parents=True, exist_ok=True)

    db_host = settings.database_url.split("@")[-1][:80] if "@" in settings.database_url else "local"
    logger.info(
        "startup_begin",
        env=settings.app_env,
        database=db_host,
        schema_auto_create=settings.schema_auto_create,
        run_migrations=settings.run_migrations_on_startup,
    )

    _validate_production(settings, logger)

    # Sync DB boot in tests (deterministic). Async bind-first in real deploys (Render port scan).
    stop = threading.Event()
    if "pytest" in sys.modules:
        _boot_database(settings, logger)
    else:
        threading.Thread(
            target=_boot_database,
            args=(settings, logger),
            name="db-boot",
            daemon=True,
        ).start()
        logger.info("database_boot_deferred", reason="bind_port_before_schema_sync")

    interval = int(settings.inprocess_sweeper_seconds or 0)
    if interval > 0 and "pytest" not in sys.modules:
        threading.Thread(target=_sweeper_loop, args=(stop, interval), name="hold-sweeper", daemon=True).start()
    yield
    stop.set()


def _sweeper_loop(stop: threading.Event, interval: int) -> None:
    """Render runs mail processing inside the web process, so sweeps must too."""
    from sqlmodel import Session, select

    from app.models.org import Tenant
    from app.services.hold_sweeper import run_all_sweeps

    logger = get_logger("sweeper")
    while not stop.wait(interval):
        if not _db_ready.is_set():
            continue
        try:
            with Session(get_engine()) as session:
                for tenant in session.exec(select(Tenant)).all():
                    run_all_sweeps(session, tenant.tenant_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sweeper_loop_failed", error=str(exc))


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health")
    def health():
        """Liveness — process is up (Render healthCheckPath). Does not wait for DB."""
        return {
            "status": "ok",
            "env": settings.app_env,
            "database_ready": _db_ready.is_set(),
        }

    @app.get("/ready")
    def ready():
        """Readiness — database schema/seed finished and reachable."""
        if not _db_ready.is_set():
            err = _get_db_error()
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "database": "booting" if not err else "failed",
                    "error": err,
                },
            )
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": str(exc)},
            )

    return app


app = create_app()
