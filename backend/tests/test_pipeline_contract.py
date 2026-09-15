"""Pipeline must not COMPLETE while blocking; communication keyed by event_id."""

from sqlmodel import select

from app.ai.gemini import HeuristicProvider
from app.ai.service import LLMService
from app.core.enums import ProcessingStage
from app.engine.pipeline import ProcessingPipeline
from app.models.intake import RawEmailEvent
from app.models.org import Tenant
from app.models.outcome import Communication, Outcome
from app.services.intake import IntakeService


def _tid(session) -> str:
    return session.exec(select(Tenant)).first().tenant_id


def test_incomplete_meeting_event_stays_communication_not_completed(session):
    tid = _tid(session)
    intake = IntakeService(session, tid)
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))
    ingested = intake.ingest(
        message_id="pipe-block-1",
        thread_id="conv-pipe-block",
        sender="arun.kumar@company.com",
        recipients=["facilities@acme.demo"],
        subject="Meeting room required for 18 September",
        body_text="Please book a meeting room for 18 September.",
        source="OUTLOOK",
    )
    result = pipeline.process_event(ingested["event_id"])
    event = session.get(RawEmailEvent, ingested["event_id"])
    assert result["status"] == "clarification_sent"
    assert event.processing_stage == ProcessingStage.COMMUNICATION.value
    outcome = session.get(Outcome, result["outcome_id"])
    assert (outcome.facts or {}).get("orchestration_stage") == "AWAITING_REQUIREMENTS"
    assert meeting_comms(session, outcome.outcome_id)


def meeting_comms(session, outcome_id: str) -> list[Communication]:
    return session.exec(select(Communication).where(Communication.outcome_id == outcome_id)).all()


def test_follow_up_clarification_keyed_by_event_id(session):
    tid = _tid(session)
    intake = IntakeService(session, tid)
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))
    first = intake.ingest(
        message_id="pipe-fu-1",
        thread_id="conv-pipe-fu",
        sender="arun.kumar@company.com",
        recipients=["facilities@acme.demo"],
        subject="Need a meeting room",
        body_text="Please book a meeting room for 18 September.",
        source="OUTLOOK",
    )
    r1 = pipeline.process_event(first["event_id"])
    outcome_id = r1["outcome_id"]
    second = intake.ingest(
        message_id="pipe-fu-2",
        thread_id="conv-pipe-fu",
        sender="arun.kumar@company.com",
        recipients=["facilities@acme.demo"],
        subject="Re: [INFORMATION REQUIRED] Need a meeting room",
        body_text="internal , non veg , rahul and aman",
        source="OUTLOOK",
    )
    r2 = pipeline.process_event(second["event_id"])
    event2 = session.get(RawEmailEvent, second["event_id"])
    assert event2.processing_stage != ProcessingStage.COMPLETED.value
    assert r2["status"] in {"clarification_sent", "no_resource"}
    mails = meeting_comms(session, outcome_id)
    clarify = [m for m in mails if "INFORMATION REQUIRED" in (m.subject or "")]
    assert len(clarify) >= 2
    keys = {m.idempotency_key for m in clarify}
    assert any(second["event_id"] in (k or "") for k in keys)


def test_no_resource_event_not_marked_completed(session):
    tid = _tid(session)
    intake = IntakeService(session, tid)
    pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))
    ingested = intake.ingest(
        message_id="pipe-cap-1",
        thread_id="conv-pipe-cap",
        sender="big.team@company.com",
        recipients=["facilities@acme.demo"],
        subject="Need a meeting room for all hands",
        body_text=(
            "Book a meeting room for 80 people on 22 September 2026 from 2pm to 5pm. "
            "Internal meeting at Corporate Office. No visitors. No catering. Display required."
        ),
        source="OUTLOOK",
    )
    result = pipeline.process_event(ingested["event_id"])
    event = session.get(RawEmailEvent, ingested["event_id"])
    outcome = session.get(Outcome, result["outcome_id"])
    stage = (outcome.facts or {}).get("orchestration_stage")
    assert stage in {"NO_RESOURCE", "AWAITING_REQUIREMENTS"}
    assert event.processing_stage != ProcessingStage.COMPLETED.value
    if stage == "NO_RESOURCE":
        assert result["status"] == "no_resource"
