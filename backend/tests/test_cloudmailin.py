"""CloudMailin webhook normalize + idempotency tests."""

from app.connectors.cloudmailin import normalize_cloudmailin_payload
from app.models.org import Tenant
from app.models.outcome import Outcome
from app.services.intake import IntakeService
from sqlmodel import select


SAMPLE = {
    "envelope": {
        "to": "inbox@demo.cloudmailin.net",
        "from": "alice@example.com",
        "recipients": ["inbox@demo.cloudmailin.net"],
    },
    "headers": {
        "message_id": "<abc123@example.com>",
        "subject": "Meeting Room Request",
        "from": "Alice <alice@example.com>",
        "to": "inbox@demo.cloudmailin.net",
    },
    "plain": "Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours.",
    "html": None,
    "attachments": [],
}


def test_normalize_cloudmailin_payload():
    event = normalize_cloudmailin_payload(SAMPLE)
    d = event.to_intake_dict()
    assert d["message_id"] == "<abc123@example.com>"
    assert d["thread_id"] == "<abc123@example.com>"
    assert d["sender"] == "alice@example.com"
    assert "8 people" in d["body_text"]


def test_continuation_uses_in_reply_to_thread():
    reply = {
        **SAMPLE,
        "headers": {
            "message_id": "<reply456@example.com>",
            "in_reply_to": "<abc123@example.com>",
            "references": "<abc123@example.com>",
            "subject": "Re: Meeting Room Request",
            "from": "alice@example.com",
            "to": "inbox@demo.cloudmailin.net",
        },
        "plain": "8 people, 3 PM, for 2 hours.",
        "reply_plain": "8 people, 3 PM, for 2 hours.",
    }
    event = normalize_cloudmailin_payload(reply)
    assert event.provider_conversation_id == "<abc123@example.com>"


def test_continuation_prefers_references_root_over_clarification_id():
    """Reply to our outbound clarification must stay on the original thread."""
    reply = {
        **SAMPLE,
        "headers": {
            "message_id": "<gmail-reply@mail.gmail.com>",
            "in_reply_to": "<clarification-id@cloudmta.net>",
            "references": "<abc123@example.com> <clarification-id@cloudmta.net>",
            "subject": "Re: [INFORMATION REQUIRED] [EVT-2026-0006] Additional details needed",
            "from": "alice@example.com",
            "to": "inbox@demo.cloudmailin.net",
        },
        "plain": "10 members will be there",
        "reply_plain": "10 members will be there",
    }
    event = normalize_cloudmailin_payload(reply)
    assert event.provider_conversation_id == "<abc123@example.com>"


def test_cloudmailin_ingest_idempotent(session):
    tid = session.exec(select(Tenant)).first().tenant_id
    intake = IntakeService(session, tid)
    event = normalize_cloudmailin_payload(SAMPLE)
    a = intake.ingest(
        message_id=event.provider_message_id,
        thread_id=event.provider_conversation_id,
        sender=event.sender,
        recipients=event.recipients,
        subject=event.subject,
        body_text=event.body_text,
        source="CLOUDMAILIN",
    )
    b = intake.ingest(
        message_id=event.provider_message_id,
        thread_id=event.provider_conversation_id,
        sender=event.sender,
        recipients=event.recipients,
        subject=event.subject,
        body_text=event.body_text,
        source="CLOUDMAILIN",
    )
    assert a["status"] == "queued"
    assert b["status"] == "deduplicated"


def test_cloudmailin_webhook_endpoint(client):
    res = client.post("/api/v1/webhooks/cloudmailin", json=SAMPLE)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["provider"] == "CLOUDMAILIN"
    assert body["ingest"]["status"] in {"queued", "deduplicated"}
    # duplicate POST
    res2 = client.post("/api/v1/webhooks/cloudmailin", json=SAMPLE)
    assert res2.json()["ingest"]["status"] == "deduplicated"
