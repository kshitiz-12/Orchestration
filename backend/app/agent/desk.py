"""Executes the AI admin's decision: cases, tickets, passes, routing, approvals and replies.

The model proposes; this module decides what actually happens under the risk policy and only
tells the requester what really happened.
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.agent.company_seed import is_placeholder
from app.agent.digest import digest_mode
from app.agent.directory import Route, catalogue, handles_category, knowledge_text, route_for
from app.agent.playbooks import (
    LEGACY_CATEGORIES,
    assess_risk,
    case_prefix,
    has_playbook,
    missing_questions,
    normalize_category,
    playbook_for,
)
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
from app.models.outcome import Approval, Outcome
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


def is_service_case(outcome: Optional[Outcome]) -> bool:
    return bool(outcome) and outcome.template_code == SERVICE_TEMPLATE


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
    for key, value in details.items():
        if value in (None, "", [], {}):
            continue
        shown = ", ".join(_as_list(value)) if isinstance(value, list) else str(value)
        lines.append(f"- {key.replace('_', ' ').capitalize()}: {shown}")
    return lines


def _normalize_details(details: dict) -> dict:
    out = dict(details or {})
    for src in ("visitors", "visitor", "guests", "guest_names", "names"):
        if src in out and "visitor_names" not in out:
            out["visitor_names"] = out.pop(src)
    for src in ("vehicle_number", "vehicle", "vehicles", "car_number"):
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
        )
        hint = None if self.agent.can_reason else self._legacy_hint(event, current)
        decision = self.agent.decide(payload, heuristic_hint=hint)
        self._record_decision(event, conversation, decision)

        mine, legacy = self._split(decision, current, cases)
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
        self, decision: AgentDecision, current: Optional[Outcome], cases: list[Outcome]
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
                if target is not None and is_service_case(target):
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
            return self._close(target, "Requester confirmed it is done.")
        return self._update(target, intent, event, decision)

    def _new_request(
        self,
        intent: AgentIntent,
        event: RawEmailEvent,
        conversation: Conversation,
        decision: AgentDecision,
        *,
        has_legacy_case: bool,
    ) -> dict:
        category = normalize_category(intent.category)
        route = route_for(self.session, self.tenant_id, category)
        details = _normalize_details(intent.details)
        requester = (event.sender or "").lower()
        person = self.session.exec(select(Person).where(Person.email == requester)).first()
        ref = self.engine.next_case_reference(case_prefix(category))
        title = (intent.summary or category.replace("_", " ").capitalize())[:200]
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
            priority=intent.priority,
            facts={
                "agent_case": True,
                "agent_category": category,
                "details": details,
                "department_code": route.department_code,
                "department_name": route.department_name,
                "raw_request": strip_for_ai(event.body_text or "")[:2000],
            },
            business_event_id=event.event_id,
            conversation_id=conversation.conversation_id,
            due_at=utcnow() + timedelta(hours=route.sla_hours),
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
            priority=intent.priority,
            department_code=route.department_code,
            requester_email=requester,
            sla_due_at=utcnow() + timedelta(hours=route.sla_hours),
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
        if (self.settings.admin_fyi_level or "").strip().lower() == "all" and admin and admin not in route.recipients:
            self._notify_admin(outcome, kind="info", headline="New request opened")
        return self._progress(outcome, intent, route, decision, text=event.body_text or "")

    def _progress(self, outcome: Outcome, intent: AgentIntent, route: Route, decision: AgentDecision, *, text: str) -> dict:
        """Move a case forward as far as policy allows: ask, get approval, or do it."""
        facts = outcome.facts or {}
        category = facts.get("agent_category") or "general"
        details = facts.get("details") or {}
        missing = list(dict.fromkeys(intent.missing))
        # A free-text answer (rules fallback can't parse it) goes to the team rather than asking again.
        if not details.get("requester_note"):
            for question in missing_questions(category, details):
                if question not in missing:
                    missing.append(question)
        if missing:
            _set_facts(self.session, outcome, agent_stage="AWAITING_INFO", missing=missing)
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
                )
                self._ticket_status(outcome, "AWAITING_APPROVAL")
                self._notify_admin(outcome, kind="decision", headline=f"Needs your approval - {risk.reason}")
            return {"intent": intent, "status": "awaiting_approval", "outcome": outcome, "reason": risk.reason}
        return self._dispatch(outcome, intent, route)

    def _dispatch(self, outcome: Outcome, intent: Optional[AgentIntent], route: Route) -> dict:
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
            teams = [route] + [route_for(self.session, self.tenant_id, c) for c in playbook_for(category).fan_out]
            by_inbox: dict[tuple[str, ...], list[Route]] = {}
            for team in teams:
                group = by_inbox.setdefault(tuple(team.recipients), [])
                if all(t.department_code != team.department_code for t in group):
                    group.append(team)
            names = [t.department_name for group in by_inbox.values() for t in group]
            for group in by_inbox.values():
                label = " + ".join(t.department_name for t in group)
                self._work_order(
                    outcome, group[0], headline=f"{playbook_for(category).label} - {label} tasks",
                    final=False, fingerprint_extra=label,
                )
            day1 = self._day_one_note(outcome) if category == "onboarding" else ""
            _set_facts(self.session, outcome, agent_stage="DISPATCHED", missing=[], teams=names, day1_note=day1 or None)
            self._ticket_status(outcome, "ASSIGNED", assignee=route.recipients[0] if route.recipients else None)
            return {"intent": intent, "status": "dispatched", "outcome": outcome, "team": ", ".join(names), "day1": day1}
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
        self._work_order(outcome, route, headline="New work order", final=False)
        return {"intent": intent, "status": "dispatched", "outcome": outcome, "team": route.department_name}

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
        route = route_for(self.session, self.tenant_id, facts.get("agent_category") or "general")
        if stage == "AWAITING_INFO":
            return self._progress(outcome, intent, route, decision, text=event.body_text or "")
        if stage in {"DISPATCHED", "AWAITING_APPROVAL"} and intent.details:
            self._work_order(outcome, route, headline="Update from requester", final=False, fingerprint_extra=event.event_id)
        return {"intent": intent, "status": "updated", "outcome": outcome}

    def _cancel(self, outcome: Outcome, intent: AgentIntent) -> dict:
        outcome.status = OutcomeStatus.CANCELLED.value
        outcome.closed_at = utcnow()
        _set_facts(self.session, outcome, agent_stage="CANCELLED")
        self._ticket_status(outcome, "CANCELLED")
        for vp in self.session.exec(select(VisitorPass).where(VisitorPass.outcome_id == outcome.outcome_id)).all():
            vp.status = "CANCELLED"
            self.session.add(vp)
        route = route_for(self.session, self.tenant_id, (outcome.facts or {}).get("agent_category") or "general")
        self._work_order(outcome, route, headline="Cancelled by requester - no action needed", final=True)
        return {"intent": intent, "status": "cancelled", "outcome": outcome}

    def _close(self, outcome: Outcome, note: str) -> dict:
        outcome.status = OutcomeStatus.CLOSED.value
        outcome.closed_at = utcnow()
        _set_facts(self.session, outcome, agent_stage="CLOSED", resolution_note=note)
        self._ticket_status(outcome, "CLOSED")
        return {"intent": None, "status": "closed", "outcome": outcome}

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

    def _briefing(self, outcome: Outcome, headline: str, *, kind: str) -> str:
        facts = outcome.facts or {}
        name = resolve_requester_name(self.session, outcome=outcome)
        lines = [f"{outcome.case_reference} - {outcome.title}", "", headline, ""]
        lines.append(f"Requester: {name} <{outcome.requester_email}>" if name not in {"there", "team"} else f"Requester: {outcome.requester_email}")
        lines.append(f"Type: {(facts.get('agent_category') or 'general').replace('_', ' ')}")
        if facts.get("department_name"):
            lines.append(f"Team: {facts['department_name']}")
        vendor = self._preferred_vendor(facts.get("agent_category") or "")
        if vendor:
            lines.append(f"Preferred vendor: {vendor}")
        detail_lines = _details_lines({k: v for k, v in (facts.get("details") or {}).items() if k != "description"})
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
            lines.append('Reply "done" when finished (add a note if you like), "assign to <email>", '
                         '"tell requester: <message>", "change <detail> to <value>", "close" or "cancel".')
        return "\n".join(lines) + "\n"

    @staticmethod
    def _day_one_note(outcome: Outcome) -> str:
        d = (outcome.facts or {}).get("details") or {}
        who = d.get("employee_name") or d.get("joiner_name") or d.get("name") or "the new joiner"
        when = d.get("joining_date") or d.get("start_date") or d.get("date") or "the joining date"
        where = d.get("location") or d.get("office") or "the office reception"
        return (
            f"Day-1 note for {who} (you can forward this):\n"
            f"- Report on {when} at {where} by 9:30 AM with a government photo ID.\n"
            "- HR will meet you at reception for joining formalities.\n"
            "- IT will hand over your laptop and login; Facilities will show you your desk and issue your access card."
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
        self, outcome: Outcome, route: Route, *, headline: str, final: bool, fingerprint_extra: str = ""
    ) -> None:
        if not route.recipients:
            return
        note = ""
        if route.redirected_to_admin:
            note = f"(No {route.department_name} contact set yet - sent to you. Add it in Company setup.)"
        body = self._briefing(outcome, f"{headline}\n{note}".strip(), kind="info" if final else "work")
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

    def _notify_admin(self, outcome: Outcome, *, kind: str, headline: str) -> None:
        admin = self._admin()
        if not admin:
            return
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=CommunicationType.APPROVAL_REQUIRED.value if kind == "decision" else CommunicationType.INFORMATION_ONLY.value,
            body=self._briefing(outcome, headline, kind=kind),
            recipients=[admin],
            action_label="OPS DECISION" if kind == "decision" else "OPS UPDATE",
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
                if r.get("day1") and "Day-1 note" not in draft:
                    draft += "\n\n" + r["day1"]
            return draft
        if all(r["status"] == "small_talk" for r in results) and not draft:
            return ""
        return self._template_reply(results, name, split=split)

    @staticmethod
    def _draft_is_grounded(draft: str, mine: list[AgentIntent], results: list[dict]) -> bool:
        low = draft.lower()
        for r in results:
            intent = r.get("intent")
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
                lines.append(f"I've logged {what} as {ref} and assigned it to {team}. I'll let you know once it's done.")
                if r.get("day1"):
                    lines += ["", r["day1"]]
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
    def apply_team_reply(self, outcome: Outcome, text: str, actor: str) -> dict:
        """Admin or department replying on a desk case in plain words."""
        body = (text or "").strip()
        low = body.lower()
        facts = outcome.facts or {}
        route = route_for(self.session, self.tenant_id, facts.get("agent_category") or "general")
        tell = re.search(r"(?:tell|inform|message|reply to)\s+(?:the\s+)?requester\s*[:\-,]?\s*(.+)", body, re.I | re.S)
        assign = re.search(r"\bassign(?:ed)?\s+(?:it\s+)?to\s+([\w.+-]+@[\w.-]+)", body, re.I)
        if re.match(r"^\s*(?:approved?|ok(?:ay)?\s+approved?|yes,?\s+approve|go\s+ahead)\b", low):
            if facts.get("agent_stage") != "AWAITING_APPROVAL":
                return {"applied": False, "action": "approve", "note": "nothing pending approval"}
            self._decide_approval(outcome, "APPROVED", actor)
            _set_facts(self.session, outcome, admin_approved=True, approved_by=actor)
            result = self._dispatch(outcome, None, route)
            self._tell_requester(outcome, self._approved_text(outcome, result))
            return {"applied": True, "action": "approve"}
        if re.match(r"^\s*(?:reject(?:ed)?|decline[d]?|deny|denied|not\s+approved)\b", low):
            reason = re.sub(r"^\s*(?:reject(?:ed)?|decline[d]?|deny|denied|not\s+approved)\b[\s,:\-]*", "", body, flags=re.I).strip()
            self._decide_approval(outcome, "REJECTED", actor, reason)
            outcome.status = OutcomeStatus.CLOSED.value
            outcome.closed_at = utcnow()
            _set_facts(self.session, outcome, agent_stage="REJECTED", resolution_note=reason or "Not approved")
            self._ticket_status(outcome, "REJECTED")
            self._tell_requester(
                outcome,
                f"Sorry - {outcome.case_reference} ({outcome.title}) could not be approved"
                + (f": {reason}" if reason else ".") + "\n\nReply here if you'd like to discuss it.",
            )
            return {"applied": True, "action": "reject"}
        if assign:
            email = assign.group(1).lower()
            self._ticket_status(outcome, "ASSIGNED", assignee=email)
            _set_facts(self.session, outcome, assignee_email=email)
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
            self._tell_requester(outcome, tell.group(1).strip())
            return {"applied": True, "action": "message"}
        change = re.match(r"^\s*(?:change|update|set|move)\s+(?:the\s+)?(.{2,40}?)\s+to\s+(.+)$", body.splitlines()[0] if body else "", re.I)
        if change:
            field = re.sub(r"[^a-z0-9]+", "_", change.group(1).lower()).strip("_")
            value = change.group(2).strip().rstrip(".")
            details = {**(facts.get("details") or {}), field: value}
            _set_facts(self.session, outcome, details=details)
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
            self._close(outcome, f"Closed by {actor}")
            self._tell_requester(outcome, f"{outcome.case_reference} ({outcome.title}) is now closed. Reply here if you need anything else.")
            return {"applied": True, "action": "close"}
        if re.search(r"\b(?:done|fixed|resolved|completed|closed|sorted|repaired|replaced|delivered|arranged)\b", low):
            note = re.sub(r"^\s*(?:it'?s\s+)?(?:done|fixed|resolved|completed|closed)\b[\s,.:\-]*", "", body, flags=re.I).strip()
            _set_facts(self.session, outcome, agent_stage="RESOLVED", resolution_note=note or "Completed", resolved_by=actor)
            outcome.status = OutcomeStatus.RESOLVED.value
            self.session.add(outcome)
            self._ticket_status(outcome, "RESOLVED")
            self._tell_requester(
                outcome,
                f"Good news - {outcome.case_reference} ({outcome.title}) has been taken care of."
                + (f"\nNote from the team: {note}" if note else "")
                + "\n\nIf anything is still not right, just reply here and I'll reopen it.",
            )
            admin = self._admin()
            if admin and actor != admin and not digest_mode():
                self._notify_admin(outcome, kind="info", headline=f"Completed by {actor}")
            return {"applied": True, "action": "done"}
        if re.match(r"^\s*cancel", low):
            self._cancel(outcome, AgentIntent(type="cancel"))
            self._tell_requester(outcome, f"{outcome.case_reference} ({outcome.title}) has been cancelled by the admin team.")
            return {"applied": True, "action": "cancel"}
        return {"applied": False, "action": "unknown"}

    def _approved_text(self, outcome: Outcome, result: dict) -> str:
        status = result.get("status")
        if status == "issued":
            passes = ", ".join(f"{p['name']} ({p['pass_code']})" for p in result.get("passes", []))
            return f"{outcome.case_reference} is approved and your visitors are registered: {passes}."
        team = (outcome.facts or {}).get("department_name") or "the team"
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
