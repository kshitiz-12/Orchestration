"""Harden pass: bootstrap password, API header forge strip, analytics verification."""

import uuid

import pytest
from sqlmodel import Session, select

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.core.config import get_settings
from app.core.security import verify_password
from app.engine.pipeline import ProcessingPipeline
from app.models.intake import RawEmailEvent
from app.models.org import Person, Tenant
from app.models.outcome import Communication
from app.services.admin_commands import sanitize_api_email_headers
from app.services.intake import IntakeService
from app.services.ops_ledger import record
from scripts.bootstrap_empty_company import bootstrap_empty

ADMIN = "ops-desk@example.com"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ADMIN_OPS_EMAIL", ADMIN)
    monkeypatch.setenv("ADMIN_SENDER_VERIFICATION", "strict")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _tid(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def test_sanitize_api_email_headers_strips_spf_dkim():
    cleaned = sanitize_api_email_headers(
        {
            "From": "ops@example.com",
            "_envelope": {"spf": {"result": "pass", "domain": "example.com"}},
            "Authentication-Results": "mx; dkim=pass header.d=example.com",
            "Subject": "Spend?",
        }
    )
    assert "From" in cleaned
    assert "Subject" in cleaned
    assert "_envelope" not in cleaned
    assert "Authentication-Results" not in cleaned


def test_api_intake_strips_forged_auth_headers(session: Session, env):
    tid = _tid(session)
    service = IntakeService(session, tid)
    result = service.ingest(
        message_id=f"<{uuid.uuid4().hex}@api>",
        thread_id="api-thread-1",
        sender=ADMIN,
        recipients=["desk@example.com"],
        subject="How much did we spend?",
        body_text="How much did FACILITIES spend last 30 days?",
        source="API",
        headers={
            "_envelope": {"spf": {"result": "pass", "domain": "example.com"}},
            "authentication-results": "mx; dkim=pass header.d=example.com",
            "X-Custom": "keep-me",
        },
    )
    event = session.get(RawEmailEvent, result["event_id"])
    assert event is not None
    assert "_envelope" not in (event.headers or {})
    assert "authentication-results" not in {k.lower() for k in (event.headers or {})}
    assert (event.headers or {}).get("X-Custom") == "keep-me"


def test_ops_analytics_rejects_unverified_sender(session: Session, env):
    tid = _tid(session)
    record(
        session,
        tid,
        event_type="SPEND_RECORDED",
        summary="test spend",
        amount=999.0,
        department_code="FACILITIES",
        actor_role="system",
    )
    session.commit()
    mid = f"<{uuid.uuid4().hex}@mail>"
    ev = RawEmailEvent(
        tenant_id=tid,
        idempotency_key=mid,
        provider="CLOUDMAILIN",
        provider_message_id=mid,
        provider_conversation_id=mid,
        gmail_message_id=mid,
        gmail_thread_id=mid,
        source="CLOUDMAILIN",
        sender=ADMIN,
        subject="Spend",
        body_text="How much did FACILITIES spend in the last 30 days?",
        body_for_ai="How much did FACILITIES spend in the last 30 days?",
        headers={},  # no SPF/DKIM — must not answer under strict verification
    )
    session.add(ev)
    session.commit()
    result = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider())).process_event(ev.event_id)
    assert result["status"] == "ops_analytics_unverified"
    assert result["replied"] is False
    assert not [
        m for m in session.exec(select(Communication)).all() if ADMIN in (m.recipients or []) and "999" in (m.body or "")
    ]


def test_bootstrap_uses_admin_password_env(session: Session, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@company.test")
    monkeypatch.setenv("ADMIN_PASSWORD", "Str0ng-Prod-Pass!")
    monkeypatch.setenv("APP_ENV", "prototype")
    get_settings.cache_clear()
    # Wipe people so bootstrap creates fresh admin for this email
    for p in session.exec(select(Person)).all():
        session.delete(p)
    session.commit()
    tid = bootstrap_empty(session)
    admin = session.exec(select(Person).where(Person.tenant_id == tid, Person.email == "boss@company.test")).one()
    assert verify_password("Str0ng-Prod-Pass!", admin.password_hash)
    get_settings.cache_clear()


def test_bootstrap_rejects_weak_password_in_production(session: Session, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        bootstrap_empty(session)
    get_settings.cache_clear()
