from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.database import ensure_seeded, init_db
from app.core.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    setup_logging(settings.debug)
    logger = get_logger("startup")
    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    Path("./secrets").mkdir(parents=True, exist_ok=True)
    init_db()
    try:
        ensure_seeded()
        logger.info("database_ready", auto_seed=settings.auto_seed)
    except Exception as exc:  # noqa: BLE001
        logger.error("seed_failed", error=str(exc))
        raise
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
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
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
