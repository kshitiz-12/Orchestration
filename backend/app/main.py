from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import ensure_seeded, format_startup_error, get_engine, init_db
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestIdMiddleware


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

    try:
        init_db()
        ensure_seeded()
        logger.info("database_ready", auto_seed=settings.auto_seed)
    except Exception as exc:  # noqa: BLE001
        logger.error("startup_failed", error=str(exc), traceback=format_startup_error(exc))
        raise
    yield


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
        """Liveness — process is up."""
        return {"status": "ok", "env": settings.app_env}

    @app.get("/ready")
    def ready():
        """Readiness — database reachable (use for load balancers)."""
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "not_ready", "database": str(exc)}

    return app


app = create_app()
