import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Force sqlite + heuristic AI before app import
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GEMINI_API_KEY"] = ""
os.environ["SECRET_KEY"] = "test-secret"
os.environ["APP_ENV"] = "prototype"
os.environ["EMAIL_PROVIDER"] = "cloudmailin"
os.environ["CLOUDMAILIN_WEBHOOK_SECRET"] = ""


from app.core.database import get_session  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from scripts.seed import seed  # noqa: E402

get_settings.cache_clear()


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        seed(session)
        yield session


@pytest.fixture()
def client(engine, session) -> Generator[TestClient, None, None]:
    app = create_app()

    def _override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client) -> dict:
    resp = client.post("/api/v1/auth/login", json={"email": "admin@prototype.local", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
