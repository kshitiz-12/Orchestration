"""Executes the AI admin's decision: cases, tickets, passes, routing, approvals and replies.

The model proposes; this module decides what actually happens under the risk policy and only
tells the requester what really happened.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.agent.company_seed import is_placeholder
from app.agent.digest import digest_mode
from app.agent.directory import (
    Route,
    catalogue,
    find_department,
    handles_category,
    knowledge_text,
    route_for,
    route_for_case,
)
from app.agent.learning import add_correction, similar_verified
from app.agent.learning import record_closure as save_learning_record
from app.agent.playbooks import (
    LEGACY_CATEGORIES,
    RiskVerdict,
    assess_risk,
    case_prefix,
    decision_class,
    evidence_hint,
    fill_required,
    has_playbook,
    label_value,
    label_for,
    missing_questions,
    normalize_category,
    playbook_for,
    split_tasks,
    tasks_from_text,
)
from app.agent.priority import infer_priority, sla_hours_for
from app.ai.admin_agent import (
    AdminAgent,
    AgentDecision,
    AgentIntent,
    automated_reason,
    build_agent_payload,
    build_trail,
    case_state,
    open_cases,
    requester_profile,
)
from app.audit.service import AuditService
from app.core.config import get_settings
from app.core.enums import AuditAction, CommunicationType, OutcomeStatus
from app.core.logging import get_logger
from app.engine.outcome_engine import OutcomeEngine
from app.models.company import ServiceTicket, VisitorPass
from app.models.intake import Conversation, RawEmailEvent
from app.models.org import Person, Resource, Vendor, utcnow
from app.models.outcome import Approval, Evidence, Outcome
from app.services.communication import CommunicationService, resolve_requester_name
from app.services.email_utils import strip_for_ai

logger = get_logger(__name__)

SERVICE_TEMPLATE = "SERVICE_REQUEST"
_CLOSED = {OutcomeStatus.CLOSED.value, OutcomeStatus.CANCELLED.value, OutcomeStatus.ADMINISTRATIVELY_CLOSED.value}
_CASE_REF = re.compile(r"\b([A-Z]{2,5}-\d{4}-\d{3,})\b")
_VENDOR_HINTS = {
    "travel": ("transport", "travel", "cab"),
    "supplies": ("stationery", "supplies"),
    "maintenance": ("facility",),
    "hvac": ("facility", "hvac"),
    "electrical": ("facility", "electrical"),
    "plumbing": ("facility", "plumbing"),
    "catering": ("catering", "food"),
}


_EMPLOYEE_PARKING_RE = re.compile(
    r"\b(?:permanent|monthly|regular|daily|own\s+car|my\s+car|new\s+joinee|new\s+joiner|employee\s+parking"
    r"|parking\s+sticker|long[\s-]term)\b",
    re.I,
)
# The model's own draft admits it does not know - treat the question as unverified even if it forgot the flag.
_UNVERIFIED_ANSWER_RE = re.compile(
    r"\b(?:check\s+with\s+(?:the\s+)?(?:team|admin|hr|facilities)|get\s+back\s+to\s+you|not\s+sure|"
    r"don'?t\s+have\s+(?:that|this|the)\s+(?:information|details)|could\s*n[o']?t\s+verify|unable\s+to\s+(?:confirm|verify))\b",
    re.I,
)
_FORWARD_CLAIM_RE = re.compile(
    r"\b(?:forwarded|passed\s+(?:it\s+)?(?:on|along)|assigned|sent\s+(?:it\s+)?to|handed\s+over|arranged|allotted|allocated)\b",
    re.I,
)


_NOT_FIXED_RE = re.compile(
    r"\b(?:not\s+(?:yet\s+)?(?:fixed|working|resolved|done|sorted|solved|repaired|cleaned|delivered|received)|"
    r"still\s+(?:not|isn'?t|doesn'?t|broken|leaking|the\s+same|an?\s+issue|a\s+problem|pending|happening)|"
    r"(?:isn'?t|doesn'?t|didn'?t|hasn'?t|wasn'?t)\s+(?:fixed|working|work|resolved|done|sorted|solved|arrived)|"
    r"(?:same|again)\s+(?:issue|problem)|happening\s+again|broke\s+again|please\s+reopen|reopen)\b",
    re.I,
)
_SATISFIED_RE = re.compile(
    r"^\s*(?:thanks?|thank\s+you|thx|great|perfect|awesome|working\s+(?:now|fine)|it\s+works|all\s+good|"
    r"sorted|resolved|confirmed|ok(?:ay)?\s+thanks?)\b",
    re.I,
)


_TEAM_ISSUE_RE = re.compile(
    r"^\s*(?:issue|problem|blocked|on\s+hold|can'?t|cannot|unable\s+to|not\s+possible|"
    r"need(?:s|ed)?\s+(?:a\s+|an\s+)?(?:approval|part|spare|budget|vendor|quote|access)|waiting\s+(?:for|on))\b",
    re.I,
)
_TEAM_PROGRESS_RE = re.compile(
    r"^\s*(?:on\s+it|in\s+progress|working\s+on\s+it|started|noted|acknowledged|ack\b|received|"
    r"(?:technician|electrician|plumber|engineer|person|someone|team)\s+(?:is\s+)?(?:assigned|on\s+the\s+way|coming|sent)|"
    r"will\s+(?:be\s+)?(?:done|fix(?:ed)?|complete[d]?|deliver(?:ed)?|arrange[d]?|sort(?:ed)?|do\s+it|check)|"
    r"eta\b|by\s+(?:today|tomorrow|eod|\d)|in\s+\d+\s*(?:min|mins|minutes|hours?|hrs?))",
    re.I,
)
_DONE_WORDS = (r"(?:done|fixed|resolved|complete[d]?|finished|closed|sorted|repaired|replaced|delivered|arranged|"
               r"cleaned|installed|issued|ready|allocated|provided|configured|created|activated|handed\s+over|"
               r"set\s*up|prepared|booked|organi[sz]ed|shared|given)")
_ALL_DONE_RE = re.compile(r"^\s*(?:all|everything)\s+(?:is\s+|are\s+)?(?:done|complete[d]?|finished)\b", re.I)


def _is_done_reply(low: str) -> bool:
    if re.search(rf"\b(?:will|to|not|n'?t|yet\s+to|tomorrow|later|soon|almost|nearly)\s+(?:be\s+)?(?:get\s+)?"
                 rf"{_DONE_WORDS}\b", low):
        return False
    return bool(re.search(rf"\b{_DONE_WORDS}\b", low))


def is_service_case(outcome: Optional[Outcome]) -> bool:
    return bool(outcome) and outcome.template_code == SERVICE_TEMPLATE


_PERSON_KEYS = ("employee_name", "joiner_name", "name", "full_name", "new_joiner", "joinee_name", "candidate_name",
                "employee", "on_behalf_of", "visitor_names", "guest_name")
_ID_KEYS = ("employee_id", "emp_id", "staff_id")


def _norm_values(value: Any) -> set[str]:
    items = value if isinstance(value, (list, tuple)) else [value]
    return {re.sub(r"\s+", " ", str(v)).strip().lower() for v in items if str(v or "").strip()}


def _identity(details: dict, text: str = "") -> tuple[set[str], set[str]]:
    people: set[str] = set()
    ids: set[str] = set()
    for k in _PERSON_KEYS:
        people |= _norm_values(details.get(k)) if details.get(k) else set()
    for k in _ID_KEYS:
        ids |= _norm_values(details.get(k)) if details.get(k) else set()
    for k in ("name", "employee_name", "full_name"):
        if v := label_value(text, k):
            people |= _norm_values(v)
    for k in _ID_KEYS:
        if v := label_value(text, k):
            ids |= _norm_values(v)
    return people, ids


def _about_someone_else(intent: AgentIntent, target: Outcome, text: str) -> bool:
    """The new mail names a different person (or employee ID) than the case it was linked to."""
    facts = target.facts or {}
    old_people, old_ids = _identity(
        {**((facts.get("ai_plan") or {}).get("details") or {}), **(facts.get("details") or {})},
        facts.get("raw_request") or "",
    )
    new_people, new_ids = _identity(dict(intent.details or {}), text)
    if new_ids and old_ids and not (new_ids & old_ids):
        return True
    return bool(new_people and old_people and not (new_people & old_people))


def _set_facts(session: Session, outcome: Outcome, **updates: Any) -> dict:
    facts = {**(outcome.facts or {}), **updates}
    outcome.facts = facts
    outcome.updated_at = utcnow()
    session.add(outcome)
    flag_modified(outcome, "facts")
    return facts


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict):
                name = v.get("name") or v.get("visitor_name") or ""
                company = v.get("company") or ""
                out.append(f"{name} ({company})" if company and name else str(name or company))
            elif str(v).strip():
                out.append(str(v).strip())
        return [o for o in out if o]
    return [p.strip() for p in re.split(r",|;|\band\b|\n", str(value)) if p.strip()]


def _details_lines(details: dict) -> list[str]:
    lines = []
    copies = {"visit_date": ("date", "visit_day", "on"), "visit_time": ("time", "arrival_time")}
    for key, value in details.items():
        if value in (None, "", [], {}):
            continue
        if any(details.get(src) == value for src in copies.get(key, ())):
            continue
        shown = ", ".join(_as_list(value)) if isinstance(value, list) else str(value)
        lines.append(f"- {key.replace('_', ' ').capitalize()}: {shown}")
    return lines


_IST = timezone(timedelta(hours=5, minutes=30))
READY_FOR_JOINING = "READY_FOR_JOINING"
# The day-one handover check goes out once the office day has started.
_HANDOVER_CHECK_AT = time(9, 30)


def _ist_now() -> datetime:
    return datetime.now(_IST).replace(tzinfo=None)


def _ist_to_utc(moment: datetime) -> datetime:
    return moment - timedelta(hours=5, minutes=30)


def joining_day(facts: dict) -> Optional[date]:
    if facts.get("joining_on"):
        try:
            return date.fromisoformat(str(facts["joining_on"]))
        except ValueError:
            pass
    d = facts.get("details") or {}
    raw = d.get("joining_date") or d.get("start_date") or d.get("date_of_joining") or d.get("doj") or d.get("date")
    if not raw:
        return None
    from app.services.room_booking import parse_meeting_date

    return parse_meeting_date(raw, today=_ist_now().date())


# Requests for something at a set time: the team's deadline can't be later than that time.
_TIMED_CATEGORIES = {"catering", "cafeteria", "event", "travel", "employee_transport", "guest_house"}


def _needed_by(facts: dict) -> Optional[datetime]:
    """When a timed service must be ready (naive UTC), from the request's date and time."""
    if facts.get("agent_category") not in _TIMED_CATEGORIES:
        return None
    from app.services.room_booking import parse_clock, parse_meeting_date

    d = facts.get("details") or {}
    raw_day = next((d.get(k) for k in ("date", "visit_date", "event_date", "travel_date") if d.get(k)), None)
    raw_time = next((d.get(k) for k in ("time", "visit_time", "start_time", "pickup_time", "event_time") if d.get(k)), None)
    day = parse_meeting_date(raw_day, today=_ist_now().date()) if raw_day else None
    exact = re.fullmatch(r"\s*([01]\d|2[0-3]):([0-5]\d)\s*", str(raw_time or ""))
    clock = time(int(exact.group(1)), int(exact.group(2))) if exact else (parse_clock(raw_time) if raw_time else None)
    if not day or not clock:
        return None
    return _ist_to_utc(datetime.combine(day, clock))


def _joiner(facts: dict) -> str:
    d = facts.get("details") or {}
    return str(d.get("employee_name") or d.get("joiner_name") or d.get("name") or "the new joiner")


def _day_label(day: date) -> str:
    return f"{day.day} {day:%b %Y}"


_SIGNOFF_RE = re.compile(r"^\s*(?:best|kind|warm)?\s*(?:regards|thanks|thank you|cheers|sincerely)\b.*$", re.I)


def _before_signoff(draft: str, block: str) -> str:
    """Put an extra block above the sign-off ("Best regards, / Workplace Team"), not under it."""
    lines = draft.rstrip().split("\n")
    for i in range(len(lines) - 1, max(-1, len(lines) - 5), -1):
        if _SIGNOFF_RE.match(lines[i]):
            head = "\n".join(lines[:i]).rstrip()
            return f"{head}\n\n{block}\n\n" + "\n".join(lines[i:])
    return f"{draft.rstrip()}\n\n{block}"


def _normalize_details(details: dict) -> dict:
    out = dict(details or {})
    for src in ("visitors", "visitor", "guests", "guest_names", "names"):
        if src in out and "visitor_names" not in out:
            out["visitor_names"] = out.pop(src)
    for src in ("vehicle_number", "vehicle", "vehicles", "car_number", "car_no", "car", "vehicle_no",
                "registration_number", "number_plate", "plate", "car_registration"):
        if src in out and "vehicle_numbers" not in out:
            out["vehicle_numbers"] = out.pop(src)
    for src in ("date", "visit_day", "on"):
        if src in out and "visit_date" not in out:
            out["visit_date"] = out[src]
    for src in ("time", "arrival_time"):
        if src in out and "visit_time" not in out:
            out["visit_time"] = out[src]
    return out


class AdminDesk:
    def __init__(self, session: Session, tenant_id: str, comms: CommunicationService, provider: Any = None):
        self.session = session
        self.tenant_id = tenant_id
        self.comms = comms
        self.agent = AdminAgent(provider)
        self.engine = OutcomeEngine(session, tenant_id)
        self.audit = AuditService(session)
        self.settings = get_settings()
        self.handoff_categories: set[str] = set()

    # ------------------------------------------------------------------ entry
    def handle(self, event: RawEmailEvent, conversation: Conversation) -> Optional[dict]:
        """Return a result when the desk handled the mail; None hands it to the existing flows."""
        requester = (event.sender or "").strip().lower()
        auto = automated_reason(requester, event.subject or "", event.headers)
        if auto:
            logger.info("admin_desk_ignored_automated_mail", event_id=event.event_id, reason=auto)
            self.session.commit()
            return {"status": "agent_ignored", "reason": auto, "replied": False}
        current = self._current_case(conversation)
        text = strip_for_ai(event.body_text or event.body_for_ai or "")
        name = resolve_requester_name(self.session, conversation=conversation, email=requester, event=event)
        cases = open_cases(self.session, self.tenant_id, requester)
        payload = build_agent_payload(
            subject=event.subject or "",
            this_message=text,
            trail=build_trail(self.session, conversation, event.event_id),
            cases=[case_state(c) for c in cases],
            current_case=current.case_reference if current else None,
            profile=requester_profile(self.session, requester, name if name not in {"there", "team"} else None),
            knowledge=knowledge_text(self.session, self.tenant_id),
            departments=catalogue(self.session, self.tenant_id),
            attachments=[a.get("filename", "") for a in (event.attachments or [])],
            similar_cases=similar_verified(self.session, self.tenant_id, f"{event.subject or ''}\n{text}"),
        )
        hint = None if self.agent.can_reason else self._legacy_hint(event, current)
        decision = self.agent.decide(payload, heuristic_hint=hint)
        self._record_decision(event, conversation, decision)

        mine, legacy = self._split(decision, current, cases, f"{event.subject or ''}\n{text}")
        self.handoff_categories = {normalize_category(i.category) for i in legacy} if self.agent.can_reason else set()
        if not mine:
            return None

        results = [self._execute(intent, event, conversation, current, cases, decision) for intent in mine]
        results = [r for r in results if r]
        reply = self._reply_text(decision, mine, results, name, split=bool(legacy))
        target = next((r["outcome"] for r in results if r.get("outcome") is not None), None)
        if reply:
            self._send_reply(event, conversation, target, reply, results)
        if legacy:
            logger.info("admin_desk_partial_handoff", event_id=event.event_id, legacy=[i.category for i in legacy])
            return None
        self.session.commit()
        return {
            "status": "agent_handled",
            "intents": [i.type + (f":{normalize_category(i.category)}" if i.type == "new_request" else "") for i in mine],
            "outcome_id": target.outcome_id if target else None,
            "case_reference": target.case_reference if target else None,
            "decision_source": decision.source,
            "replied": bool(reply),
        }

    # ------------------------------------------------------------ routing
    def _current_case(self, conversation: Conversation) -> Optional[Outcome]:
        if not conversation.current_outcome_id:
            return None
        outcome = self.session.get(Outcome, conversation.current_outcome_id)
        return outcome if outcome and outcome.status not in _CLOSED else None

    def _legacy_hint(self, event: RawEmailEvent, current: Optional[Outcome]) -> Optional[str]:
        if current is not None and not is_service_case(current):
            return (current.category or "GENERAL").upper()
        from app.ai.gemini import HeuristicProvider

        try:
            return HeuristicProvider().extract(subject=event.subject or "", body=event.body_text or "").event_type
        except Exception:  # noqa: BLE001
            return None

    def _find_case(self, ref: Optional[str], current: Optional[Outcome], cases: list[Outcome]) -> Optional[Outcome]:
        if ref:
            m = _CASE_REF.search(ref.upper())
            if m:
                found = next((c for c in cases if c.case_reference == m.group(1)), None)
                if found:
                    return found
                return self.session.exec(
                    select(Outcome).where(Outcome.tenant_id == self.tenant_id, Outcome.case_reference == m.group(1))
                ).first()
        return current

    def _status_target(self, intent: AgentIntent, current: Optional[Outcome], cases: list[Outcome]) -> Optional[Outcome]:
        found = self._find_case(intent.case_reference, current, cases)
        if found is None and len(cases) == 1:
            return cases[0]
        return found

    def _split(
        self, decision: AgentDecision, current: Optional[Outcome], cases: list[Outcome], text: str = ""
    ) -> tuple[list[AgentIntent], list[AgentIntent]]:
        mine: list[AgentIntent] = []
        legacy: list[AgentIntent] = []
        for intent in decision.intents:
            cat = normalize_category(intent.category)
            if intent.type == "status":
                target = self._status_target(intent, current, cases)
                (legacy if target is not None and not is_service_case(target) else mine).append(intent)
            elif intent.type in {"small_talk", "question", "empty"}:
                if intent.type in {"small_talk", "empty"} and current is not None and not is_service_case(current):
                    legacy.append(intent)
                else:
                    mine.append(intent)
            elif intent.type == "new_request":
                if cat in LEGACY_CATEGORIES or cat == "legacy":
                    legacy.append(intent)
                else:
                    mine.append(intent)
            else:
                target = self._find_case(intent.case_reference, current, cases)
                if (target is not None and is_service_case(target) and intent.type == "update_case"
                        and current is None and not _CASE_REF.search((text or "").upper())
                        and _about_someone_else(intent, target, text)):
                    # A fresh email (not a reply, no reference) about a different person is a new request,
                    # even when an open case of the same type is waiting for details.
                    intent.type, intent.case_reference = "new_request", None
                    mine.append(intent)
                elif target is not None and is_service_case(target):
                    mine.append(intent)
                elif target is None and intent.type == "update_case" and cat not in LEGACY_CATEGORIES | {"legacy", "general"}:
                    intent.type = "new_request"
                    mine.append(intent)
                else:
                    legacy.append(intent)
        return mine, legacy

    # ------------------------------------------------------------ execution
    def _execute(
        self,
        intent: AgentIntent,
        event: RawEmailEvent,
        conversation: Conversation,
        current: Optional[Outcome],
        cases: list[Outcome],
        decision: AgentDecision,
    ) -> Optional[dict]:
        if intent.type == "question" and (
            not intent.answer_verified or _UNVERIFIED_ANSWER_RE.search(decision.reply_to_requester or "")
        ):
            return self._knowledge_gap(intent, event, conversation, decision, current)
        if intent.type in {"small_talk", "question", "empty"}:
            return {"intent": intent, "status": intent.type}
        if intent.type == "status":
            return {"intent": intent, "status": "status", "outcome": self._status_target(intent, current, cases)}
        if intent.type == "new_request":
            return self._new_request(intent, event, conversation, decision, has_legacy_case=bool(current and not is_service_case(current)))
        target = self._find_case(intent.case_reference, current, cases)
        if target is None:
            return None
        if intent.type == "cancel":
            return self._cancel(target, intent)
        if intent.type == "close":
            return self._close(target, "Requester confirmed it is done.", closure="verified_by_requester")
        return self._update(target, intent, event, decision)

    def _knowledge_gap(
        self,
        intent: AgentIntent,
        event: RawEmailEvent,
        conversation: Conversation,
        decision: AgentDecision,
        current: Optional[Outcome],
    ) -> dict:
        """No-guess rule: a company question we cannot answer from verified knowledge goes to a person."""
        question = strip_for_ai(event.body_text or "")[:600] or intent.summary
        ask = AgentIntent(
            type="new_request",
            category="general",
            summary=f"Question: {(intent.summary or question)[:120]}",
            details={"question": question},
            priority="MEDIUM",
        )
        result = self._new_request(
            ask, event, conversation, decision,
            has_legacy_case=bool(current and not is_service_case(current)),
            extra_facts={"knowledge_gap": True},
        )
        if result.get("status") == "dispatched":
            result["status"] = "knowledge_gap"
        return result

    def _new_request(
        self,
        intent: AgentIntent,
        event: RawEmailEvent,
        conversation: Conversation,
        decision: AgentDecision,
        *,
        has_legacy_case: bool,
        extra_facts: Optional[dict] = None,
    ) -> dict:
        category = normalize_category(intent.category)
        route = route_for(self.session, self.tenant_id, category)
        details = _normalize_details(intent.details)
        requester = (event.sender or "").lower()
        person = self.session.exec(select(Person).where(Person.email == requester)).first()
        ref = self.engine.next_case_reference(case_prefix(category))
        title = (intent.summary or label_for(category))[:200]
        raw = strip_for_ai(event.body_text or "")
        verdict = infer_priority(f"{intent.summary}\n{raw}\n{details}", intent.priority)
        sla = sla_hours_for(verdict.priority, route.sla_hours)
        outcome = Outcome(
            tenant_id=self.tenant_id,
            case_reference=ref,
            template_code=SERVICE_TEMPLATE,
            category=category.upper()[:40],
            title=title,
            summary=title,
            requester_email=requester,
            requester_person_id=person.person_id if person else None,
            status=OutcomeStatus.ACTIVE.value,
            priority=verdict.priority,
            facts={
                "agent_case": True,
                "agent_category": category,
                "category_label": label_for(category),
                "details": details,
                "department_code": route.department_code,
                "department_name": route.department_name,
                "priority_reason": verdict.reason or None,
                "sla_hours": sla,
                "raw_request": raw[:2000],
                "desired_outcome": intent.desired_outcome or None,
                "risk_signals": intent.risk_signals or None,
                "tasks": list(intent.tasks) or tasks_from_text(raw) or None,
                "ai_plan": {
                    "category": category,
                    "priority": intent.priority,
                    "details": dict(intent.details or {}),
                    "missing": list(intent.missing),
                    "needs_admin": intent.needs_admin_decision,
                    "desired_outcome": intent.desired_outcome,
                    "risk_signals": intent.risk_signals,
                    "confidence": decision.confidence,
                    "source": decision.source,
                    "reason_summary": decision.reason_summary,
                },
                **(extra_facts or {}),
            },
            business_event_id=event.event_id,
            conversation_id=conversation.conversation_id,
            due_at=utcnow() + timedelta(hours=sla),
        )
        self.session.add(outcome)
        self.session.flush()
        if not has_legacy_case:
            conversation.current_outcome_id = outcome.outcome_id
            conversation.status = "ACTIVE"
            self.session.add(conversation)
        ticket = ServiceTicket(
            tenant_id=self.tenant_id,
            outcome_id=outcome.outcome_id,
            reference=ref,
            category=category,
            title=title,
            description=str(details.get("description") or details.get("issue") or title)[:2000],
            location=str(details.get("location") or details.get("office") or "")[:200] or None,
            priority=verdict.priority,
            department_code=route.department_code,
            requester_email=requester,
            sla_due_at=utcnow() + timedelta(hours=sla),
            details=details,
        )
        self.session.add(ticket)
        self.session.flush()
        self.audit.record(
            tenant_id=self.tenant_id,
            actor="ai_admin",
            action=AuditAction.OUTCOME_CREATED,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"case_reference": ref, "category": category, "department": route.department_code},
            correlation_id=event.event_id,
        )
        admin = self._admin()
        if verdict.urgent:
            self._notify_admin(outcome, kind="urgent", headline=f"URGENT - {verdict.reason}")
        elif (self.settings.admin_fyi_level or "").strip().lower() == "all" and admin and admin not in route.recipients:
            self._notify_admin(outcome, kind="info", headline="New request opened")
        return self._progress(outcome, intent, route, decision, text=event.body_text or "")

    def _progress(self, outcome: Outcome, intent: AgentIntent, route: Route, decision: AgentDecision, *, text: str) -> dict:
        """Move a case forward as far as policy allows: ask, get approval, or do it."""
        facts = outcome.facts or {}
        category = facts.get("agent_category") or "general"
        details = facts.get("details") or {}
        if category == "parking" and not details.get("parking_type") and _EMPLOYEE_PARKING_RE.search(
            f"{text}\n{facts.get('raw_request') or ''}\n{details}"
        ):
            details = {**details, "parking_type": "employee_permanent", "visit_date": details.get("visit_date") or "Permanent"}
            facts = _set_facts(self.session, outcome, details=details)
            ticket = self._ticket(outcome)
            if ticket:
                ticket.details = details
                self.session.add(ticket)
        filled = fill_required(category, details, f"{facts.get('raw_request') or ''}\n{text}")
        if filled != details:
            details = filled
            facts = _set_facts(self.session, outcome, details=details)
            ticket = self._ticket(outcome)
            if ticket:
                ticket.details = details
                self.session.add(ticket)
        missing = list(dict.fromkeys(intent.missing))
        if details.get("parking_type") == "employee_permanent":
            missing = [q for q in missing if not re.search(r"\b(?:date|day|when)\b", q, re.I)]
        # A free-text answer (rules fallback can't parse it) goes to the team rather than asking again.
        if not details.get("requester_note"):
            for question in missing_questions(category, details):
                if question not in missing:
                    missing.append(question)
        urgent = outcome.priority == "URGENT"
        if missing and not urgent:
            _set_facts(self.session, outcome, agent_stage="AWAITING_INFO", missing=missing,
                       info_requested_at=utcnow().isoformat())
            self._ticket_status(outcome, "OPEN")
            return {"intent": intent, "status": "awaiting_info", "outcome": outcome, "missing": missing}

        risk = assess_risk(
            category=category,
            text=f"{text}\n{details}",
            details=details,
            agent_flag=intent.needs_admin_decision,
            agent_reason=intent.decision_reason,
            confidence=decision.confidence,
            spend_limit=route.spend_approval_limit,
            known=has_playbook(category) or handles_category(self.session, self.tenant_id, category),
        )
        if not risk.needs_admin and self.settings.ai_emergency_stop and not urgent:
            risk = RiskVerdict(True, "the AI assistant is paused (emergency stop) - please confirm before the desk acts")
        _set_facts(self.session, outcome, decision_class=decision_class(category, risk.needs_admin))
        if risk.needs_admin and not facts.get("admin_approved"):
            if facts.get("agent_stage") != "AWAITING_APPROVAL":
                approval = Approval(
                    tenant_id=self.tenant_id,
                    outcome_id=outcome.outcome_id,
                    approval_type=f"{category.upper()}_REQUEST"[:60],
                    approver_role="ADMIN",
                    payload={"reason": risk.reason, "details": details},
                )
                self.session.add(approval)
                self.session.flush()
                _set_facts(
                    self.session, outcome, agent_stage="AWAITING_APPROVAL", missing=[],
                    decision_reason=risk.reason, approval_id=approval.approval_id,
                    approval_requested_at=utcnow().isoformat(),
                )
                self._ticket_status(outcome, "AWAITING_APPROVAL")
                self._notify_admin(outcome, kind="decision", headline=f"Needs your approval - {risk.reason}", route=route)
            return {"intent": intent, "status": "awaiting_approval", "outcome": outcome, "reason": risk.reason}
        result = self._dispatch(outcome, intent, route)
        if missing:
            # Urgent work starts at once; the open questions go to the requester in the same reply.
            _set_facts(self.session, outcome, missing=missing)
            result["missing"] = missing
        return result

    def _dispatch(self, outcome: Outcome, intent: Optional[AgentIntent], route: Route) -> dict:
        self._start_clock(outcome)
        facts = outcome.facts or {}
        category = facts.get("agent_category") or "general"
        action = playbook_for(category).action
        if action == "visitor_pass":
            passes = self._issue_visitor_passes(outcome)
            _set_facts(self.session, outcome, agent_stage="COMPLETED", missing=[], visitor_passes=passes)
            self._ticket_status(outcome, "RESOLVED")
            self._work_order(outcome, route, headline="Visitor pre-registered - add to today's gate manifest", final=True)
            return {"intent": intent, "status": "issued", "outcome": outcome, "passes": passes}
        if action == "fan_out":
            book = playbook_for(category)
            cats = [book.category, *book.fan_out]
            routes = [route] + [route_for(self.session, self.tenant_id, c) for c in book.fan_out]
            per_team = split_tasks(book.category, facts.get("tasks") or [], cats, facts.get("details"))
            by_inbox: dict[tuple[str, ...], list[Route]] = {}
            inbox_cats: dict[tuple[str, ...], list[str]] = {}
            for cat, team in zip(cats, routes):
                key = tuple(team.recipients)
                group = by_inbox.setdefault(key, [])
                if all(t.department_code != team.department_code for t in group):
                    group.append(team)
                inbox_cats.setdefault(key, []).append(cat)
            requester = (outcome.requester_email or "").strip().lower()

            def raised_it(inbox: tuple[str, ...], group: list[Route]) -> bool:
                # The requester's own team (its real contact, not an admin fallback) doesn't get a work order for it.
                return bool(requester) and requester in {r.lower() for r in inbox} and not any(
                    t.redirected_to_admin for t in group)

            own = {k for k, g in by_inbox.items() if raised_it(k, g)}
            if len(own) == len(by_inbox):
                own = set()
            names, groups, first_inbox, orders = [], [], None, []
            for inbox, group in by_inbox.items():
                label = " + ".join(t.department_name for t in group)
                tasks = list(dict.fromkeys(t for c in inbox_cats[inbox] for t in per_team.get(c, [])))
                if inbox in own:
                    groups.append({"label": label, "recipients": list(inbox), "done": True, "tasks": tasks,
                                   "note": "Raised by this team - no work order sent", "raised_by_team": True})
                    continue
                names.extend(t.department_name for t in group)
                first_inbox = first_inbox or inbox
                groups.append({"label": label, "recipients": list(inbox), "done": False, "tasks": tasks})
                orders.append((group[0], label, tasks))
            joining = joining_day(facts) if category == "onboarding" else None
            if joining:
                _set_facts(self.session, outcome, joining_on=joining.isoformat())
            day1 = self._day_one_note(outcome) if category == "onboarding" else ""
            _set_facts(self.session, outcome, agent_stage="DISPATCHED", missing=[], teams=names, team_groups=groups,
                       day1_note=day1 or None)
            for team_route, label, tasks in orders:
                self._work_order(
                    outcome, team_route, headline=f"{book.label} - {label} tasks",
                    final=False, fingerprint_extra=label, tasks=tasks,
                )
            self._ticket_status(outcome, "ASSIGNED", assignee=first_inbox[0] if first_inbox else None)
            return {"intent": intent, "status": "dispatched", "outcome": outcome, "team": ", ".join(names), "day1": day1}
        if action == "parking" and (facts.get("details") or {}).get("parking_type") == "employee_permanent":
            _set_facts(self.session, outcome, agent_stage="DISPATCHED", missing=[])
            self._ticket_status(outcome, "ASSIGNED", assignee=route.recipients[0] if route.recipients else None)
            self._work_order(outcome, route, headline="Employee parking - permanent allocation needed", final=False)
            return {"intent": intent, "status": "dispatched", "outcome": outcome, "team": route.department_name}
        if action == "parking":
            slots = self._allot_parking(outcome)
            done = bool(slots) and all(s.get("slot") for s in slots)
            _set_facts(self.session, outcome, agent_stage="COMPLETED" if done else "DISPATCHED", missing=[], parking=slots)
            self._ticket_status(outcome, "RESOLVED" if done else "ASSIGNED")
            self._work_order(
                outcome, route,
                headline="Visitor parking allotted" if done else "Parking needed - no free visitor slot, please arrange",
                final=done,
            )
            return {"intent": intent, "status": "allocated" if done else "dispatched", "outcome": outcome, "parking": slots}
        _set_facts(self.session, outcome, agent_stage="DISPATCHED", missing=[])
        self._ticket_status(outcome, "ASSIGNED", assignee=route.recipients[0] if route.recipients else None)
        headline = "New work order"
        if facts.get("knowledge_gap"):
            headline = 'Question needs a verified answer - reply "tell requester: <answer>"'
        elif outcome.priority == "URGENT":
            headline = "URGENT work order - please act now"
        elif outcome.priority == "HIGH":
            headline = "High-priority work order"
        self._work_order(outcome, route, headline=headline, final=False)
        return {"intent": intent, "status": "dispatched", "outcome": outcome, "team": route.department_name}

    def _start_clock(self, outcome: Outcome) -> None:
        """SLA runs from when the team gets the work, not from when we were still asking or waiting for approval."""
        facts = outcome.facts or {}
        if facts.get("dispatched_at"):
            return
        hours = float(facts.get("sla_hours") or 24)
        now = utcnow()
        outcome.due_at = now + timedelta(hours=hours)
        needed_by = _needed_by(facts)
        if needed_by and now + timedelta(minutes=15) < needed_by < outcome.due_at:
            outcome.due_at = needed_by
        _set_facts(self.session, outcome, dispatched_at=now.isoformat())
        ticket = self._ticket(outcome)
        if ticket:
            ticket.sla_due_at = outcome.due_at
            self.session.add(ticket)

    def _update(self, outcome: Outcome, intent: AgentIntent, event: RawEmailEvent, decision: AgentDecision) -> dict:
        facts = outcome.facts or {}
        details = {**(facts.get("details") or {}), **_normalize_details(intent.details)}
        if not intent.details and (event.body_text or "").strip():
            note = strip_for_ai(event.body_text or "")[:600]
            if note:
                details["requester_note"] = note
        _set_facts(self.session, outcome, details=details)
        ticket = self._ticket(outcome)
        if ticket:
            ticket.details = details
            self.session.add(ticket)
        stage = facts.get("agent_stage")
        route = route_for_case(self.session, self.tenant_id, facts)
        said = strip_for_ai(event.body_text or "")
        if stage == "RESOLVED" and _NOT_FIXED_RE.search(said):
            return self.reopen(outcome, said, actor=outcome.requester_email or "requester", intent=intent)
        if stage == "RESOLVED" and _SATISFIED_RE.search(said):
            self._close(outcome, "Requester confirmed it is sorted.", closure="verified_by_requester")
            return {"intent": intent, "status": "closed", "outcome": outcome}
        if stage == "AWAITING_INFO":
            return self._progress(outcome, intent, route, decision, text=event.body_text or "")
        if stage in {"DISPATCHED", "AWAITING_APPROVAL"} and intent.details:
            self._work_order(outcome, route, headline="Update from requester", final=False, fingerprint_extra=event.event_id)
        return {"intent": intent, "status": "updated", "outcome": outcome}

    def reopen(self, outcome: Outcome, reason: str, *, actor: str, intent: Optional[AgentIntent] = None) -> dict:
        facts = outcome.facts or {}
        count = int(facts.get("reopen_count") or 0) + 1
        outcome.status = OutcomeStatus.ACTIVE.value
        outcome.closed_at = None
        self.session.add(outcome)
        _set_facts(
            self.session, outcome, agent_stage="DISPATCHED", reopen_count=count, reopen_reason=reason[:400],
            dispatched_at=None, sla_reminded_at=None, sla_escalated_at=None, resolution_note=None,
            evidence_status=None, closure_type=None, verified=None,
        )
        add_correction(self.session, outcome, "reopened", actor, reason=reason[:200])
        self._start_clock(outcome)
        self._ticket_status(outcome, "REOPENED")
        route = route_for_case(self.session, self.tenant_id, facts)
        self._work_order(
            outcome, route, headline=f"Reopened - requester says it is not sorted (reopen #{count})",
            final=False, fingerprint_extra=f"reopen{count}",
        )
        if count >= 2:
            self._notify_admin(outcome, kind="at_risk", headline=f"Reopened {count} times - needs a closer look")
        logger.info("desk_case_reopened", outcome_id=outcome.outcome_id, count=count, actor=actor)
        return {"intent": intent, "status": "reopened", "outcome": outcome, "team": route.department_name}

    def _cancel(self, outcome: Outcome, intent: AgentIntent) -> dict:
        outcome.status = OutcomeStatus.CANCELLED.value
        outcome.closed_at = utcnow()
        _set_facts(self.session, outcome, agent_stage="CANCELLED")
        self._ticket_status(outcome, "CANCELLED")
        for vp in self.session.exec(select(VisitorPass).where(VisitorPass.outcome_id == outcome.outcome_id)).all():
            vp.status = "CANCELLED"
            self.session.add(vp)
        route = route_for_case(self.session, self.tenant_id, outcome.facts or {})
        self._work_order(outcome, route, headline="Cancelled by requester - no action needed", final=True)
        self.record_closure(outcome, "cancelled")
        return {"intent": intent, "status": "cancelled", "outcome": outcome}

    def _close(self, outcome: Outcome, note: str, *, closure: str = "administrative") -> dict:
        outcome.status = OutcomeStatus.CLOSED.value
        outcome.closed_at = utcnow()
        _set_facts(self.session, outcome, agent_stage="CLOSED", resolution_note=note)
        self._ticket_status(outcome, "CLOSED")
        self.record_closure(outcome, closure)
        return {"intent": None, "status": "closed", "outcome": outcome}

    def record_closure(self, outcome: Outcome, closure: str) -> None:
        """Honest closure reason (blueprint 11.3) and the learning record; never let it break the close itself."""
        from app.agent.learning import VERIFIED_CLOSURES

        _set_facts(self.session, outcome, closure_type=closure, verified=closure in VERIFIED_CLOSURES)
        try:
            save_learning_record(self.session, outcome)
        except Exception as exc:  # noqa: BLE001
            logger.warning("learning_record_failed", outcome_id=outcome.outcome_id, error=str(exc))

    def auto_close_resolved(self, outcome: Outcome) -> None:
        """Quiet period after resolution: verified only when the team left completion evidence."""
        evidence = (outcome.facts or {}).get("evidence_status")
        closure = "verified_evidence" if evidence in {"provided", "admin_confirmed", "not_required"} else "closed_without_evidence"
        outcome.status = OutcomeStatus.CLOSED.value
        outcome.closed_at = utcnow()
        self.session.add(outcome)
        _set_facts(self.session, outcome, agent_stage="CLOSED", closed_reason="auto-closed after resolution")
        self._ticket_status(outcome, "CLOSED")
        self.record_closure(outcome, closure)

    # ------------------------------------------------------------ helpers
    def _ticket(self, outcome: Outcome) -> Optional[ServiceTicket]:
        return self.session.exec(select(ServiceTicket).where(ServiceTicket.outcome_id == outcome.outcome_id)).first()

    def _ticket_status(self, outcome: Outcome, status: str, assignee: Optional[str] = None) -> None:
        ticket = self._ticket(outcome)
        if not ticket:
            return
        ticket.status = status
        if assignee:
            ticket.assignee_email = assignee
        if status in {"RESOLVED", "CLOSED"}:
            ticket.resolved_at = ticket.resolved_at or utcnow()
        ticket.updated_at = utcnow()
        self.session.add(ticket)

    def _issue_visitor_passes(self, outcome: Outcome) -> list[dict]:
        details = (outcome.facts or {}).get("details") or {}
        names = _as_list(details.get("visitor_names"))
        vehicles = _as_list(details.get("vehicle_numbers"))
        out = []
        for i, raw in enumerate(names):
            m = re.match(r"^(.*?)\s*\((.*)\)\s*$", raw)
            name, company = (m.group(1), m.group(2)) if m else (raw, details.get("company"))
            code = f"VP-{secrets.token_hex(3).upper()}"
            self.session.add(
                VisitorPass(
                    tenant_id=self.tenant_id,
                    outcome_id=outcome.outcome_id,
                    pass_code=code,
                    visitor_name=name.strip()[:120],
                    company=(str(company).strip()[:120] if company else None),
                    host_email=outcome.requester_email,
                    visit_date=str(details.get("visit_date") or "")[:40] or None,
                    visit_time=str(details.get("visit_time") or "")[:40] or None,
                    office=str(details.get("location") or details.get("office") or "")[:120] or None,
                    vehicle_number=vehicles[i] if i < len(vehicles) else None,
                    purpose=str(details.get("purpose") or "")[:200] or None,
                )
            )
            out.append({"name": name.strip(), "company": company, "pass_code": code})
        self.session.flush()
        return out

    def _allot_parking(self, outcome: Outcome) -> list[dict]:
        details = (outcome.facts or {}).get("details") or {}
        day = str(details.get("visit_date") or "")[:40]
        vehicles = _as_list(details.get("vehicle_numbers"))
        taken = {
            vp.parking_slot
            for vp in self.session.exec(
                select(VisitorPass).where(VisitorPass.tenant_id == self.tenant_id, VisitorPass.visit_date == day)
            ).all()
            if vp.parking_slot and vp.status != "CANCELLED"
        }
        free = [
            r.name
            for r in self.session.exec(
                select(Resource).where(Resource.tenant_id == self.tenant_id, Resource.type == "PARKING_SLOT")
            ).all()
            if r.status == "AVAILABLE" and r.name not in taken
        ]
        out = []
        for plate in vehicles:
            slot = free.pop(0) if free else None
            self.session.add(
                VisitorPass(
                    tenant_id=self.tenant_id,
                    outcome_id=outcome.outcome_id,
                    pass_code=f"PK-{secrets.token_hex(3).upper()}",
                    visitor_name=str(details.get("visitor_names") or "Guest vehicle")[:120],
                    host_email=outcome.requester_email,
                    visit_date=day or None,
                    vehicle_number=plate[:40],
                    parking_slot=slot,
                    status="REGISTERED",
                )
            )
            out.append({"vehicle": plate, "slot": slot})
        self.session.flush()
        return out

    def _briefing(self, outcome: Outcome, headline: str, *, kind: str, tasks: Optional[list[str]] = None) -> str:
        facts = outcome.facts or {}
        name = resolve_requester_name(self.session, outcome=outcome)
        lines = [f"{outcome.case_reference} - {outcome.title}", "", headline, ""]
        if tasks is None and kind in {"work", "decision"} and not facts.get("team_groups"):
            tasks = facts.get("tasks")
        if tasks:
            lines += ["YOUR TASKS:" if kind == "work" else "Requested:", *[f"{i}. {t}" for i, t in enumerate(tasks, 1)], ""]
        lines.append(f"Requester: {name} <{outcome.requester_email}>" if name not in {"there", "team"} else f"Requester: {outcome.requester_email}")
        lines.append(f"Type: {facts.get('category_label') or label_for(facts.get('agent_category'))}")
        working = [g["label"] for g in facts.get("team_groups") or [] if not g.get("raised_by_team")]
        if working:
            lines.append(f"Teams working on it: {', '.join(working)}")
        elif facts.get("department_name"):
            lines.append(f"Team: {facts['department_name']}")
        if outcome.priority and outcome.priority != "MEDIUM":
            lines.append(f"Priority: {outcome.priority.title()}" + (f" ({facts['priority_reason']})" if facts.get("priority_reason") else ""))
        if outcome.due_at and facts.get("dispatched_at"):
            from app.engine.event_services import fmt_local

            lines.append(f"Due by: {fmt_local(outcome.due_at + timedelta(hours=5, minutes=30))}")
        vendor = self._preferred_vendor(facts.get("agent_category") or "")
        if vendor:
            lines.append(f"Preferred vendor: {vendor}")
        # With a task list, the raw item list would show every team the other teams' work.
        hide = {"description"} | ({"items", "item", "tasks", "requirements"} if facts.get("tasks") or facts.get("team_groups") else set())
        detail_lines = _details_lines({k: v for k, v in (facts.get("details") or {}).items() if k not in hide})
        desc = (facts.get("details") or {}).get("description")
        if desc:
            lines += ["", f"What they asked: {desc}"]
        if detail_lines:
            lines += ["", "Details:", *detail_lines]
        for p in facts.get("visitor_passes") or []:
            lines.append(f"- Pass {p['pass_code']}: {p['name']}" + (f" ({p['company']})" if p.get("company") else ""))
        for p in facts.get("parking") or []:
            lines.append(f"- Vehicle {p['vehicle']}: " + (f"slot {p['slot']}" if p.get("slot") else "no free slot"))
        lines.append("")
        if kind == "decision":
            lines.append('Reply "approve" or "reject, <reason>". You can also say "tell requester: <message>".')
        elif kind == "work":
            proof = evidence_hint(facts.get("agent_category"))
            done = f'"done - <{proof}>"' if proof else '"done" when finished (add a note if you like)'
            lines.append('Reply "on it" / "ETA 4 pm" to update the requester, "issue: <what is blocking>" if stuck, '
                         f'{done}, "assign to <email>", '
                         '"tell requester: <message>", "change <detail> to <value>", "close" or "cancel".')
            if proof:
                lines.append("A job is only marked verified once we have that note or a photo attached to your reply.")
            lines.append('Wrong team or type? Reply "change team to <team>", "change type to <type>" or '
                         '"change priority to high" - the desk learns from these corrections.')
        return "\n".join(lines) + "\n"

    @staticmethod
    def _day_one_note(outcome: Outcome) -> str:
        d = (outcome.facts or {}).get("details") or {}
        who = d.get("employee_name") or d.get("joiner_name") or d.get("name") or "the new joiner"
        when = d.get("joining_date") or d.get("start_date") or d.get("date") or "the joining date"
        where = d.get("location") or d.get("office") or "the office reception"
        day = joining_day(outcome.facts or {})
        if day and day <= _ist_now().date():
            return (
                f"First-days note for {who} (you can forward this):\n"
                f"- Joined on {when} at {where}; HR will complete any pending joining formalities.\n"
                "- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please "
                "use a visitor pass at reception."
            )
        return (
            f"Day-1 note for {who} (you can forward this):\n"
            f"- Report on {when} at {where} by 9:30 AM with a government photo ID.\n"
            "- HR will meet you at reception for joining formalities.\n"
            "- Your laptop, login, desk and ID / access card will be ready on day one."
        )

    def _preferred_vendor(self, category: str) -> Optional[str]:
        words = _VENDOR_HINTS.get(category)
        if not words:
            return None
        for v in self.session.exec(select(Vendor).where(Vendor.tenant_id == self.tenant_id, Vendor.status == "ACTIVE")).all():
            if any(w in (v.category or "").lower() for w in words):
                return v.name if is_placeholder(v.contact_email) else f"{v.name} <{v.contact_email}>"
        return None

    def _work_order(
        self, outcome: Outcome, route: Route, *, headline: str, final: bool, fingerprint_extra: str = "",
        tasks: Optional[list[str]] = None,
    ) -> None:
        if not route.recipients:
            return
        note = ""
        if route.redirected_to_admin:
            note = f"(No {route.department_name} contact set yet - sent to you. Add it in Company setup.)"
        body = self._briefing(outcome, f"{headline}\n{note}".strip(), kind="info" if final else "work", tasks=tasks)
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=CommunicationType.INFORMATION_ONLY.value if final else CommunicationType.ACTION_REQUIRED.value,
            body=body,
            recipients=route.recipients,
            action_label="DONE" if final else "WORK ORDER",
            subject_hint=headline[:80],
            suppress_fingerprint=f"wo:{headline}:{fingerprint_extra}",
        )
        admin = self._admin()
        if final and admin and admin not in route.recipients and not digest_mode():
            self._notify_admin(outcome, kind="info", headline=f"Completed by the desk - {headline}")

    def _notify_admin(self, outcome: Outcome, *, kind: str, headline: str, route: Optional[Route] = None) -> None:
        admin = self._admin()
        recipients = [admin] if admin else []
        if kind == "decision" and route and route.approver and route.approver not in recipients:
            recipients.append(route.approver)
        if not recipients:
            return
        body = self._briefing(outcome, headline, kind=kind)
        if kind == "decision":
            from app.services.approval_links import approval_links_block

            links = approval_links_block((outcome.facts or {}).get("approval_id"))
            if links:
                body += f"\nOne click:\n{links}\n"
        labels = {"decision": "OPS DECISION", "urgent": "URGENT", "at_risk": "AT RISK", "escalation": "ESCALATION"}
        ctype = CommunicationType.APPROVAL_REQUIRED.value if kind == "decision" else (
            CommunicationType.ACTION_REQUIRED.value if kind in {"urgent", "at_risk", "escalation"}
            else CommunicationType.INFORMATION_ONLY.value
        )
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=ctype,
            body=body,
            recipients=recipients,
            action_label=labels.get(kind, "OPS UPDATE"),
            subject_hint=headline[:80],
            suppress_fingerprint=f"admin:{kind}:{headline}",
        )

    @staticmethod
    def _admin() -> Optional[str]:
        from app.services.admin_ops import admin_ops_email

        return admin_ops_email()

    # ------------------------------------------------------------ reply
    def _reply_text(
        self, decision: AgentDecision, mine: list[AgentIntent], results: list[dict], name: str, *, split: bool
    ) -> str:
        if any(r["status"] == "knowledge_gap" for r in results):
            # The model's draft may contain a guessed answer - only say what is verified.
            return self._template_reply(results, name, split=split)
        refs = [r["outcome"].case_reference for r in results if r.get("intent") and r["intent"].type == "new_request" and r.get("outcome")]
        draft = (decision.reply_to_requester or "").strip()
        if draft and not split and self._draft_is_grounded(draft, mine, results):
            for i, ref in enumerate(refs, start=1):
                draft = draft.replace(f"[[REF{i}]]", ref)
            draft = re.sub(r"\[\[REF\d+\]\]", "", draft)
            missing_refs = [r for r in refs if r not in draft]
            if missing_refs:
                draft += "\n\nReference: " + ", ".join(missing_refs)
            for r in results:
                if r.get("day1") and r["day1"].split(" for ")[0] not in draft:
                    draft = _before_signoff(draft, r["day1"])
            return draft
        if all(r["status"] == "small_talk" for r in results) and not draft:
            return ""
        return self._template_reply(results, name, split=split)

    @staticmethod
    def _draft_is_grounded(draft: str, mine: list[AgentIntent], results: list[dict]) -> bool:
        low = draft.lower()
        for r in results:
            intent = r.get("intent")
            if r["status"] == "awaiting_approval" and (_FORWARD_CLAIM_RE.search(draft) or "approv" not in low):
                return False
            if intent and intent.type == "update_case" and r["status"] == "awaiting_info":
                if "?" not in draft or _FORWARD_CLAIM_RE.search(draft):
                    return False
            if r["status"] == "reopened" and "reopen" not in low:
                return False
            if r["status"] == "closed" and intent and intent.type == "update_case" and "close" not in low:
                return False
            if not intent or intent.type != "new_request":
                continue
            if r["status"] == "awaiting_approval" and not intent.needs_admin_decision:
                return False
            if r["status"] == "awaiting_info" and not intent.missing and "?" not in draft:
                return False
            if r["status"] in {"dispatched", "issued", "allocated"} and intent.needs_admin_decision:
                return False
        return not re.search(r"\b(?:has been|is now)\s+(?:fixed|resolved|approved|booked|repaired)\b", low)

    def _template_reply(self, results: list[dict], name: str, *, split: bool) -> str:
        first = name.split(" ")[0] if name and name not in {"there", "team"} else ""
        lines = [f"Hi {first}," if first else "Hi,", ""]
        for r in results:
            outcome: Optional[Outcome] = r.get("outcome")
            status = r["status"]
            ref = outcome.case_reference if outcome else ""
            what = (outcome.title if outcome else "") or "your request"
            if status == "awaiting_info":
                lines.append(f"I've logged {what} as {ref}. To take it forward I just need:")
                lines += [f"- {q}" for q in r.get("missing", [])]
            elif status == "awaiting_approval":
                lines.append(f"I've logged {what} as {ref} and passed it to the admin for approval. I'll update you here.")
            elif status == "dispatched":
                team = r.get("team") or ((outcome.facts or {}).get("department_name") if outcome else None) or "the team"
                if outcome is not None and outcome.priority == "URGENT":
                    lines.append(f"I've logged {what} as {ref} as URGENT and alerted {team} and the admin right away.")
                else:
                    lines.append(f"I've logged {what} as {ref} and assigned it to {team}. I'll let you know once it's done.")
                if r.get("missing"):
                    lines += ["", "To help them, could you also tell me:"] + [f"- {q}" for q in r["missing"]]
                if r.get("day1"):
                    lines += ["", r["day1"]]
            elif status == "knowledge_gap":
                lines.append("I couldn't find a verified answer to that in our records, so rather than guess I've passed "
                             f"your question to the admin team ({ref}). They'll reply to you here.")
            elif status == "reopened":
                team = r.get("team") or "the team"
                lines.append(f"Sorry it's still not sorted - I've reopened {ref} ({what}) and sent it back to {team} "
                             "with your note. I'll update you here.")
            elif status == "issued":
                lines.append(f"Your visitors are pre-registered ({ref}):")
                lines += [f"- {p['name']}: pass {p['pass_code']}" for p in r.get("passes", [])]
                lines.append("Please ask them to carry a photo ID and meet you at reception.")
            elif status == "allocated":
                lines.append(f"Parking is arranged ({ref}):")
                lines += [f"- {p['vehicle']}: slot {p['slot']}" for p in r.get("parking", [])]
            elif status == "updated":
                lines.append(f"Thanks - I've added that to {ref}.")
            elif status == "cancelled":
                lines.append(f"Done - {ref} is cancelled.")
            elif status == "closed":
                lines.append(f"Great, I've closed {ref}. Thanks for confirming!")
            elif status == "status" and outcome:
                state = case_state(outcome)
                lines.append(f"{ref} ({outcome.title}) is currently: {str(state.get('stage') or outcome.status).replace('_', ' ').lower()}.")
            elif status == "status":
                lines.append("I couldn't find an open request for you - could you share the reference number?")
            elif status == "empty":
                lines.append("Your mail seems to have come through empty - could you resend it with the details?")
            elif status in {"small_talk", "question"}:
                lines.append("How can I help you today? I can help with rooms, visitors, parking, repairs, IT, supplies, travel and more.")
            lines.append("")
        if split:
            lines.append("Your other request is being handled in a separate mail on this thread.")
            lines.append("")
        lines.append(self.settings.mail_signature)
        return "\n".join(lines).strip() + "\n"

    def _send_reply(
        self, event: RawEmailEvent, conversation: Conversation, outcome: Optional[Outcome], body: str, results: list[dict]
    ) -> None:
        subject = (event.subject or "").strip() or "Your request"
        if not re.match(r"^\s*re\s*:", subject, re.I):
            subject = f"Re: {subject}"
        refs = [r["outcome"].case_reference for r in results if r.get("outcome") is not None]
        for ref in dict.fromkeys(refs):
            if f"[{ref}]" not in subject:
                subject = f"{subject} [{ref}]"
        self.comms.send(
            communication_type=CommunicationType.INFORMATION_ONLY.value,
            recipients=[(event.sender or "").lower()],
            subject=subject[:200],
            body=body,
            conversation_id=conversation.conversation_id,
            outcome_id=outcome.outcome_id if outcome else None,
            thread_id=conversation.thread_id,
            in_reply_to_message_id=event.provider_message_id or event.gmail_message_id,
            idempotency_key=f"agent-reply:{event.event_id}",
        )

    def _record_decision(self, event: RawEmailEvent, conversation: Conversation, decision: AgentDecision) -> None:
        from app.models.intake import AIDecision

        self.session.add(
            AIDecision(
                tenant_id=self.tenant_id,
                event_id=event.event_id,
                conversation_id=conversation.conversation_id,
                model=decision.source,
                model_version=decision.source,
                prompt_version="admin-agent-v1",
                confidence=decision.confidence,
                output=decision.model_dump(),
                recommendation=",".join(i.type for i in decision.intents),
                rationale="admin desk decision",
                route="AGENT",
            )
        )
        self.session.flush()

    # ------------------------------------------------------------ admin / team replies
    def apply_team_reply(self, outcome: Outcome, text: str, actor: str, attachments: Optional[list[str]] = None) -> dict:
        """Admin or department replying on a desk case in plain words."""
        files = [a for a in (attachments or []) if a]
        body = (text or "").strip()
        low = body.lower()
        facts = outcome.facts or {}
        route = route_for_case(self.session, self.tenant_id, facts)
        tell = re.search(r"(?:tell|inform|message|reply to)\s+(?:the\s+)?requester\s*[:\-,]?\s*(.+)", body, re.I | re.S)
        assign = re.search(r"\bassign(?:ed)?\s+(?:it\s+)?to\s+([\w.+-]+@[\w.-]+)", body, re.I)
        if re.match(r"^\s*(?:approved?|ok(?:ay)?\s+approved?|yes,?\s+approve|go\s+ahead)\b", low):
            if facts.get("agent_stage") != "AWAITING_APPROVAL":
                return {"applied": False, "action": "approve", "note": "nothing pending approval"}
            self._decide_approval(outcome, "APPROVED", actor)
            self.on_approval_decided(outcome, approved=True, actor=actor)
            return {"applied": True, "action": "approve"}
        if re.match(r"^\s*(?:reject(?:ed)?|decline[d]?|deny|denied|not\s+approved)\b", low):
            reason = re.sub(r"^\s*(?:reject(?:ed)?|decline[d]?|deny|denied|not\s+approved)\b[\s,:\-]*", "", body, flags=re.I).strip()
            self._decide_approval(outcome, "REJECTED", actor, reason)
            self.on_approval_decided(outcome, approved=False, actor=actor, note=reason)
            return {"applied": True, "action": "reject"}
        if assign:
            email = assign.group(1).lower()
            self._ticket_status(outcome, "ASSIGNED", assignee=email)
            _set_facts(self.session, outcome, assignee_email=email)
            add_correction(self.session, outcome, "reassigned", actor, to=email)
            self.comms.send_case_update(
                outcome=outcome,
                communication_type=CommunicationType.ACTION_REQUIRED.value,
                body=self._briefing(outcome, f"Assigned to you by {actor}", kind="work"),
                recipients=[email],
                action_label="WORK ORDER",
                subject_hint="Assigned to you",
                suppress_fingerprint=f"assign:{email}",
            )
            return {"applied": True, "action": "assign", "assignee": email}
        if tell:
            message = tell.group(1).strip()
            if facts.get("knowledge_gap") and facts.get("agent_stage") not in {"RESOLVED", "CLOSED"}:
                self._tell_requester(outcome, f"About your question ({outcome.case_reference}): {message}")
                self._record_evidence(outcome, message, actor, files)
                self._resolve(outcome, note=message[:400], actor=actor, evidence="provided")
                self._draft_knowledge(outcome, message, actor)
                return {"applied": True, "action": "answered"}
            self._tell_requester(outcome, message)
            return {"applied": True, "action": "message"}
        change = re.match(r"^\s*(?:change|update|set|move)\s+(?:the\s+)?(.{2,40}?)\s+to\s+(.+)$", body.splitlines()[0] if body else "", re.I)
        if change:
            field = re.sub(r"[^a-z0-9]+", "_", change.group(1).lower()).strip("_")
            value = change.group(2).strip().rstrip(".")
            if field in {"category", "type", "request_type"}:
                return self._recategorise(outcome, value, actor)
            if field in {"team", "department", "dept"}:
                return self._reroute(outcome, value, actor)
            if field == "priority":
                return self._reprioritise(outcome, value, actor)
            previous = (facts.get("details") or {}).get(field)
            details = {**(facts.get("details") or {}), field: value}
            _set_facts(self.session, outcome, details=details)
            add_correction(self.session, outcome, "detail_changed", actor, field=field, before=previous, after=value)
            ticket = self._ticket(outcome)
            if ticket:
                ticket.details = details
                self.session.add(ticket)
            self._tell_requester(
                outcome,
                f"A quick update on {outcome.case_reference} ({outcome.title}): "
                f"{change.group(1).strip()} is now {value}.\n\nReply here if that doesn't work for you.",
            )
            return {"applied": True, "action": "change", "field": field, "value": value}
        if re.match(r"^\s*(?:close|close\s+it|close\s+the\s+case)\b", low):
            self._close(outcome, f"Closed by {actor}", closure="administrative")
            self._tell_requester(outcome, f"{outcome.case_reference} ({outcome.title}) is now closed. Reply here if you need anything else.")
            return {"applied": True, "action": "close"}
        if not re.match(r"^\s*cancel", low) and facts.get("agent_stage") != "RESOLVED":
            team, tasks = self._team_of(outcome, actor)
            reading = self.agent.read_team_reply(body, {
                "CASE": f"{outcome.case_reference} - {outcome.title}",
                "TYPE": facts.get("category_label") or facts.get("agent_category"),
                "STAGE": facts.get("agent_stage"),
                "TEAM": team,
                "YOUR_TASKS": tasks or facts.get("tasks") or [],
            })
            if reading:
                note = reading.note.strip() or None
                if reading.action == "done":
                    return self._team_done(outcome, body, actor, files, note=note)
                if reading.action == "progress":
                    return self._team_progress(outcome, body, actor, note=note)
                if reading.action == "blocked":
                    return self._team_blocked(outcome, body, actor, note=note)
                if reading.action == "message" and note:
                    self._tell_requester(outcome, f"Message about {outcome.case_reference} ({outcome.title}) from {team}: {note}")
                    return {"applied": True, "action": "message"}
        if _TEAM_ISSUE_RE.match(body):
            return self._team_blocked(outcome, body, actor)
        if _TEAM_PROGRESS_RE.match(body):
            return self._team_progress(outcome, body, actor)
        if _is_done_reply(low):
            return self._team_done(outcome, body, actor, files)
        if re.match(r"^\s*cancel", low):
            self._cancel(outcome, AgentIntent(type="cancel"))
            self._tell_requester(outcome, f"{outcome.case_reference} ({outcome.title}) has been cancelled by the admin team.")
            return {"applied": True, "action": "cancel"}
        if facts.get("agent_stage") == "RESOLVED" and facts.get("evidence_status") == "missing" and (body or files):
            return self._add_evidence(outcome, body, actor, files)
        return {"applied": False, "action": "unknown"}

    def on_approval_decided(self, outcome: Outcome, *, approved: bool, actor: str, note: str = "") -> dict:
        """Single place a desk approval takes effect - mail reply, dashboard or signed link."""
        facts = outcome.facts or {}
        if facts.get("agent_stage") != "AWAITING_APPROVAL":
            return {"applied": False}
        route = route_for_case(self.session, self.tenant_id, facts)
        if approved:
            if outcome.status == OutcomeStatus.AT_RISK.value:
                outcome.status = OutcomeStatus.ACTIVE.value
                self.session.add(outcome)
            _set_facts(self.session, outcome, admin_approved=True, approved_by=actor)
            result = self._dispatch(outcome, None, route)
            self._tell_requester(outcome, self._approved_text(outcome, result))
            return {"applied": True, "action": "approve", "result": result.get("status")}
        outcome.status = OutcomeStatus.CLOSED.value
        outcome.closed_at = utcnow()
        self.session.add(outcome)
        _set_facts(self.session, outcome, agent_stage="REJECTED", resolution_note=note or "Not approved", rejected_by=actor)
        self._ticket_status(outcome, "REJECTED")
        self.record_closure(outcome, "rejected")
        self._tell_requester(
            outcome,
            f"Sorry - {outcome.case_reference} ({outcome.title}) could not be approved"
            + (f": {note}" if note else ".") + "\n\nReply here if you'd like to discuss it.",
        )
        return {"applied": True, "action": "reject"}

    def _team_blocked(self, outcome: Outcome, body: str, actor: str, note: Optional[str] = None) -> dict:
        note = (note or re.sub(r"^\s*(?:issue|problem|blocked|on\s+hold)\s*[:\-,]?\s*", "", body, flags=re.I).strip())[:400]
        outcome.status = OutcomeStatus.AT_RISK.value
        self.session.add(outcome)
        _set_facts(self.session, outcome, agent_stage="BLOCKED", blocked_reason=note, blocked_by=actor,
                   blocked_at=utcnow().isoformat())
        self._ticket_status(outcome, "ON_HOLD")
        team, _ = self._team_of(outcome, actor)
        if actor != self._admin():
            self._notify_admin(outcome, kind="at_risk", headline=f"{team} reports a problem: {note[:80]}")
        self._tell_requester(
            outcome,
            f"A quick update on {outcome.case_reference} ({outcome.title}): {team} has hit a snag - {note}\n\n"
            "We're on it and will update you as soon as it moves.",
        )
        return {"applied": True, "action": "blocked"}

    def _team_progress(self, outcome: Outcome, body: str, actor: str, note: Optional[str] = None) -> dict:
        note = (note or body.strip().splitlines()[0])[:300]
        facts = outcome.facts or {}
        if outcome.status == OutcomeStatus.AT_RISK.value:
            outcome.status = OutcomeStatus.ACTIVE.value
            self.session.add(outcome)
        _set_facts(self.session, outcome, agent_stage="IN_PROGRESS", progress_note=note, progress_by=actor,
                   acknowledged_at=facts.get("acknowledged_at") or utcnow().isoformat())
        self._ticket_status(outcome, "IN_PROGRESS")
        team, _ = self._team_of(outcome, actor)
        self._order_update(
            outcome, actor,
            requester_msg=f"Update on {outcome.case_reference} ({outcome.title}) from {team}: {note}",
            admin_headline=f"{team} update: {note[:80]}",
        )
        return {"applied": True, "action": "in_progress"}

    def _team_done(self, outcome: Outcome, body: str, actor: str, files: Optional[list[str]] = None,
                   note: Optional[str] = None) -> dict:
        facts = outcome.facts or {}
        files = files or []
        note = note or re.sub(r"^\s*(?:it'?s\s+|all\s+)?(?:done|fixed|resolved|completed|closed)\b[\s,.:\-]*", "", body,
                              flags=re.I).strip()
        if facts.get("agent_stage") == "RESOLVED":
            return self._add_evidence(outcome, note or body, actor, files)
        groups = [dict(g) for g in facts.get("team_groups") or []]
        admin = self._admin()
        who = (actor or "").lower()
        mine = [g for g in groups if not g.get("done") and who in {r.lower() for r in g.get("recipients") or []}]
        # The admin finishes the whole job only when not standing in for a team that is still pending
        # (e.g. IT has no inbox yet), or when they say so outright.
        on_a_team = any(who in {r.lower() for r in g.get("recipients") or []} for g in groups)
        acting_as_team = on_a_team and not _ALL_DONE_RE.match(body)
        if len(groups) > 1 and (who != (admin or "").lower() or acting_as_team):
            for g in mine:
                g["done"] = True
                g["note"] = note[:300] or None
            pending = [g["label"] for g in groups if not g.get("done")]
            if pending and not mine:
                # A team that already finished (or someone outside the job) can't close the other teams' work.
                if note or files:
                    self._record_evidence(outcome, note, actor, files)
                return {"applied": True, "action": "team_done", "pending": pending}
            if mine and pending:
                if note or files:
                    self._record_evidence(outcome, note, actor, files)
                _set_facts(self.session, outcome, team_groups=groups, agent_stage="IN_PROGRESS")
                team = " + ".join(g["label"] for g in mine)
                tasks = [t for g in mine for t in g.get("tasks") or []]
                done_lines = "".join(f"\n- {t}" for t in tasks)
                self._order_update(
                    outcome, actor,
                    requester_msg=(
                        f"Progress on {outcome.case_reference} ({outcome.title}): {team} has finished their part."
                        + (f"{done_lines}" if done_lines else "")
                        + (f"\nNote from the team: {note}" if note else "")
                        + f"\n\nStill in progress: {', '.join(pending)}."
                    ),
                    admin_headline=f"{team} done - still waiting on {', '.join(pending)}" + (f" ({note})" if note else ""),
                )
                return {"applied": True, "action": "team_done", "pending": pending}
            _set_facts(self.session, outcome, team_groups=groups)

        if facts.get("agent_category") == "onboarding" and not facts.get("handover_check_at"):
            joining = joining_day(facts)
            if joining and joining > _ist_now().date():
                return self._ready_for_joining(outcome, actor, note, files, groups, joining)

        hint = evidence_hint(facts.get("agent_category"))
        if files or len(note.split()) >= 3:
            self._record_evidence(outcome, note, actor, files)
            evidence = "provided"
        elif actor == admin:
            evidence = "admin_confirmed"
        elif not hint or facts.get("knowledge_gap"):
            evidence = "not_required"
        else:
            evidence = "missing"
        self._resolve(outcome, note=note, actor=actor, evidence=evidence)
        days = max(1, round(float(getattr(self.settings, "desk_autoclose_hours", 72) or 72) / 24))
        if facts.get("knowledge_gap") and note:
            self._tell_requester(outcome, f"About your question ({outcome.case_reference}): {note}")
            self._draft_knowledge(outcome, note, actor)
        else:
            team, _ = self._team_of(outcome, actor)
            self._order_update(
                outcome, actor,
                requester_msg=(
                    f"Good news - {outcome.case_reference} ({outcome.title}) has been taken care of."
                    + (f"\nNote from {team}: {note}" if note else "")
                    + f"\n\nIf anything is still not right, just reply \"not fixed\" and I'll reopen it. "
                    f"Otherwise it closes automatically in {days} day{'s' if days != 1 else ''}."
                ),
                admin_headline=(f"Completed - {team} finished the last part" if len(groups) > 1 else f"Completed by {team}")
                + (f": {note}" if note else ""),
            )
        if evidence == "missing":
            self.comms.send_case_update(
                outcome=outcome,
                communication_type=CommunicationType.ACTION_REQUIRED.value,
                body=self._briefing(
                    outcome,
                    f"Thanks for completing this. To close it as verified, please reply with {hint} "
                    "(or attach a photo).",
                    kind="info",
                ),
                recipients=[actor],
                action_label="PROOF NEEDED",
                subject_hint="Completion note needed",
                suppress_fingerprint=f"proof:{outcome.outcome_id}:{facts.get('reopen_count') or 0}",
            )
        if facts.get("knowledge_gap") and note and admin and actor != admin and not digest_mode():
            self._notify_admin(outcome, kind="info", headline=f"Answered by {actor}")
        return {"applied": True, "action": "done", "evidence": evidence}

    def _ready_for_joining(self, outcome: Outcome, actor: str, note: str, files: list[str], groups: list[dict],
                           joining: date) -> dict:
        """Everything is prepared but the joiner hasn't arrived: hold the case open for the day-one handover."""
        facts = outcome.facts or {}
        if note or files:
            self._record_evidence(outcome, note, actor, files)
        if facts.get("agent_stage") == READY_FOR_JOINING:
            return {"applied": True, "action": "ready_noted"}
        for g in groups:
            if not g.get("done"):
                g["done"] = True
                g["note"] = (note or "")[:300] or None
        who, when = _joiner(facts), _day_label(joining)
        outcome.due_at = _ist_to_utc(datetime.combine(joining, time(18, 0)))
        self.session.add(outcome)
        _set_facts(self.session, outcome, team_groups=groups, agent_stage=READY_FOR_JOINING, ready_at=utcnow().isoformat(),
                   joining_on=joining.isoformat(), progress_note=f"Everything ready - handover on {when}")
        working = [g for g in groups if not g.get("raised_by_team")]
        lines = [
            f"- {g['label']}: {'; '.join(g.get('tasks') or []) or 'their part'}" + (f" (note: {g['note']})" if g.get("note") else "")
            for g in working
        ]
        self._order_update(
            outcome, actor,
            requester_msg=(
                f"Everything for {who} is ready ahead of the joining day ({when}) - {outcome.case_reference}:\n"
                + "\n".join(lines)
                + f"\n\nOn {when} I'll ask the teams to confirm they've handed everything over to {who}, "
                "and I'll confirm here once that's done."
            ),
            admin_headline=f"Ready for joining on {when} - handover check on the day" + (f" ({note})" if note else ""),
        )
        return {"applied": True, "action": "ready_for_joining", "joining_on": joining.isoformat()}

    def start_handover_check(self, outcome: Outcome, now: Optional[datetime] = None) -> bool:
        """On the joining day, ask each team to confirm the handover; the case resolves once they all do."""
        facts = outcome.facts or {}
        joining = joining_day(facts)
        now = now or utcnow()
        local = now + timedelta(hours=5, minutes=30)
        if (facts.get("agent_stage") != READY_FOR_JOINING or facts.get("handover_check_at") or not joining
                or local < datetime.combine(joining, _HANDOVER_CHECK_AT)):
            return False
        who = _joiner(facts)
        groups = [dict(g) for g in facts.get("team_groups") or []]
        working = [g for g in groups if not g.get("raised_by_team")]
        for g in working:
            g["prep_note"], g["note"], g["done"] = g.get("note"), None, False
        outcome.due_at = max(_ist_to_utc(datetime.combine(joining, time(18, 0))), now + timedelta(hours=4))
        self.session.add(outcome)
        _set_facts(self.session, outcome, team_groups=groups, agent_stage="DISPATCHED", handover_check_at=now.isoformat(),
                   dispatched_at=now.isoformat(), sla_reminded_at=None, sla_escalated_at=None, progress_note=None)
        for g in working:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type=CommunicationType.ACTION_REQUIRED.value,
                body=self._briefing(
                    outcome,
                    f"{who} joins today. Please hand everything over and reply \"handed over\" "
                    "(or \"issue: <what is blocking>\").",
                    kind="work", tasks=g.get("tasks"),
                ),
                recipients=list(g.get("recipients") or []),
                action_label="WORK ORDER",
                subject_hint=f"Handover today - {g['label']}",
                suppress_fingerprint=f"handover:{outcome.outcome_id}:{g['label']}",
            )
        names = ", ".join(g["label"] for g in working) or "the teams"
        self._tell_requester(
            outcome,
            f"{who} joins today ({outcome.case_reference}). I've asked {names} to confirm the handover "
            "and will update you here once it's done.",
        )
        return True

    def _draft_knowledge(self, outcome: Outcome, answer: str, actor: str) -> None:
        """A human's answer becomes a draft FAQ; the AI only uses it once an admin approves it (governed learning)."""
        from app.models.company import KnowledgeEntry

        question = str(((outcome.facts or {}).get("details") or {}).get("question") or outcome.title)
        key = f"learned_{outcome.case_reference or outcome.outcome_id}".lower().replace("-", "_")
        entry = self.session.exec(
            select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == self.tenant_id, KnowledgeEntry.key == key)
        ).first() or KnowledgeEntry(tenant_id=self.tenant_id, key=key, title="", content="")
        entry.title = re.sub(r"^Question:\s*", "", outcome.title or question)[:200]
        entry.content = f"Q: {question.strip()[:600]}\nA: {answer.strip()[:1500]}\n(answered by {actor})"
        entry.section = "draft"
        entry.is_active = False
        entry.updated_at = utcnow()
        self.session.add(entry)
        self.session.flush()

    def _recategorise(self, outcome: Outcome, value: str, actor: str) -> dict:
        facts = outcome.facts or {}
        new = normalize_category(value)
        old = facts.get("agent_category") or "general"
        if new == old:
            return {"applied": False, "action": "recategorise", "note": "already that type"}
        before = route_for_case(self.session, self.tenant_id, facts)
        route = route_for(self.session, self.tenant_id, new)
        _set_facts(self.session, outcome, agent_category=new, category_label=label_for(new),
                   department_code=route.department_code, department_name=route.department_name,
                   department_override=None)
        outcome.category = new.upper()[:40]
        self.session.add(outcome)
        ticket = self._ticket(outcome)
        if ticket:
            ticket.category = new
            ticket.department_code = route.department_code
            self.session.add(ticket)
        add_correction(self.session, outcome, "recategorised", actor, before=old, after=new,
                       from_team=before.department_code, to_team=route.department_code)
        return self._handover(outcome, route, before, f"Re-routed to you by {actor} (now {label_for(new)})")

    def _reroute(self, outcome: Outcome, value: str, actor: str) -> dict:
        facts = outcome.facts or {}
        dept = find_department(self.session, self.tenant_id, value)
        if dept is None:
            return {"applied": False, "action": "reroute", "note": f"no team called {value}"}
        before = route_for_case(self.session, self.tenant_id, facts)
        if dept.code == before.department_code:
            return {"applied": False, "action": "reroute", "note": "already with that team"}
        _set_facts(self.session, outcome, department_override=dept.code, department_code=dept.code, department_name=dept.name)
        route = route_for_case(self.session, self.tenant_id, outcome.facts or {})
        ticket = self._ticket(outcome)
        if ticket:
            ticket.department_code = dept.code
            self.session.add(ticket)
        add_correction(self.session, outcome, "rerouted", actor, category=facts.get("agent_category"),
                       before=before.department_code, after=dept.code)
        return self._handover(outcome, route, before, f"Re-routed to you by {actor}")

    def _handover(self, outcome: Outcome, route: Route, before: Route, headline: str) -> dict:
        if (outcome.facts or {}).get("agent_stage") in {"DISPATCHED", "IN_PROGRESS", "BLOCKED"}:
            self._ticket_status(outcome, "ASSIGNED", assignee=route.recipients[0] if route.recipients else None)
            self._work_order(outcome, route, headline=headline, final=False, fingerprint_extra=f"handover:{route.department_code}")
            if before.recipients and set(before.recipients) != set(route.recipients):
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type=CommunicationType.INFORMATION_ONLY.value,
                    body=self._briefing(outcome, f"Moved to {route.department_name} - no action needed from you.", kind="info"),
                    recipients=before.recipients,
                    action_label="REASSIGNED",
                    subject_hint="Moved to another team",
                    suppress_fingerprint=f"moved:{route.department_code}",
                )
        return {"applied": True, "action": "rerouted", "team": route.department_name}

    def _reprioritise(self, outcome: Outcome, value: str, actor: str) -> dict:
        from app.agent.priority import normalize_priority

        new = normalize_priority(value)
        old = outcome.priority or "MEDIUM"
        if new == old:
            return {"applied": False, "action": "priority", "note": "already that priority"}
        facts = outcome.facts or {}
        route = route_for_case(self.session, self.tenant_id, facts)
        hours = sla_hours_for(new, route.sla_hours)
        outcome.priority = new
        start = facts.get("dispatched_at")
        if start:
            outcome.due_at = datetime.fromisoformat(start) + timedelta(hours=hours)
        self.session.add(outcome)
        _set_facts(self.session, outcome, sla_hours=hours, priority_reason=f"set by {actor}",
                   sla_reminded_at=None, sla_escalated_at=None)
        ticket = self._ticket(outcome)
        if ticket:
            ticket.priority = new
            ticket.sla_due_at = outcome.due_at
            self.session.add(ticket)
        add_correction(self.session, outcome, "priority_changed", actor, before=old, after=new)
        return {"applied": True, "action": "priority", "priority": new}

    def _resolve(self, outcome: Outcome, *, note: str, actor: str, evidence: str) -> None:
        _set_facts(self.session, outcome, agent_stage="RESOLVED", resolution_note=note or "Completed", resolved_by=actor,
                   resolved_at=utcnow().isoformat(), evidence_status=evidence)
        if outcome.status != OutcomeStatus.RESOLVED.value:
            outcome.status = OutcomeStatus.RESOLVED.value
            self.session.add(outcome)
        self._ticket_status(outcome, "RESOLVED")

    def _record_evidence(self, outcome: Outcome, note: str, actor: str, files: list[str]) -> None:
        self.session.add(
            Evidence(
                tenant_id=self.tenant_id,
                outcome_id=outcome.outcome_id,
                evidence_type="ATTACHMENT" if files else "COMPLETION_NOTE",
                record_ref=", ".join(files)[:500] or None,
                description=(note or "")[:1000] or None,
                metadata_json={"by": actor, "files": files},
            )
        )
        self.session.flush()

    def _add_evidence(self, outcome: Outcome, note: str, actor: str, files: list[str]) -> dict:
        """Proof sent after the job was marked done: the case can now close as verified."""
        if not (files or len((note or "").split()) >= 2):
            return {"applied": False, "action": "evidence", "note": "no usable proof in the reply"}
        self._record_evidence(outcome, note, actor, files)
        _set_facts(self.session, outcome, evidence_status="provided",
                   resolution_note=note[:400] if note else (outcome.facts or {}).get("resolution_note"))
        return {"applied": True, "action": "evidence"}

    def _approved_text(self, outcome: Outcome, result: dict) -> str:
        status = result.get("status")
        if status == "issued":
            passes = ", ".join(f"{p['name']} ({p['pass_code']})" for p in result.get("passes", []))
            return f"{outcome.case_reference} is approved and your visitors are registered: {passes}."
        facts = outcome.facts or {}
        team = ", ".join(facts.get("teams") or []) if status == "dispatched" and facts.get("team_groups") else ""
        team = team or facts.get("department_name") or "the team"
        return f"{outcome.case_reference} ({outcome.title}) is approved and assigned to {team}. I'll update you once it's done."

    def _decide_approval(self, outcome: Outcome, decision: str, actor: str, reason: str = "") -> None:
        for apr in self.session.exec(
            select(Approval).where(Approval.outcome_id == outcome.outcome_id, Approval.decision == "PENDING")
        ).all():
            apr.decision = decision
            apr.reason = reason or None
            apr.decided_at = utcnow()
            self.session.add(apr)
        self.audit.record(
            tenant_id=self.tenant_id,
            actor=actor,
            action=AuditAction.HUMAN_OVERRIDE,
            entity_type="Outcome",
            entity_id=outcome.outcome_id,
            after={"approval": decision, "reason": reason},
            correlation_id=outcome.outcome_id,
        )

    def _team_of(self, outcome: Outcome, actor: str) -> tuple[str, list[str]]:
        """Which team (and its tasks) a reply came from, so updates say who did what."""
        actor = (actor or "").lower()
        for g in (outcome.facts or {}).get("team_groups") or []:
            if actor in {r.lower() for r in g.get("recipients") or []}:
                return g.get("label") or "The team", list(g.get("tasks") or [])
        facts = outcome.facts or {}
        return facts.get("department_name") or "The team", []

    def _order_update(self, outcome: Outcome, actor: str, *, requester_msg: str, admin_headline: str) -> None:
        """Every team update reaches the requester (the raising team) and the admin."""
        self._tell_requester(outcome, requester_msg)
        admin = self._admin()
        if not admin or digest_mode() or (actor or "").lower() == admin.lower():
            return
        if (outcome.requester_email or "").lower() == admin.lower():
            return
        self._notify_admin(outcome, kind="info", headline=admin_headline)

    def _tell_requester(self, outcome: Outcome, message: str) -> None:
        if not outcome.requester_email:
            return
        name = resolve_requester_name(self.session, outcome=outcome)
        first = name.split(" ")[0] if name and name not in {"there", "team"} else ""
        body = f"{'Hi ' + first + ',' if first else 'Hi,'}\n\n{message.strip()}\n\n{self.settings.mail_signature}\n"
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=CommunicationType.INFORMATION_ONLY.value,
            body=body,
            recipients=[outcome.requester_email],
            action_label="UPDATE",
            subject_hint=outcome.title,
            suppress_fingerprint=f"tell:{hash(message)}",
        )
