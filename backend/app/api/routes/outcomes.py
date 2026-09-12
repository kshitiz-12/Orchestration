from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import SessionDep, TenantDep, UserDep
from app.engine.outcome_engine import OutcomeEngine
from app.models.intake import AIDecision, Conversation, HumanReviewItem, RawEmailEvent
from app.models.outcome import (
    Approval,
    AuditLog,
    Communication,
    Evidence,
    ExceptionRecord,
    Outcome,
    Requirement,
    Task,
    VendorIssue,
)
from app.schemas.api import (
    ApprovalDecisionRequest,
    ConfirmBookingRequest,
    EvidenceCreate,
    ExceptionResolveRequest,
    TaskStatusUpdate,
)
from app.models.org import utcnow

router = APIRouter(tags=["outcomes"])


@router.get("/dashboard/kpis")
def dashboard_kpis(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    def count(model, *filters):
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id, *filters)
        return session.exec(stmt).one()

    return {
        "outcomes_active": count(
            Outcome,
            Outcome.status.in_(["ACTIVE", "AT_RISK", "BLOCKED", "PARTIALLY_READY", "VALIDATING"]),  # type: ignore
        ),
        "at_risk": count(Outcome, Outcome.status == "AT_RISK"),
        "overdue_tasks": session.exec(
            select(func.count())
            .select_from(Task)
            .where(
                Task.tenant_id == tenant_id,
                Task.due_at < utcnow(),
                Task.status.notin_(["CLOSED", "CANCELLED", "VERIFIED"]),  # type: ignore
            )
        ).one(),
        "pending_approvals": count(Approval, Approval.decision == "PENDING"),
        "human_reviews": count(HumanReviewItem, HumanReviewItem.status == "PENDING"),
        "failures": session.exec(
            select(func.count())
            .select_from(__import__("app.models.intake", fromlist=["ProcessingJob"]).ProcessingJob)
            .where(
                __import__("app.models.intake", fromlist=["ProcessingJob"]).ProcessingJob.tenant_id
                == tenant_id,
                __import__("app.models.intake", fromlist=["ProcessingJob"]).ProcessingJob.status.in_(
                    ["FAILED", "DEAD_LETTER"]
                ),
            )
        ).one(),
        "new_emails_24h": count(RawEmailEvent),
    }


@router.get("/outcomes")
def list_outcomes(
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
    status: str | None = None,
    limit: int = 100,
):
    stmt = select(Outcome).where(Outcome.tenant_id == tenant_id).order_by(Outcome.created_at.desc())  # type: ignore
    if status:
        stmt = stmt.where(Outcome.status == status)
    return session.exec(stmt.limit(limit)).all()


@router.get("/outcomes/{outcome_id}")
def get_outcome(outcome_id: str, session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    requirements = session.exec(select(Requirement).where(Requirement.outcome_id == outcome_id)).all()
    tasks = session.exec(select(Task).where(Task.outcome_id == outcome_id)).all()
    approvals = session.exec(select(Approval).where(Approval.outcome_id == outcome_id)).all()
    exceptions = session.exec(select(ExceptionRecord).where(ExceptionRecord.outcome_id == outcome_id)).all()
    evidence = session.exec(select(Evidence).where(Evidence.outcome_id == outcome_id)).all()
    communications = session.exec(select(Communication).where(Communication.outcome_id == outcome_id)).all()
    vendor_issues = session.exec(select(VendorIssue).where(VendorIssue.outcome_id == outcome_id)).all()
    audit = session.exec(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .where(
            (AuditLog.entity_id == outcome_id)
            | (AuditLog.correlation_id == outcome_id)
            | (AuditLog.correlation_id == outcome.business_event_id)
        )
        .order_by(AuditLog.timestamp.desc())  # type: ignore
        .limit(200)
    ).all()
    email = session.get(RawEmailEvent, outcome.business_event_id) if outcome.business_event_id else None
    thread_emails: list = []
    if outcome.conversation_id:
        thread_emails = session.exec(
            select(RawEmailEvent)
            .where(RawEmailEvent.conversation_id == outcome.conversation_id)
            .order_by(RawEmailEvent.created_at.desc())  # type: ignore
            .limit(20)
        ).all()
        if not email and thread_emails:
            email = thread_emails[0]
    ai = None
    if outcome.conversation_id:
        ai = session.exec(
            select(AIDecision)
            .where(AIDecision.conversation_id == outcome.conversation_id)
            .order_by(AIDecision.created_at.desc())  # type: ignore
        ).first()
    if not ai and email:
        ai = session.exec(
            select(AIDecision).where(AIDecision.event_id == email.event_id).order_by(AIDecision.created_at.desc())  # type: ignore
        ).first()
    conversation = session.get(Conversation, outcome.conversation_id) if outcome.conversation_id else None
    return {
        "outcome": outcome,
        "requirements": requirements,
        "tasks": tasks,
        "approvals": approvals,
        "exceptions": exceptions,
        "evidence": evidence,
        "communications": sorted(communications, key=lambda c: c.created_at or c.sent_at, reverse=True),
        "vendor_issues": vendor_issues,
        "audit": audit,
        "email": email,
        "thread_emails": thread_emails,
        "ai_decision": ai,
        "conversation": conversation,
    }


@router.post("/outcomes/{outcome_id}/close")
def close_outcome(outcome_id: str, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    engine = OutcomeEngine(session, tenant_id)
    try:
        engine.try_close(outcome, actor=user.email)
        session.commit()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return outcome


@router.post("/outcomes/{outcome_id}/confirm-booking")
def confirm_booking(
    outcome_id: str,
    payload: ConfirmBookingRequest,
    session: SessionDep,
    tenant_id: TenantDep,
    user: UserDep,
):
    """Ops confirms a meeting room and emails BOOKING CONFIRMED to the requester."""
    from app.connectors.factory import get_email_provider
    from app.engine.scenarios import ScenarioOrchestrator
    from app.services.communication import CommunicationService

    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    if outcome.template_code != "MEETING_ROOM":
        raise HTTPException(400, "Only meeting room requests can be confirmed this way")

    email = get_email_provider(session, tenant_id)
    sender = email if email.is_connected() else None
    comms = CommunicationService(session, tenant_id, email_sender=sender)
    try:
        updated = ScenarioOrchestrator(session, tenant_id, comms).confirm_meeting_room_booking(
            outcome,
            actor=user.email,
            room_name=payload.room_name,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "ok": True,
        "outcome_id": updated.outcome_id,
        "status": updated.status,
        "booked_room": (updated.facts or {}).get("booked_room"),
        "delivered": True,
    }


@router.post("/outcomes/{outcome_id}/resend-clarification")
def resend_clarification(outcome_id: str, session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    """Force a live clarification email via CloudMailin (prototype helper)."""
    from app.connectors.factory import get_email_provider
    from app.services.communication import CommunicationService

    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    conversation = session.get(Conversation, outcome.conversation_id) if outcome.conversation_id else None
    if not conversation:
        raise HTTPException(400, "Outcome has no conversation")

    questions = []
    for item in conversation.missing_information or []:
        if isinstance(item, dict) and item.get("question"):
            questions.append(item["question"])
    if not questions:
        questions = [
            "How many people will attend?",
            "What date and preferred start time?",
            "How long do you need the room (duration)?",
        ]

    email = get_email_provider(session, tenant_id)
    sender = email if email.is_connected() else None
    if not sender or not getattr(sender, "can_send", sender.is_connected)():
        raise HTTPException(
            400,
            "Outbound email is not configured. Set CLOUDMAILIN_SMTP_URL and CLOUDMAILIN_FROM_EMAIL on the server.",
        )

    latest = session.exec(
        select(RawEmailEvent)
        .where(RawEmailEvent.conversation_id == conversation.conversation_id)
        .order_by(RawEmailEvent.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    in_reply_to = (latest.provider_message_id or latest.gmail_message_id) if latest else None

    # Unique key so resend is allowed
    import time

    msg = CommunicationService(session, tenant_id, email_sender=sender).send(
        communication_type="INFORMATION_REQUIRED",
        recipients=[conversation.requester_email],
        subject=f"[INFORMATION REQUIRED] [{outcome.case_reference}] Additional details needed",
        body=(
            "We need a few details to continue processing your request:\n\n"
            + "\n".join(f"- {q}" for q in questions)
            + "\n\nPlease reply to this email (use Reply so it stays on the same request)."
        ),
        conversation_id=conversation.conversation_id,
        outcome_id=outcome.outcome_id,
        thread_id=conversation.thread_id,
        in_reply_to_message_id=in_reply_to,
        idempotency_key=f"clarify-resend:{outcome.outcome_id}:{int(time.time())}",
    )
    session.commit()
    return {
        "ok": True,
        "message_id": msg.message_id if msg else None,
        "provider_message_id": msg.provider_message_id if msg else None,
        "delivered": bool(msg and msg.provider_message_id),
    }


@router.get("/tasks")
def list_tasks(session: SessionDep, tenant_id: TenantDep, _user: UserDep, outcome_id: str | None = None):
    stmt = select(Task).where(Task.tenant_id == tenant_id)
    if outcome_id:
        stmt = stmt.where(Task.outcome_id == outcome_id)
    return session.exec(stmt.order_by(Task.due_at)).all()  # type: ignore


@router.post("/tasks/{task_id}/status")
def update_task(task_id: str, payload: TaskStatusUpdate, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    task = session.get(Task, task_id)
    if not task or task.tenant_id != tenant_id:
        raise HTTPException(404, "Task not found")
    engine = OutcomeEngine(session, tenant_id)
    try:
        engine.update_task_status(task, payload.status, actor=user.email, resolution=payload.resolution)
        session.commit()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return task


@router.post("/evidence")
def add_evidence(payload: EvidenceCreate, session: SessionDep, tenant_id: TenantDep, user: UserDep, outcome_id: str):
    from app.audit.service import AuditService
    from app.core.enums import AuditAction

    ev = Evidence(
        tenant_id=tenant_id,
        outcome_id=outcome_id,
        task_id=payload.task_id,
        requirement_id=payload.requirement_id,
        evidence_type=payload.evidence_type,
        description=payload.description,
        record_ref=payload.record_ref,
        submitted_by=user.person_id,
        status="SUBMITTED",
    )
    session.add(ev)
    session.flush()
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=AuditAction.EVIDENCE_ADDED,
        entity_type="Evidence",
        entity_id=ev.evidence_id,
        after=payload.model_dump(),
        correlation_id=outcome_id,
    )
    session.commit()
    return ev


@router.post("/evidence/{evidence_id}/verify")
def verify_evidence(evidence_id: str, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    from app.audit.service import AuditService
    from app.core.enums import AuditAction

    ev = session.get(Evidence, evidence_id)
    if not ev or ev.tenant_id != tenant_id:
        raise HTTPException(404, "Evidence not found")
    ev.status = "VERIFIED"
    ev.verifier_person_id = user.person_id
    ev.verified_at = utcnow()
    session.add(ev)
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=AuditAction.EVIDENCE_VERIFIED,
        entity_type="Evidence",
        entity_id=ev.evidence_id,
        after={"status": "VERIFIED"},
        correlation_id=ev.outcome_id,
    )
    if ev.task_id:
        task = session.get(Task, ev.task_id)
        if task and task.status == "COMPLETED_PENDING_EVIDENCE":
            OutcomeEngine(session, tenant_id).update_task_status(task, "VERIFIED", actor=user.email)
    session.commit()
    return ev


@router.post("/approvals/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    session: SessionDep,
    tenant_id: TenantDep,
    user: UserDep,
):
    from app.audit.service import AuditService
    from app.core.enums import AuditAction

    approval = session.get(Approval, approval_id)
    if not approval or approval.tenant_id != tenant_id:
        raise HTTPException(404, "Approval not found")
    approval.decision = payload.decision
    approval.reason = payload.reason
    approval.decided_at = utcnow()
    approval.approver_person_id = user.person_id
    session.add(approval)
    action = AuditAction.APPROVAL_GRANTED if payload.decision == "APPROVED" else AuditAction.APPROVAL_REJECTED
    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=action,
        entity_type="Approval",
        entity_id=approval.approval_id,
        after=payload.model_dump(),
        correlation_id=approval.outcome_id,
    )
    session.commit()
    return approval


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(
    exception_id: str,
    payload: ExceptionResolveRequest,
    session: SessionDep,
    tenant_id: TenantDep,
    user: UserDep,
):
    exc = session.get(ExceptionRecord, exception_id)
    if not exc or exc.tenant_id != tenant_id:
        raise HTTPException(404, "Exception not found")
    exc.resolution = payload.resolution
    exc.status = payload.status
    exc.resolved_at = utcnow()
    session.add(exc)
    session.commit()
    return exc
