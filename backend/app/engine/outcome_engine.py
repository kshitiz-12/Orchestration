from datetime import timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.audit.service import AuditService
from app.core.enums import (
    AuditAction,
    ExceptionSeverity,
    OutcomeStatus,
    RequirementStatus,
    TaskStatus,
)
from app.core.logging import get_logger
from app.models.intake import Conversation
from app.models.org import OutcomeTemplate, Person, utcnow
from app.models.outcome import (
    Approval,
    ExceptionRecord,
    Outcome,
    Requirement,
    Task,
    TaskDependency,
    VendorIssue,
)
from app.models.org import new_id

logger = get_logger(__name__)


class OutcomeEngine:
    """Core orchestration: Event → Outcome → Requirements → Tasks → Evidence → Closure.

    Independent of Gmail and Gemini.
    """

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.audit = AuditService(session)

    def get_template(self, code: str) -> Optional[OutcomeTemplate]:
        return self.session.exec(
            select(OutcomeTemplate).where(
                OutcomeTemplate.tenant_id == self.tenant_id,
                OutcomeTemplate.code == code,
                OutcomeTemplate.is_active == True,  # noqa: E712
            )
        ).first()

    def next_case_reference(self, prefix: str) -> str:
        year = utcnow().year
        like = f"{prefix}-{year}-%"
        existing = self.session.exec(
            select(Outcome).where(Outcome.case_reference.like(like))  # type: ignore[attr-defined]
        ).all()
        seq = len(existing) + 1
        return f"{prefix}-{year}-{seq:04d}"

    def find_person_by_email(self, email: str) -> Optional[Person]:
        return self.session.exec(select(Person).where(Person.email == email.lower())).first()

    def find_person_by_role(self, role: str) -> Optional[Person]:
        return self.session.exec(
            select(Person).where(
                Person.tenant_id == self.tenant_id,
                Person.role == role,
                Person.is_active == True,  # noqa: E712
            )
        ).first()

    def create_outcome_from_template(
        self,
        *,
        template_code: str,
        title: str,
        summary: str,
        requester_email: str,
        conversation_id: Optional[str],
        business_event_id: Optional[str],
        facts: dict[str, Any],
        priority: str = "MEDIUM",
        actor: str = "system",
    ) -> Outcome:
        template = self.get_template(template_code)
        if not template:
            raise ValueError(f"Unknown outcome template: {template_code}")

        # Thread linking: never create a second outcome for the same conversation
        if conversation_id:
            existing = self.session.exec(
                select(Outcome).where(
                    Outcome.conversation_id == conversation_id,
                    Outcome.status.notin_(  # type: ignore[attr-defined]
                        [OutcomeStatus.CLOSED.value, OutcomeStatus.CANCELLED.value]
                    ),
                )
            ).first()
            if existing:
                existing.facts = {**(existing.facts or {}), **facts}
                existing.summary = summary or existing.summary
                existing.updated_at = utcnow()
                self.session.add(existing)
                self.audit.record(
                    tenant_id=self.tenant_id,
                    actor=actor,
                    action=AuditAction.OUTCOME_UPDATED,
                    entity_type="Outcome",
                    entity_id=existing.outcome_id,
                    after={"facts": existing.facts},
                    correlation_id=business_event_id,
                )
                self._recompute_readiness(existing)
                return existing

        requester = self.find_person_by_email(requester_email)
        case_ref = self.next_case_reference(template.case_prefix)
        outcome = Outcome(
            tenant_id=self.tenant_id,
            case_reference=case_ref,
            template_id=template.template_id,
            template_code=template.code,
            category=template.category,
            title=title,
            summary=summary,
            requester_email=requester_email,
            requester_person_id=requester.person_id if requester else None,
            owner_person_id=(self.find_person_by_role(template.tasks[0].get("owner_role", "ADMIN")).person_id
                             if template.tasks else None),
            status=OutcomeStatus.ACTIVE.value,
            priority=priority,
            facts=facts,
            business_event_id=business_event_id,
            conversation_id=conversation_id,
            due_at=utcnow() + timedelta(hours=72),
        )
        self.session.add(outcome)
        self.session.flush()

        # Transactional creation of requirements + tasks
        req_by_code: dict[str, Requirement] = {}
        for req_def in template.requirements:
            req = Requirement(
                tenant_id=self.tenant_id,
                outcome_id=outcome.outcome_id,
                code=req_def["code"],
                title=req_def["title"],
                applicability=req_def.get("applicability", "REQUIRED"),
                status=RequirementStatus.ACTION_PENDING.value,
                is_mandatory=req_def.get("is_mandatory", True),
                is_blocker=req_def.get("is_blocker", False),
                evidence_rule=req_def.get("evidence_rule"),
                evidence_required=req_def.get("evidence_required", False),
            )
            self.session.add(req)
            self.session.flush()
            req_by_code[req.code] = req

        task_by_code: dict[str, Task] = {}
        for task_def in template.tasks:
            owner = self.find_person_by_role(task_def.get("owner_role", "ADMIN"))
            req_code = task_def.get("requirement_code")
            task = Task(
                tenant_id=self.tenant_id,
                outcome_id=outcome.outcome_id,
                requirement_id=req_by_code[req_code].requirement_id if req_code in req_by_code else None,
                code=task_def["code"],
                title=task_def["title"],
                description=task_def.get("description"),
                owner_role=task_def.get("owner_role"),
                owner_person_id=owner.person_id if owner else None,
                status=TaskStatus.ASSIGNED.value if owner else TaskStatus.NOT_STARTED.value,
                due_at=utcnow() + timedelta(hours=task_def.get("sla_hours", 48)),
                sla_hours=task_def.get("sla_hours", 48),
                task_group=task_def.get("task_group"),
                is_mandatory=task_def.get("is_mandatory", True),
                evidence_required=task_def.get("evidence_required", False),
                depends_on_task_codes=task_def.get("depends_on", []),
            )
            self.session.add(task)
            self.session.flush()
            task_by_code[task.code] = task
            self.audit.record(
                tenant_id=self.tenant_id,
                actor=actor,
                action=AuditAction.TASK_CREATED,
                entity_type="Task",
                entity_id=task.task_id,
                after={"code": task.code, "title": task.title},
                correlation_id=outcome.outcome_id,
            )

        for task in task_by_code.values():
            for dep_code in task.depends_on_task_codes or []:
                if dep_code in task_by_code:
                    self.session.add(
                        TaskDependency(
                            task_id=task.task_id,
                            depends_on_task_id=task_by_code[dep_code].task_id,
                        )
                    )

        self.audit.record(
            tenant_id=self.tenant_id,
            actor=actor,
            action=AuditAction.OUTCOME_CREATED,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"case_reference": case_ref, "template": template_code},
            correlation_id=business_event_id,
        )

        if conversation_id:
            conv = self.session.get(Conversation, conversation_id)
            if conv:
                conv.current_outcome_id = outcome.outcome_id
                conv.status = "ACTIVE"
                self.session.add(conv)

        self._recompute_readiness(outcome)
        self.session.flush()
        return outcome

    def apply_blocker(self, outcome: Outcome, blocker_code: str, blocked_task_codes: list[str], reason: str) -> None:
        """Block ONLY dependent tasks; independent tasks continue."""
        tasks = self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
        blockers = list(outcome.blockers or [])
        blockers.append({"code": blocker_code, "reason": reason, "tasks": blocked_task_codes})
        outcome.blockers = blockers
        for task in tasks:
            if task.code in blocked_task_codes:
                task.is_blocked = True
                task.status = TaskStatus.BLOCKED.value
                task.blocked_by = list(set((task.blocked_by or []) + [blocker_code]))
                self.session.add(task)
                self.audit.record(
                    tenant_id=self.tenant_id,
                    actor="system",
                    action=AuditAction.TASK_BLOCKED,
                    entity_type="Task",
                    entity_id=task.task_id,
                    after={"blocker": blocker_code, "reason": reason},
                    correlation_id=outcome.outcome_id,
                )
        # If any mandatory task is blocked, outcome may be BLOCKED or PARTIALLY_READY
        independent_active = any(
            not t.is_blocked and t.status not in {TaskStatus.CLOSED.value, TaskStatus.CANCELLED.value}
            for t in tasks
        )
        outcome.status = (
            OutcomeStatus.PARTIALLY_READY.value if independent_active else OutcomeStatus.BLOCKED.value
        )
        self.session.add(outcome)
        self._recompute_readiness(outcome)

    def create_exception(
        self,
        *,
        outcome: Outcome,
        exception_type: str,
        title: str,
        description: str,
        severity: str = ExceptionSeverity.HIGH.value,
        options: Optional[list] = None,
        owner_role: str = "WORKPLACE",
        task_id: Optional[str] = None,
    ) -> ExceptionRecord:
        owner = self.find_person_by_role(owner_role)
        exc = ExceptionRecord(
            tenant_id=self.tenant_id,
            outcome_id=outcome.outcome_id,
            task_id=task_id,
            exception_type=exception_type,
            severity=severity,
            title=title,
            description=description,
            owner_role=owner_role,
            owner_person_id=owner.person_id if owner else None,
            options=options or [],
        )
        self.session.add(exc)
        self.session.flush()
        self.audit.record(
            tenant_id=self.tenant_id,
            actor="system",
            action=AuditAction.EXCEPTION_CREATED,
            entity_type="Exception",
            entity_id=exc.exception_id,
            after={"type": exception_type, "title": title},
            correlation_id=outcome.outcome_id,
        )
        return exc

    def request_approval(
        self,
        *,
        outcome: Outcome,
        approval_type: str,
        approver_role: str,
        payload: Optional[dict] = None,
        task_id: Optional[str] = None,
    ) -> Approval:
        approver = self.find_person_by_role(approver_role)
        approval = Approval(
            tenant_id=self.tenant_id,
            outcome_id=outcome.outcome_id,
            task_id=task_id,
            approval_type=approval_type,
            approver_role=approver_role,
            approver_person_id=approver.person_id if approver else None,
            payload=payload or {},
        )
        self.session.add(approval)
        self.session.flush()
        self.audit.record(
            tenant_id=self.tenant_id,
            actor="system",
            action=AuditAction.APPROVAL_REQUESTED,
            entity_type="Approval",
            entity_id=approval.approval_id,
            after={"type": approval_type},
            correlation_id=outcome.outcome_id,
        )
        return approval

    def add_vendor_issues(self, outcome: Outcome, issues: list[dict]) -> list[VendorIssue]:
        workstream_map = {
            "QUALITY": "Quality",
            "SUBSTITUTION": "Procurement",
            "AUTHENTICITY": "Quality",
            "EXPIRY": "Safety",
            "QUANTITY": "Procurement",
            "BILLING": "Finance",
            "PERFORMANCE": "Vendor Response",
            "SUPPLY": "Supply Continuity",
        }
        created = []
        for issue in issues:
            itype = issue.get("issue_type", "QUALITY")
            row = VendorIssue(
                tenant_id=self.tenant_id,
                outcome_id=outcome.outcome_id,
                issue_type=itype,
                workstream=workstream_map.get(itype, "Quality"),
                title=issue.get("summary", itype),
                description=issue.get("summary"),
                severity=issue.get("severity", "MEDIUM"),
                allegation_status="UNVERIFIED",
            )
            self.session.add(row)
            created.append(row)
        self.session.flush()
        return created

    def update_task_status(
        self,
        task: Task,
        status: str,
        *,
        actor: str,
        resolution: Optional[str] = None,
    ) -> Task:
        before = {"status": task.status}
        if status in {TaskStatus.CLOSED.value, TaskStatus.VERIFIED.value} and task.evidence_required:
            from app.models.outcome import Evidence

            verified = self.session.exec(
                select(Evidence).where(
                    Evidence.task_id == task.task_id,
                    Evidence.status == "VERIFIED",
                )
            ).first()
            if not verified:
                # Prevent verified/closed without evidence; park as pending evidence
                status = TaskStatus.COMPLETED_PENDING_EVIDENCE.value

        task.status = status
        if resolution:
            task.resolution = resolution
        if status in {TaskStatus.COMPLETED_PENDING_EVIDENCE.value, TaskStatus.VERIFIED.value, TaskStatus.CLOSED.value}:
            task.completed_at = utcnow()
        if status == TaskStatus.VERIFIED.value:
            task.verified_at = utcnow()
        task.updated_at = utcnow()
        self.session.add(task)
        self.audit.record(
            tenant_id=self.tenant_id,
            actor=actor,
            action=AuditAction.TASK_STATUS_CHANGED,
            entity_type="Task",
            entity_id=task.task_id,
            before=before,
            after={"status": status, "resolution": resolution},
            correlation_id=task.outcome_id,
        )
        outcome = self.session.get(Outcome, task.outcome_id)
        if outcome:
            self._recompute_readiness(outcome)
            self._sync_requirements_from_tasks(outcome)
        return task

    def _sync_requirements_from_tasks(self, outcome: Outcome) -> None:
        reqs = self.session.exec(select(Requirement).where(Requirement.outcome_id == outcome.outcome_id)).all()
        tasks = self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
        by_req = {}
        for t in tasks:
            if t.requirement_id:
                by_req.setdefault(t.requirement_id, []).append(t)
        for req in reqs:
            related = by_req.get(req.requirement_id, [])
            if not related:
                continue
            if all(t.status in {TaskStatus.VERIFIED.value, TaskStatus.CLOSED.value} for t in related):
                if req.evidence_required:
                    from app.models.outcome import Evidence

                    ev = self.session.exec(
                        select(Evidence).where(
                            Evidence.requirement_id == req.requirement_id,
                            Evidence.status == "VERIFIED",
                        )
                    ).first()
                    req.status = RequirementStatus.COMPLETED.value if ev else RequirementStatus.ACTION_PENDING.value
                else:
                    req.status = RequirementStatus.COMPLETED.value
            elif any(t.status == TaskStatus.APPROVAL_PENDING.value for t in related):
                req.status = RequirementStatus.APPROVAL_PENDING.value
            elif any(t.is_blocked for t in related):
                req.status = RequirementStatus.EXCEPTION.value
            self.session.add(req)

    def _recompute_readiness(self, outcome: Outcome) -> None:
        reqs = self.session.exec(
            select(Requirement).where(
                Requirement.outcome_id == outcome.outcome_id,
                Requirement.is_mandatory == True,  # noqa: E712
            )
        ).all()
        mandatory = [r for r in reqs if r.applicability != "NOT_APPLICABLE"]
        if not mandatory:
            outcome.readiness_pct = 0.0
        else:
            completed = sum(1 for r in mandatory if r.status == RequirementStatus.COMPLETED.value)
            outcome.readiness_pct = round(100.0 * completed / len(mandatory), 1)

        tasks = self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id)).all()
        # Joining-day vs permanent readiness for onboarding
        if outcome.template_code == "ONBOARDING":
            join_groups = {"HR", "IT", "SECURITY", "MANAGER", "ADMIN_TEMP"}
            perm_groups = {"ADMIN_PERMANENT", "ADMIN"}
            join_tasks = [t for t in tasks if (t.task_group or "") in join_groups or t.code != "SEAT_PERMANENT"]
            perm_tasks = [t for t in tasks if t.code == "SEAT_PERMANENT" or (t.task_group or "") in perm_groups]
            def pct(ts):
                if not ts:
                    return 100.0
                done = sum(1 for t in ts if t.status in {TaskStatus.VERIFIED.value, TaskStatus.CLOSED.value})
                return round(100.0 * done / len(ts), 1)
            outcome.joining_day_readiness_pct = pct(join_tasks)
            outcome.permanent_readiness_pct = pct(perm_tasks)

        overdue_critical = any(
            t.is_blocked and t.due_at and t.due_at < utcnow() and t.is_mandatory for t in tasks
        )
        if overdue_critical and outcome.status not in {
            OutcomeStatus.CLOSED.value,
            OutcomeStatus.CANCELLED.value,
            OutcomeStatus.VERIFIED.value,
        }:
            outcome.status = OutcomeStatus.AT_RISK.value
        self.session.add(outcome)

    def try_close(self, outcome: Outcome, actor: str) -> Outcome:
        reqs = self.session.exec(
            select(Requirement).where(
                Requirement.outcome_id == outcome.outcome_id,
                Requirement.is_mandatory == True,  # noqa: E712
            )
        ).all()
        incomplete = [
            r
            for r in reqs
            if r.applicability != "NOT_APPLICABLE" and r.status != RequirementStatus.COMPLETED.value
        ]
        if incomplete:
            raise ValueError(
                f"Cannot close outcome: {len(incomplete)} mandatory requirements incomplete"
            )
        outcome.status = OutcomeStatus.VERIFIED.value
        outcome.verified_at = utcnow()
        self.session.add(outcome)
        self.audit.record(
            tenant_id=self.tenant_id,
            actor=actor,
            action=AuditAction.OUTCOME_VERIFIED,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"status": outcome.status},
        )
        outcome.status = OutcomeStatus.CLOSED.value
        outcome.closed_at = utcnow()
        self.session.add(outcome)
        self.audit.record(
            tenant_id=self.tenant_id,
            actor=actor,
            action=AuditAction.OUTCOME_CLOSED,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"status": outcome.status},
        )
        return outcome
