"""Dashboard 'waiting on you' must match the Needs your decision inbox."""

from sqlmodel import Session, select

from app.models.intake import HumanReviewItem, RawEmailEvent
from app.models.org import Tenant
from app.models.outcome import Approval, Outcome


def _tenant(session: Session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def _email(session: Session, tenant_id: str, suffix: str) -> RawEmailEvent:
    event = RawEmailEvent(
        tenant_id=tenant_id,
        idempotency_key=f"inbox-{suffix}",
        provider="API",
        provider_message_id=f"msg-{suffix}",
        gmail_message_id=f"msg-{suffix}",
        source="API",
        sender="ops@acme.demo",
        subject=f"Inbox {suffix}",
        body_text="Please decide",
        body_for_ai="Please decide",
    )
    session.add(event)
    session.flush()
    return event


def test_reviews_inbox_matches_waiting_on_you_kpi(client, session: Session, auth_headers):
    tenant_id = _tenant(session)

    event = _email(session, tenant_id, "review")
    session.add(
        HumanReviewItem(
            tenant_id=tenant_id,
            event_id=event.event_id,
            status="PENDING",
            reason="Low confidence extraction",
        )
    )

    open_case = Outcome(
        tenant_id=tenant_id,
        case_reference="ROOM-INBOX-OPEN",
        template_code="MEETING_ROOM",
        category="MEETING",
        title="Open catering case",
        requester_email="host@acme.demo",
        status="ACTIVE",
        facts={"pending_confirmation": False},
    )
    closed_case = Outcome(
        tenant_id=tenant_id,
        case_reference="ROOM-INBOX-CLOSED",
        template_code="MEETING_ROOM",
        category="MEETING",
        title="Closed leftover approval",
        requester_email="host@acme.demo",
        status="CLOSED",
        facts={},
    )
    confirm_case = Outcome(
        tenant_id=tenant_id,
        case_reference="ROOM-INBOX-CONFIRM",
        template_code="MEETING_ROOM",
        category="MEETING",
        title="Waiting on room confirm",
        requester_email="host@acme.demo",
        status="ACTIVE",
        facts={
            "pending_confirmation": True,
            "proposed_room": {"name": "F2-R1"},
        },
    )
    session.add(open_case)
    session.add(closed_case)
    session.add(confirm_case)
    session.flush()

    session.add(
        Approval(
            tenant_id=tenant_id,
            outcome_id=open_case.outcome_id,
            approval_type="CATERING_SPEND",
            decision="PENDING",
            payload={"amount_ex_tax": 4200, "currency": "INR", "vendor": "Cafe Demo"},
        )
    )
    session.add(
        Approval(
            tenant_id=tenant_id,
            outcome_id=closed_case.outcome_id,
            approval_type="CATERING_SPEND",
            decision="PENDING",
            payload={"amount_ex_tax": 99, "currency": "INR"},
        )
    )
    session.commit()

    inbox = client.get("/api/v1/reviews", headers=auth_headers)
    assert inbox.status_code == 200, inbox.text
    rows = inbox.json()
    kinds = sorted(row["kind"] for row in rows)
    assert kinds == ["approval", "confirm_booking", "review"]
    assert all("kind" in row for row in rows)
    assert next(row for row in rows if row["kind"] == "approval")["approval"]["approval_id"]
    assert next(row for row in rows if row["kind"] == "confirm_booking")["proposed_room"] == "F2-R1"
    assert next(row for row in rows if row["kind"] == "review")["review"]["review_id"]

    kpis = client.get("/api/v1/dashboard/kpis", headers=auth_headers)
    assert kpis.status_code == 200, kpis.text
    data = kpis.json()
    assert data["human_reviews"] == 1
    assert data["pending_approvals"] == 1
    assert data["pending_confirmations"] == 1
    assert data["waiting_on_you"] == 3
    assert data["waiting_on_you"] == len(rows)
