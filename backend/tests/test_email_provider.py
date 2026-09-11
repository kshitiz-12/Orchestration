"""Mocked Microsoft Graph / Outlook provider tests (no live Outlook account)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlmodel import select

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.connectors.factory import get_email_provider
from app.connectors.gmail import InMemoryEmailChannel
from app.connectors.outlook import (
    OutlookGraphProvider,
    microsoft_auth_url,
    save_outlook_credentials,
)
from app.core.config import get_settings
from app.engine.pipeline import ProcessingPipeline
from app.models.integrations import IntegrationCredential
from app.models.org import Tenant
from app.models.outcome import Outcome
from app.schemas.email import NormalizedEmailEvent
from app.services.communication import CommunicationService
from app.services.email_poll import poll_and_process
from app.services.intake import IntakeService


class OutlookMemoryChannel(InMemoryEmailChannel):
    @property
    def provider_name(self) -> str:
        return "OUTLOOK"


def test_factory_defaults_to_cloudmailin(session):
    get_settings.cache_clear()
    tid = session.exec(select(Tenant)).first().tenant_id
    provider = get_email_provider(session, tid)
    assert provider.provider_name == "CLOUDMAILIN"


def test_normalize_graph_message_shape():
    p = OutlookGraphProvider()
    event = p._normalize(
        {
            "id": "msg-1",
            "conversationId": "conv-1",
            "subject": "Meeting Room Request",
            "body": {"contentType": "Text", "content": "Need a room for 8 people"},
            "from": {"emailAddress": {"address": "a@outlook.com"}},
            "toRecipients": [{"emailAddress": {"address": "inbox@outlook.com"}}],
            "ccRecipients": [],
            "receivedDateTime": "2026-09-12T10:00:00Z",
            "internetMessageId": "<x@outlook.com>",
        },
        [],
    )
    assert isinstance(event, NormalizedEmailEvent)
    d = event.to_intake_dict()
    assert d["message_id"] == "msg-1"
    assert d["thread_id"] == "conv-1"
    assert d["sender"] == "a@outlook.com"


def test_oauth_url_requires_client_id(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="MICROSOFT_CLIENT_ID"):
        microsoft_auth_url(state="abc")
    get_settings.cache_clear()


def test_oauth_url_includes_personal_tenant(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "common")
    get_settings.cache_clear()
    url = microsoft_auth_url(state="abc")
    assert "login.microsoftonline.com/common" in url
    assert "test-client-id" in url
    assert "Mail.Read" in url or "Mail.Read" in get_settings().microsoft_scopes
    get_settings.cache_clear()


def test_scopes_exclude_mail_readwrite():
    scopes = get_settings().microsoft_scopes
    assert "Mail.Read" in scopes
    assert "Mail.Send" in scopes
    assert "Mail.ReadWrite" not in scopes


def test_outlook_source_idempotent_poll(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    ch = OutlookMemoryChannel()
    payload = {
        "message_id": "graph-msg-1",
        "thread_id": "graph-conv-1",
        "sender": "employee1@acme.demo",
        "recipients": ["facilities@acme.demo"],
        "cc": [],
        "subject": "Need a meeting room for 8 people tomorrow at 3 PM for 2 hours",
        "body_text": "Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours.",
        "attachments": [],
        "headers": {},
    }
    ch.inbox = [payload]
    r1 = poll_and_process(session, tid, provider=ch, process=True)
    assert r1["ok"] is True
    assert r1["fetched"] == 1

    ch.inbox = [dict(payload)]
    r2 = poll_and_process(session, tid, provider=ch, process=True)
    assert r2["results"][0]["ingest"]["status"] == "deduplicated"
    assert len(session.exec(select(Outcome)).all()) == 1


def test_same_thread_reply_merges_conversation(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    intake = IntakeService(session, tid)
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))

    a = intake.ingest(
        message_id="out-1",
        thread_id="conv-room-1",
        sender="employee4@acme.demo",
        recipients=["facilities@acme.demo"],
        subject="Need a room for 15 people",
        body_text="I need a room/resources for tomorrow for 15 people.",
        source="OUTLOOK",
    )
    pipeline.process_event(a["event_id"])
    b = intake.ingest(
        message_id="out-2",
        thread_id="conv-room-1",
        sender="employee4@acme.demo",
        recipients=["facilities@acme.demo"],
        subject="Re: Need a room",
        body_text="2 PM to 4 PM.",
        source="OUTLOOK",
    )
    pipeline.process_event(b["event_id"])
    assert len(session.exec(select(Outcome)).all()) == 1


def test_clarification_calls_send_reply(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    intake = IntakeService(session, tid)
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))
    ingested = intake.ingest(
        message_id="clarify-1",
        thread_id="conv-clarify-1",
        sender="employee4@acme.demo",
        recipients=["facilities@acme.demo"],
        subject="Need a room",
        body_text="I need a meeting room tomorrow.",
        source="OUTLOOK",
    )
    pipeline.process_event(ingested["event_id"])

    from app.models.intake import Conversation

    conversation = session.exec(select(Conversation)).first()
    assert conversation is not None

    sender = OutlookMemoryChannel()
    comms = CommunicationService(session, tid, email_sender=sender)
    msg = comms.send_clarification(
        conversation=conversation,
        questions=["How many attendees?", "Preferred time?", "Duration?"],
        case_reference="CASE-TEST",
    )
    session.commit()
    assert msg is not None
    assert len(sender.outbox) == 1
    assert sender.outbox[0]["thread_id"] == conversation.thread_id


def test_fetch_skips_known_ids(session, monkeypatch):
    tid = session.exec(select(Tenant)).first().tenant_id
    # Seed credential so provider is "connected"
    row = IntegrationCredential(
        tenant_id=tid,
        provider="OUTLOOK",
        account_email="test@outlook.com",
        token_json=json.dumps({"access_token": "tok", "refresh_token": "ref"}),
        status="ACTIVE",
    )
    session.add(row)
    session.commit()

    intake = IntakeService(session, tid)
    intake.ingest(
        message_id="already-seen",
        thread_id="c1",
        sender="a@b.com",
        recipients=["x@y.com"],
        subject="old",
        body_text="old",
        source="OUTLOOK",
    )

    provider = OutlookGraphProvider(session, tid)
    provider._access_token = "tok"

    graph_payload = {
        "value": [
            {
                "id": "already-seen",
                "conversationId": "c1",
                "subject": "old",
                "body": {"contentType": "Text", "content": "old"},
                "from": {"emailAddress": {"address": "a@b.com"}},
                "toRecipients": [{"emailAddress": {"address": "x@y.com"}}],
                "ccRecipients": [],
                "receivedDateTime": "2026-09-12T10:00:00Z",
                "hasAttachments": False,
            },
            {
                "id": "brand-new",
                "conversationId": "c2",
                "subject": "new",
                "body": {"contentType": "Text", "content": "new body"},
                "from": {"emailAddress": {"address": "a@b.com"}},
                "toRecipients": [{"emailAddress": {"address": "x@y.com"}}],
                "ccRecipients": [],
                "receivedDateTime": "2026-09-12T11:00:00Z",
                "hasAttachments": False,
            },
        ]
    }

    class FakeResp:
        status_code = 200
        headers = {}
        text = ""

        def json(self):
            return graph_payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def request(self, method, url, headers=None, **kwargs):
            return FakeResp()

        def get(self, *a, **k):
            return FakeResp()

    with patch("app.connectors.outlook.httpx.Client", FakeClient):
        with patch("app.connectors.outlook._graph_request", lambda *a, **k: FakeResp()):
            msgs = provider.fetch_unread(max_results=10)
    assert len(msgs) == 1
    assert msgs[0]["message_id"] == "brand-new"


def test_send_reply_uses_graph_reply_endpoint(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    session.add(
        IntegrationCredential(
            tenant_id=tid,
            provider="OUTLOOK",
            account_email="test@outlook.com",
            token_json=json.dumps({"access_token": "tok"}),
            status="ACTIVE",
        )
    )
    session.commit()
    provider = OutlookGraphProvider(session, tid)
    provider._access_token = "tok"

    called = {}

    class FakeResp:
        status_code = 202
        headers = {}
        text = ""

        def json(self):
            return {}

    def fake_request(client, method, url, headers=None, **kwargs):
        called["method"] = method
        called["url"] = url
        called["json"] = kwargs.get("json")
        return FakeResp()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("app.connectors.outlook.httpx.Client", FakeClient):
        with patch("app.connectors.outlook._graph_request", fake_request):
            mid = provider.send_reply(
                to=["a@b.com"],
                subject="Re: room",
                body="How many people?",
                conversation_id="conv-x",
                in_reply_to_message_id="msg-parent",
            )
    assert mid == "msg-parent"
    assert called["method"] == "POST"
    assert "/messages/msg-parent/reply" in called["url"]
