from datetime import timedelta

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, func, select

from app.agent.learning import CLOSURE_LABELS
from app.agent.playbooks import DECISION_CLASSES
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
    OverrideFactsRequest,
    ReopenOutcomeRequest,
    TaskStatusUpdate,
)
from app.models.org import utcnow
from app.services.operator_inbox import OPEN_OUTCOME_STATUSES, inbox_kpi_counts

router = APIRouter(tags=["outcomes"])


@router.get("/dashboard/kpis")
def dashboard_kpis(session: SessionDep, tenant_id: TenantDep, _user: UserDep):
    def count(model, *filters):
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id, *filters)
        return session.exec(stmt).one()

    return {
        "outcomes_active": count(
            Outcome,
            Outcome.status.in_(list(OPEN_OUTCOME_STATUSES)),  # type: ignore
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
        **inbox_kpi_counts(session, tenant_id),
        **_wait_kpis(session, tenant_id),
        **_automation_kpis(session, tenant_id),
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
        "new_emails_24h": count(RawEmailEvent, RawEmailEvent.created_at >= utcnow() - timedelta(hours=24)),
    }


def type_label(outcome: Outcome) -> str:
    from app.agent.playbooks import label_for

    facts = outcome.facts or {}
    if outcome.template_code == "SERVICE_REQUEST":
        return facts.get("category_label") or label_for(facts.get("agent_category") or outcome.category)
    if outcome.template_code == "MEETING_ROOM":
        return "Training / event" if (outcome.case_reference or "").startswith("TRG-") else "Meeting room"
    return label_for((outcome.category or outcome.template_code or "general").lower())


def department_of(outcome: Outcome) -> str:
    facts = outcome.facts or {}
    if facts.get("department_name"):
        return facts["department_name"]
    return {"MEETING_ROOM": "Admin & Workplace", "INVOICE": "Finance & Accounts"}.get(outcome.template_code or "", "Admin & Workplace")


def waiting_on(outcome: Outcome) -> str:
    """Who the case is waiting on right now, in one word: requester, approver, team, admin or nobody."""
    facts = outcome.facts or {}
    if outcome.status in {"CLOSED", "CANCELLED", "ADMINISTRATIVELY_CLOSED", "VERIFIED"}:
        return "nobody"
    stage = str(facts.get("agent_stage") or facts.get("orchestration_stage") or "").upper()
    if outcome.status == "RESOLVED" or stage in {"RESOLVED", "COMPLETED"}:
        return "requester"
    if stage in {"AWAITING_INFO", "AWAITING_REQUIREMENTS"} or (facts.get("checklist_missing") and not facts.get("booked_room")):
        return "requester"
    if stage == "AWAITING_APPROVAL" or facts.get("approval_pending"):
        return "approver"
    if facts.get("pending_confirmation") and not facts.get("booked_room"):
        return "requester"
    if stage in {"BLOCKED", "NO_RESOURCE"} or outcome.status == "AT_RISK":
        return "admin"
    return "team"


_STAGE_LABELS = {
    "AWAITING_INFO": "Waiting for details from the requester",
    "AWAITING_APPROVAL": "Waiting for approval",
    "DISPATCHED": "With the team",
    "IN_PROGRESS": "Team is working on it",
    "BLOCKED": "Team is blocked",
    "RESOLVED": "Done - waiting for requester to confirm",
    "COMPLETED": "Done",
    "CLOSED": "Closed",
    "CLOSED_NO_REPLY": "Closed - no reply from requester",
    "REJECTED": "Not approved",
    "CANCELLED": "Cancelled",
}


def _request_summary(session: Session, outcome: Outcome) -> dict:
    """Type-neutral header for the detail page: what, who owns it, where it stands, when it's due."""
    from app.models.company import ServiceTicket

    facts = outcome.facts or {}
    stage = str(facts.get("agent_stage") or facts.get("orchestration_stage") or outcome.status or "").upper()
    ticket = session.exec(select(ServiceTicket).where(ServiceTicket.outcome_id == outcome.outcome_id)).first()
    details = facts.get("details") if isinstance(facts.get("details"), dict) else {}
    return {
        "type_label": type_label(outcome),
        "department": department_of(outcome),
        "waiting_on": waiting_on(outcome),
        "stage": stage,
        "stage_label": _STAGE_LABELS.get(stage, stage.replace("_", " ").capitalize()),
        "priority": outcome.priority or "MEDIUM",
        "priority_reason": facts.get("priority_reason"),
        "due_at": outcome.due_at,
        "past_due": bool(outcome.due_at and outcome.due_at < utcnow() and outcome.status not in {"CLOSED", "RESOLVED", "CANCELLED"}),
        "details": details,
        "missing": facts.get("missing") or facts.get("checklist_missing") or [],
        "teams": facts.get("team_groups") or [],
        "tasks": facts.get("tasks") or [],
        "notes": {k: facts.get(k) for k in ("progress_note", "blocked_reason", "resolution_note", "reopen_reason", "decision_reason")
                  if facts.get(k)},
        "reopen_count": facts.get("reopen_count") or 0,
        "is_service_request": outcome.template_code == "SERVICE_REQUEST",
        "decision_class": facts.get("decision_class"),
        "decision_class_label": DECISION_CLASSES.get(facts.get("decision_class") or ""),
        "desired_outcome": facts.get("desired_outcome"),
        "knowledge_gap": bool(facts.get("knowledge_gap")),
        "evidence_status": facts.get("evidence_status"),
        "evidence": [
            {"type": e.evidence_type, "note": e.description, "files": e.record_ref,
             "by": (e.metadata_json or {}).get("by"), "at": e.created_at}
            for e in session.exec(select(Evidence).where(Evidence.outcome_id == outcome.outcome_id)).all()
        ],
        "closure_type": facts.get("closure_type"),
        "closure_label": CLOSURE_LABELS.get(facts.get("closure_type") or ""),
        "verified": facts.get("verified"),
        "corrections": facts.get("corrections") or [],
        "ai_reason": (facts.get("ai_plan") or {}).get("reason_summary"),
        "ai_confidence": (facts.get("ai_plan") or {}).get("confidence"),
        "ticket": {
            "status": ticket.status,
            "assignee": ticket.assignee_email,
            "location": ticket.location,
            "sla_due_at": ticket.sla_due_at,
        } if ticket else None,
    }


def _automation_kpis(session: Session, tenant_id: str) -> dict:
    from app.agent.learning import automation_kpis
    from app.core.config import get_settings

    return {**automation_kpis(session, tenant_id), "ai_emergency_stop": bool(get_settings().ai_emergency_stop)}


def _wait_kpis(session: Session, tenant_id: str) -> dict:
    """Counts across every request type (JSON facts are read in app so it works on SQLite and Postgres)."""
    rows = session.exec(
        select(Outcome).where(
            Outcome.tenant_id == tenant_id,
            Outcome.status.in_(list(OPEN_OUTCOME_STATUSES) + ["RESOLVED"]),  # type: ignore
        )
    ).all()
    now = utcnow()
    awaiting_requirements = no_resource = past_sla = urgent_open = 0
    by_type: dict[str, int] = {}
    by_department: dict[str, int] = {}
    for outcome in rows:
        facts = outcome.facts or {}
        if outcome.status == "RESOLVED":
            continue
        by_type[type_label(outcome)] = by_type.get(type_label(outcome), 0) + 1
        dept = department_of(outcome)
        by_department[dept] = by_department.get(dept, 0) + 1
        if outcome.priority == "URGENT":
            urgent_open += 1
        if outcome.due_at and outcome.due_at < now:
            past_sla += 1
        stage = str(facts.get("agent_stage") or facts.get("orchestration_stage") or "").upper()
        if outcome.template_code == "MEETING_ROOM":
            if facts.get("pending_confirmation") and facts.get("proposed_room") and not facts.get("booked_room"):
                continue
            if stage == "AWAITING_REQUIREMENTS" or (
                facts.get("checklist_missing") and not facts.get("booked_room") and not facts.get("proposed_room")
            ):
                awaiting_requirements += 1
            elif stage == "NO_RESOURCE":
                no_resource += 1
        elif stage == "AWAITING_INFO":
            awaiting_requirements += 1
    resolved_24h = session.exec(
        select(func.count()).select_from(Outcome).where(
            Outcome.tenant_id == tenant_id,
            Outcome.status.in_(["RESOLVED", "CLOSED", "VERIFIED"]),  # type: ignore
            Outcome.updated_at >= now - timedelta(hours=24),
        )
    ).one()
    return {
        "awaiting_requirements": awaiting_requirements,
        "no_resource": no_resource,
        "past_sla": past_sla,
        "urgent_open": urgent_open,
        "resolved_24h": resolved_24h,
        "open_by_type": sorted(({"label": k, "count": v} for k, v in by_type.items()), key=lambda r: -r["count"]),
        "open_by_department": sorted(({"label": k, "count": v} for k, v in by_department.items()), key=lambda r: -r["count"]),
    }


@router.get("/outcomes")
def list_outcomes(
    session: SessionDep,
    tenant_id: TenantDep,
    _user: UserDep,
    status: str | None = None,
    limit: int = 100,
    type: str | None = None,
    department: str | None = None,
):
    stmt = select(Outcome).where(Outcome.tenant_id == tenant_id).order_by(Outcome.created_at.desc())  # type: ignore
    if status:
        stmt = stmt.where(Outcome.status == status)
    out = []
    for o in session.exec(stmt.limit(limit if not (type or department) else max(limit, 500))).all():
        row = {**o.model_dump(), "type_label": type_label(o), "department": department_of(o), "waiting_on": waiting_on(o)}
        if type and row["type_label"] != type:
            continue
        if department and row["department"] != department:
            continue
        out.append(row)
    return out[:limit]


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
    from app.domain.meeting import build_field_contract

    facts = dict(outcome.facts or {})
    field_contract = (
        None if outcome.template_code == "SERVICE_REQUEST"
        else facts.get("field_contract") or build_field_contract(facts)
    )
    return {
        "request": _request_summary(session, outcome),
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
        "field_contract": field_contract,
    }


@router.post("/outcomes/{outcome_id}/close")
def close_outcome(outcome_id: str, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    if outcome.template_code == "SERVICE_REQUEST":
        from app.agent.desk import AdminDesk
        from app.services.approval_actions import default_comms

        desk = AdminDesk(session, tenant_id, default_comms(session, tenant_id))
        facts = outcome.facts or {}
        proven = facts.get("agent_stage") == "RESOLVED" and facts.get("evidence_status") in {"provided", "admin_confirmed", "not_required"}
        desk._close(outcome, f"Closed from the dashboard by {user.email}",
                    closure="verified_evidence" if proven else "administrative")
        session.commit()
        return outcome
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
    """Force a live clarification email — asks only remaining gaps."""
    from app.connectors.factory import get_email_provider
    from app.services.communication import CommunicationService, resolve_requester_name
    from app.services.meeting_room import (
        default_meeting_room_questions,
        meeting_room_gaps,
        requirement_email_sections,
    )

    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    conversation = session.get(Conversation, outcome.conversation_id) if outcome.conversation_id else None
    if not conversation:
        raise HTTPException(400, "Outcome has no conversation")

    facts = dict(outcome.facts or {})
    questions = [g["question"] for g in meeting_room_gaps(facts) if g.get("question")]
    if not questions:
        for item in conversation.missing_information or []:
            if isinstance(item, dict) and item.get("question"):
                questions.append(item["question"])
    if not questions:
        questions = default_meeting_room_questions(facts)
    understood, unconfirmed = requirement_email_sections(facts)

    email = get_email_provider(session, tenant_id)
    sender = email if email.is_connected() else None
    if not sender or not getattr(sender, "can_send", sender.is_connected)():
        raise HTTPException(
            400,
            "Outbound email is not configured. Set CLOUDMAILIN_SMTP_URL and CLOUDMAILIN_FROM_EMAIL on the server.",
        )

    import time

    name = resolve_requester_name(session, outcome=outcome, conversation=conversation)
    msg = CommunicationService(session, tenant_id, email_sender=sender).send_clarification(
        conversation=conversation,
        questions=questions,
        case_reference=outcome.case_reference,
        understood=understood or None,
        unconfirmed=unconfirmed or None,
        force_send_key=f"resend:{int(time.time())}",
        first_contact=False,
        greeting_name=name,
    )
    session.commit()
    suppressed = bool(getattr(msg, "_suppressed", False)) if msg else False
    return {
        "ok": True,
        "message_id": msg.message_id if msg else None,
        "provider_message_id": msg.provider_message_id if msg else None,
        "delivered": bool(msg and msg.provider_message_id) and not suppressed,
        "suppressed": suppressed,
        "suppress_reason": getattr(msg, "_suppress_reason", None) if msg else None,
        "questions": questions,
    }


@router.post("/outcomes/{outcome_id}/override-facts")
def override_facts(
    outcome_id: str,
    payload: OverrideFactsRequest,
    session: SessionDep,
    tenant_id: TenantDep,
    user: UserDep,
):
    """Operator playbook: set/clear facts with user_confirmed provenance."""
    from app.audit.service import AuditService
    from app.connectors.factory import get_email_provider
    from app.core.enums import AuditAction
    from app.engine.outcome_reducer import apply_operator_override
    from app.engine.scenarios import ScenarioOrchestrator
    from app.services.communication import CommunicationService
    from sqlalchemy.orm.attributes import flag_modified

    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    if not payload.set and not payload.unset:
        raise HTTPException(400, "Provide set and/or unset fields")

    before = dict(outcome.facts or {})
    merged = apply_operator_override(
        before,
        payload.set or {},
        unset=payload.unset or None,
        actor=user.email,
    )
    if payload.note:
        notes = list(merged.get("operator_notes") or [])
        notes.append({"at": utcnow().isoformat(), "actor": user.email, "note": payload.note})
        merged["operator_notes"] = notes[-20:]
    outcome.facts = merged
    session.add(outcome)
    flag_modified(outcome, "facts")

    conversation = session.get(Conversation, outcome.conversation_id) if outcome.conversation_id else None
    if conversation:
        conversation.facts = {**(conversation.facts or {}), **merged}
        contract_missing = (merged.get("field_contract") or {}).get("missing") or []
        conversation.missing_information = [
            {"field": m.get("field"), "question": m.get("question"), "blocking": True}
            for m in contract_missing
        ]
        session.add(conversation)

    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=AuditAction.HUMAN_OVERRIDE,
        entity_type="Outcome",
        entity_id=outcome.outcome_id,
        before={"facts_keys": list(before.keys())},
        after={
            "set": payload.set,
            "unset": payload.unset,
            "note": payload.note,
            "checklist_missing": merged.get("checklist_missing"),
            "stage": merged.get("orchestration_stage"),
        },
        correlation_id=outcome.outcome_id,
    )

    if payload.re_orchestrate and outcome.template_code == "MEETING_ROOM":
        email = get_email_provider(session, tenant_id)
        sender = email if email.is_connected() else None
        ScenarioOrchestrator(
            session, tenant_id, CommunicationService(session, tenant_id, email_sender=sender)
        )._scenario_meeting_room(outcome, merged, None)
        session.refresh(outcome)

    session.commit()
    return {
        "ok": True,
        "outcome_id": outcome.outcome_id,
        "facts": outcome.facts,
        "field_contract": (outcome.facts or {}).get("field_contract"),
        "stage": (outcome.facts or {}).get("orchestration_stage"),
    }


@router.post("/outcomes/{outcome_id}/reopen")
def reopen_outcome(
    outcome_id: str,
    payload: ReopenOutcomeRequest,
    session: SessionDep,
    tenant_id: TenantDep,
    user: UserDep,
):
    """Operator playbook: reopen a closed / verified meeting outcome for correction."""
    from app.audit.service import AuditService
    from app.core.enums import AuditAction, OutcomeStatus
    from app.domain.meeting import MeetingStage, attach_field_contract
    from sqlalchemy.orm.attributes import flag_modified

    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    if outcome.template_code == "SERVICE_REQUEST":
        from app.agent.desk import AdminDesk
        from app.services.approval_actions import default_comms

        desk = AdminDesk(session, tenant_id, default_comms(session, tenant_id))
        desk.reopen(outcome, getattr(payload, "reason", None) or "Reopened from the dashboard", actor=user.email)
        session.commit()
        return outcome

    before_status = outcome.status
    facts = dict(outcome.facts or {})
    facts["employee_satisfied"] = False
    if (facts.get("operational_status") or "").upper() == "CLOSED":
        facts["operational_status"] = "ACTIVE"
    # Drop closed stage so search/await can resume
    if facts.get("orchestration_stage") in {
        MeetingStage.CLOSED.value,
        MeetingStage.MONITORING.value,
    }:
        if facts.get("booked_room"):
            facts["orchestration_stage"] = MeetingStage.MONITORING.value
        elif facts.get("pending_confirmation") and facts.get("proposed_room"):
            facts["orchestration_stage"] = MeetingStage.PROPOSED.value
        else:
            facts["orchestration_stage"] = MeetingStage.AWAITING_REQUIREMENTS.value
    facts["reopened"] = {
        "at": utcnow().isoformat(),
        "actor": user.email,
        "reason": payload.reason,
        "previous_status": before_status,
    }
    facts = attach_field_contract(facts)
    outcome.facts = facts
    outcome.status = OutcomeStatus.ACTIVE.value
    outcome.closed_at = None
    outcome.verified_at = None
    session.add(outcome)
    flag_modified(outcome, "facts")

    AuditService(session).record(
        tenant_id=tenant_id,
        actor=user.email,
        action=AuditAction.OUTCOME_REOPENED,
        entity_type="Outcome",
        entity_id=outcome.outcome_id,
        before={"status": before_status},
        after={"status": outcome.status, "reason": payload.reason, "stage": facts.get("orchestration_stage")},
        correlation_id=outcome.outcome_id,
    )
    session.commit()
    return {
        "ok": True,
        "outcome_id": outcome.outcome_id,
        "status": outcome.status,
        "stage": facts.get("orchestration_stage"),
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
    from app.services.approval_actions import apply_decision

    approval = session.get(Approval, approval_id)
    if not approval or approval.tenant_id != tenant_id:
        raise HTTPException(404, "Approval not found")
    if payload.decision not in {"APPROVED", "REJECTED"}:
        approval.decision = payload.decision
        approval.reason = payload.reason
        approval.decided_at = utcnow()
        session.add(approval)
        session.commit()
        return approval
    if approval.decision != "PENDING":
        raise HTTPException(409, f"Approval already {approval.decision.lower()}")
    apply_decision(
        session,
        tenant_id,
        approval,
        approved=payload.decision == "APPROVED",
        actor=user.email,
        note=payload.reason or "",
        via="dashboard",
        approver_person_id=user.person_id,
    )
    session.commit()
    return approval


@router.post("/outcomes/{outcome_id}/close-financial")
def close_financial(outcome_id: str, session: SessionDep, tenant_id: TenantDep, user: UserDep):
    outcome = session.get(Outcome, outcome_id)
    if not outcome or outcome.tenant_id != tenant_id:
        raise HTTPException(404, "Outcome not found")
    try:
        updated = OutcomeEngine(session, tenant_id).close_financial(outcome, actor=user.email)
        session.commit()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return updated


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
