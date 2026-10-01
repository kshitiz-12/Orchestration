"""Everything around a booked room: cost approval, per-owner task packages, readiness, host verification,
service entry and financial closure. Mixed into ClientMeetingOrchestrator."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.meeting import MeetingStage
from app.models.org import utcnow
from app.models.outcome import Approval, Outcome, Requirement, Task
from app.services.communication import resolve_requester_name
from app.services.event_facts import (
    event_dates,
    event_kind,
    is_multi_day,
    layout_label,
    trainer_count,
    travel_needed,
)
from app.services.meeting_room import (
    catering_needed,
    external_visitor_count,
    guest_vehicle_count,
    hybrid_needed,
    presentation_needed,
    seats_needed,
)
from app.services.no_resource_flow import format_outbound_greeting
from app.services.room_booking import meeting_window, parse_meeting_date
from app.services.site_services import (
    _money,
    _qty_label,
    build_cost_plan,
    chargeable_lines,
    has_charges,
    included_note,
    only_catering_charges,
)

logger = get_logger(__name__)

IST = timedelta(hours=5, minutes=30)
COST_APPROVAL_TYPES = ("CATERING_SPEND", "EVENT_COST")
OPEN_PACKAGE = {"SENT", "ISSUE"}

# owner department code, routing category, title shown to people
PACKAGE_OWNERS = (
    ("ADMIN", "meeting_room", "Administration"),
    ("IT", "it_support", "IT / AV"),
    ("SECURITY", "visitor", "Security & Reception"),
    ("CAFETERIA", "catering", "Cafeteria"),
    ("TRAVEL", "travel", "Travel Desk"),
)
_OWNER_TASKS = {
    "ADMIN": ("HOUSEKEEPING",),
    "IT": ("AV_TEST",),
    "SECURITY": ("PREPARE_VISITORS", "ALLOCATE_PARKING"),
    "CAFETERIA": ("VENDOR_CATERING",),
    "TRAVEL": ("TRAVEL_ARRANGE",),
}

_NO_ISSUE_RE = re.compile(r"\bno\s+(?:issues?|problems?)\b", re.I)
_DONE_RE = re.compile(
    r"^\s*(?:all\s+)?(?:done|ready|set|sorted|arranged|completed?|confirmed|delivered|taken\s+care|ok(?:ay)?[,.\s]+done)\b",
    re.I,
)
_ISSUE_RE = re.compile(
    r"\b(issues?|problems?|can'?t|cannot|unable|not\s+available|unavailable|shortage|short\s+of|delay(?:ed)?|"
    r"won'?t\s+be|blocked|out\s+of\s+stock|not\s+possible)\b",
    re.I,
)
_ADMIN_PACKAGE_RE = re.compile(r"^\s*(?:all\s+)?(?:done|ready|arranged|issue\s*[:\-]|problem\s*[:\-])", re.I)
_ENTRY_OK_RE = re.compile(
    r"\b(confirm(?:ed)?|correct|as\s+planned|that'?s\s+right|all\s+delivered|fully\s+delivered|yes|looks\s+good|accurate)\b",
    re.I,
)
_ENTRY_KEYWORDS = {
    "working_lunch": r"lunch(?:es)?|meals?",
    "high_tea": r"high[\s-]?tea|snacks?",
    "catering_general": r"catering|food|meals?",
    "tea_coffee": r"tea|coffee",
    "water": r"water",
    "flight": r"flights?|air\s*tickets?",
    "hotel": r"hotel|room[\s-]?nights?|nights?",
    "local_transfer": r"transfers?|cabs?|pick\s*-?\s*ups?|drops?|trips?",
    "visitor_parking": r"parking",
    "stationery": r"print\w*|kits?|stationery",
    "standard_av": r"av\b|technician|equipment",
    "external_venue": r"venue",
}


def local_now(now: Optional[datetime] = None) -> datetime:
    """Meeting times are stored as local (IST) wall-clock times; utcnow() is naive UTC."""
    return (now or utcnow()) + IST


def fmt_local(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return re.sub(r"(?<![:\d])0(\d)", r"\1", dt.strftime("%d %b, %I:%M %p"))


def readiness_deadline(facts: dict[str, Any]) -> Optional[datetime]:
    """Everything must be ready when setup starts on the first day."""
    window = meeting_window(facts)
    return window[0] if window else None


def event_end(facts: dict[str, Any]) -> Optional[datetime]:
    days = event_dates(facts)
    window = meeting_window({**facts, "date": days[-1]} if days else facts, with_buffers=False)
    return window[1] if window else None


def _day_labels(facts: dict[str, Any]) -> list[str]:
    out = []
    for d in event_dates(facts):
        day = parse_meeting_date(d)
        out.append(day.strftime("%a %d %b") if day else str(d))
    return out


def _fp(value: Any) -> str:
    return hashlib.sha1(repr(value).encode()).hexdigest()[:12]


def approval_state(facts: dict[str, Any]) -> str:
    if facts.get("cost_rejected"):
        return "rejected"
    if facts.get("cost_approved") or facts.get("cost_auto_approved") or facts.get("catering_assigned"):
        return "approved"
    if facts.get("cost_approval_id") or facts.get("catering_approval_id"):
        return "pending"
    return "none"


def _charge_note(line: Optional[dict], state: str) -> str:
    if not line or not line.get("chargeable"):
        return ""
    if state == "pending":
        return " — on hold until cost approval (we'll confirm)"
    if state == "rejected":
        return " — cost not approved, do not arrange"
    return " — cost approved"


def _open_asks(facts: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in facts.get("open_requests") or []:
        text = str(item.get("text") if isinstance(item, dict) else item or "").strip()
        if text and text not in out:
            out.append(text[:1].upper() + text[1:])
    return out


def build_package_items(facts: dict[str, Any]) -> dict[str, list[str]]:
    """Per-owner task lists for one event. Empty list = that owner has nothing to do."""
    plan = facts.get("cost_plan") or {}
    lines = plan.get("lines") or []
    by_code = {line.get("code"): line for line in lines}
    state = approval_state(facts)
    booked = facts.get("booked_room") or {}
    room = booked.get("name") or "the room"
    seats = seats_needed(facts)
    kind = event_kind(facts)
    days = len(event_dates(facts)) or 1
    items: dict[str, list[str]] = {code: [] for code, _, _ in PACKAGE_OWNERS}

    visitors = external_visitor_count(facts)
    cars = guest_vehicle_count(facts)
    av = hybrid_needed(facts) or presentation_needed(facts) or kind == "training"
    asks = _open_asks(facts)

    # Administration: room setup, stationery, anything nobody else owns
    admin: list[str] = []
    layout = layout_label(facts)
    if layout or kind == "training" or is_multi_day(facts):
        setup = f"Set up {room}" + (f" in {layout} layout" if layout else "") + (f" for {seats}" if seats else "")
        if trainer_count(facts):
            n = trainer_count(facts)
            setup += f" (includes {n} trainer seat{'s' if n > 1 else ''})"
        if is_multi_day(facts):
            setup += " on each day: " + ", ".join(_day_labels(facts))
        admin.append(setup)
    if "stationery" in by_code:
        admin.append(by_code["stationery"]["name"] + _charge_note(by_code["stationery"], state))
    if "water" in by_code:
        admin.append("Drinking water in the room")
    if kind == "training" and str(facts.get("attendance_capture") or "").lower() not in {"no", "none"}:
        admin.append("Attendance sheet / capture at the entrance")
    admin += asks
    beyond_plain_room = bool(
        admin or catering_needed(facts) or visitors or av or travel_needed(facts) or kind == "external"
    )
    if beyond_plain_room:
        admin += ["Final room inspection before setup time", f"Clean and reset {room} after the meeting"]
        items["ADMIN"] = admin

    if av:
        it: list[str] = []
        if hybrid_needed(facts):
            platform = "Microsoft Teams" if "team" in str(facts.get("hybrid_av") or "").lower() else "video call"
            it.append(f"Video call set up ({platform})")
        if presentation_needed(facts) or kind == "training":
            it.append("Display / projector working")
        if kind == "training":
            it += ["Trainer laptop connected and tested", "Microphone for the trainer"]
        if str(facts.get("recording") or "").lower() == "yes":
            it.append("Record the session")
        premium_av = by_code.get("standard_av")
        if premium_av and premium_av.get("chargeable"):
            it.append("Premium AV support" + _charge_note(premium_av, state))
        deadline = readiness_deadline(facts)
        it.append(f"AV test done by {fmt_local(deadline)}" if deadline else "AV test before the meeting")
        items["IT"] = it

    security: list[str] = []
    if visitors:
        names = str(facts.get("visitor_details") or "").strip()
        security.append(f"Visitor passes for {visitors}" + (f": {names}" if names else ""))
        security.append(f"Reception to receive guests and guide them to {room}")
    if cars:
        numbers = str(facts.get("vehicle_numbers") or "").strip()
        security.append(
            f"Reserve {cars} visitor parking slot{'s' if cars > 1 else ''}"
            + (f": {numbers}" if numbers else "")
            + _charge_note(by_code.get("visitor_parking"), state)
        )
    items["SECURITY"] = security

    cafeteria: list[str] = []
    for line in lines:
        if line.get("owner") != "CAFETERIA":
            continue
        count = int(plan.get("headcount") or seats or 0)
        qty = f"{count} people" + (f" x {days} days" if days > 1 else "")
        cafeteria.append(f"{line['name']}: {qty}" + _charge_note(line, state))
    if not cafeteria and catering_needed(facts):
        cafeteria.append(f"Catering: {facts.get('catering')}")
    if cafeteria:
        notes = [str(n).strip() for n in facts.get("catering_notes") or [] if str(n).strip()]
        if notes:
            cafeteria.append(f'As the organiser asked: "{notes[-1]}"')
        if facts.get("dietary"):
            cafeteria.append(f"Dietary: {facts['dietary']}")
    items["CAFETERIA"] = cafeteria

    travel: list[str] = []
    for code in ("flight", "hotel", "local_transfer"):
        line = by_code.get(code)
        if line:
            note = f" ({line['note']})" if line.get("note") else ""
            travel.append(f"{line['name']}: {_qty_label(line)}{note}" + _charge_note(line, state))
    if travel:
        details = str(facts.get("traveller_details") or facts.get("trainer_details") or "").strip()
        travel.append(f"Travellers: {details}" if details else "Traveller names and itinerary: requested from the organiser")
    items["TRAVEL"] = travel
    return items


def package_text(packages: list[dict[str, Any]]) -> str:
    blocks = []
    for pkg in packages:
        blocks.append(f"{pkg['title']}:\n" + "\n".join(f"- {i}" for i in pkg.get("items") or []))
    return "\n\n".join(blocks)


def _actual_qty(text: str, code: str) -> Optional[float]:
    kw = _ENTRY_KEYWORDS.get(code)
    if not kw:
        return None
    m = re.search(rf"\b(?:{kw})\D{{0,15}}?(\d+(?:\.\d+)?)", text, re.I) or re.search(
        rf"(\d+(?:\.\d+)?)\s*(?:[a-z]+\s+){{0,2}}?(?:{kw})", text, re.I
    )
    return float(m.group(1)) if m else None


class EventServicesMixin:
    """Needs: session, tenant_id, engine, comms, admin_ops, _save_facts, _complete_task, _na_task."""

    session: Session
    tenant_id: str

    # ---------- shared
    @staticmethod
    def _event_over(facts: dict[str, Any], now: Optional[datetime] = None) -> bool:
        end = event_end(facts)
        return bool(end and local_now(now) >= end)

    def _task(self, outcome: Outcome, code: str) -> Optional[Task]:
        return self.session.exec(select(Task).where(Task.outcome_id == outcome.outcome_id, Task.code == code)).first()

    def _requirement(self, outcome: Outcome, code: str) -> Optional[Requirement]:
        return self.session.exec(
            select(Requirement).where(Requirement.outcome_id == outcome.outcome_id, Requirement.code == code)
        ).first()

    def _pending_cost_approvals(self, outcome: Outcome) -> list[Approval]:
        return list(
            self.session.exec(
                select(Approval).where(
                    Approval.outcome_id == outcome.outcome_id,
                    Approval.decision == "PENDING",
                    Approval.approval_type.in_(COST_APPROVAL_TYPES),  # type: ignore[attr-defined]
                )
            ).all()
        )

    def _mail_requester(self, outcome: Outcome, *, label: str, lines: list[str], fingerprint: str,
                        ctype: str = "INFORMATION_ONLY", hint: Optional[str] = None) -> None:
        if not outcome.requester_email:
            return
        name = resolve_requester_name(self.session, outcome=outcome)
        body = f"{format_outbound_greeting(name)}\n\n" + "\n\n".join(b for b in lines if b)
        self.comms.send_case_update(
            outcome=outcome,
            communication_type=ctype,
            body=body + f"\n\nCase: {outcome.case_reference}",
            recipients=[outcome.requester_email],
            action_label=label,
            subject_hint=hint or outcome.summary or label.title(),
            suppress_fingerprint=fingerprint,
        )

    # ---------- cost plan + approval (only the chargeable portion)
    def _run_costs(self, outcome: Outcome, facts: dict, *, notify_admin: bool = True) -> None:
        from app.services.catering import catering_quote

        plan = build_cost_plan(self.session, self.tenant_id, facts, requester_email=outcome.requester_email)
        facts["cost_plan"] = plan
        if catering_needed(facts):
            base = catering_quote(self.session, self.tenant_id, seats_needed(facts) or 1)
            cater = [line for line in plan["lines"] if line.get("owner") == "CAFETERIA" and line.get("chargeable")]
            if cater:
                amounts = [line.get("amount") for line in cater]
                base.update(
                    rate=cater[0].get("rate"),
                    rate_source=cater[0].get("rate_source"),
                    amount_ex_tax=round(sum(amounts), 2) if all(isinstance(a, (int, float)) for a in amounts) else None,
                )
            else:
                base.update(amount_ex_tax=0.0, included=True)
            facts["catering_quote"] = base
        self._save_facts(outcome, {**(outcome.facts or {}), **facts})

        if not catering_needed(facts):
            self._na_task(outcome, "VENDOR_CATERING")
        if not has_charges(plan):
            for code in ("CATERING_APPROVAL", "SERVICE_ENTRY", "INVOICE_VALIDATE", "INVOICE_POST", "INVOICE_PAY"):
                self._na_task(outcome, code)
            if catering_needed(facts):
                self._complete_task(outcome, "VENDOR_CATERING", "system", "Included site service — cafeteria informed")
            return

        approval_type = "CATERING_SPEND" if only_catering_charges(plan) else "EVENT_COST"
        limit = float(get_settings().catering_auto_approve_limit or 0)
        total = float(plan.get("chargeable_total") or 0)
        if limit > 0 and not plan.get("quote_pending") and total <= limit:
            facts["catering_auto_approved"] = True
            facts["cost_auto_approved"] = True
            self._save_facts(outcome, {**(outcome.facts or {}), **facts})
            self.on_cost_approved(outcome)
            return

        task = self._task(outcome, "CATERING_APPROVAL")
        approval = self.engine.request_approval(  # type: ignore[attr-defined]
            outcome=outcome,
            approval_type=approval_type,
            approver_role="MANAGER",
            payload={
                **(facts.get("catering_quote") or {}),
                "cost_plan": plan,
                "chargeable_total": total,
                "currency": plan.get("currency"),
            },
            task_id=task.task_id if task else None,
        )
        if task:
            task.status = "APPROVAL_PENDING"
            task.title = "Obtain cost approval (chargeable items only)"
            self.session.add(task)
        facts["cost_approval_id"] = approval.approval_id
        facts["catering_approval_id"] = approval.approval_id
        facts["vendor_sla"] = {"acceptance_minutes": 30, "status": "PENDING_ASSIGNMENT"}
        self._save_facts(outcome, {**(outcome.facts or {}), **facts})
        approver = (plan.get("cost_centre") or {}).get("approver_email")
        # On first booking the admin sees this approval inside the booking-confirmed mail.
        self.admin_ops.action_approval(  # type: ignore[attr-defined]
            outcome,
            approval_type=approval_type,
            facts=dict(outcome.facts or facts),
            include_admin=notify_admin,
            extra_approvers=[approver] if approver else None,
        )

    def _requote_costs(self, outcome: Outcome) -> None:
        for approval in self._pending_cost_approvals(outcome):
            approval.decision = "SUPERSEDED"
            approval.decided_at = utcnow()
            self.session.add(approval)
        facts = dict(outcome.facts or {})
        for key in ("catering_assigned", "cost_approved", "cost_auto_approved", "catering_auto_approved",
                    "cost_approval_id", "catering_approval_id", "cost_rejected"):
            facts.pop(key, None)
        self._save_facts(outcome, facts)
        self._run_costs(outcome, facts)

    def on_cost_approved(self, outcome: Outcome) -> None:
        facts = dict(outcome.facts or {})
        quote = facts.get("catering_quote") or {}
        facts["cost_approved"] = True
        facts["vendor_sla"] = {
            **(facts.get("vendor_sla") or {}),
            "status": "ASSIGNED",
            "assigned_at": utcnow().isoformat(),
            "acceptance_due_minutes": 30,
        }
        if catering_needed(facts):
            facts["catering_assigned"] = True
        self._save_facts(outcome, facts)
        self._complete_task(outcome, "CATERING_APPROVAL", "system", "Cost approved (chargeable items)")
        if catering_needed(facts):
            self._complete_task(
                outcome,
                "VENDOR_CATERING",
                "system",
                f"Assigned {quote.get('vendor') or 'caterer (ops to confirm)'}"
                + (f" for {quote.get('currency') or 'INR'} {quote['amount_ex_tax']}" if quote.get("amount_ex_tax") else ""),
            )
        for code in ("SERVICE_ENTRY", "INVOICE_VALIDATE", "INVOICE_POST", "INVOICE_PAY"):
            t = self._task(outcome, code)
            if t and t.status in {"NOT_STARTED", "CANCELLED", "CLOSED"} and t.resolution != "Financial close":
                t.status = "ASSIGNED"
                t.resolution = None
                self.session.add(t)
        req = self._requirement(outcome, "INVOICE")
        if req:
            req.applicability = "REQUIRED"
            req.is_mandatory = True
            req.status = "ACTION_PENDING"
            self.session.add(req)
        if facts.get("task_packages"):
            self._dispatch_packages(outcome, reason="approved")
        self._maybe_send_ready(outcome)

    def on_catering_approved(self, outcome: Outcome) -> None:
        self.on_cost_approved(outcome)

    def on_approval_decided(self, outcome: Outcome, approval: Approval, *, approved: bool, note: str = "") -> None:
        if approval.approval_type not in COST_APPROVAL_TYPES:
            return
        if approved:
            self.on_cost_approved(outcome)
            return
        facts = dict(outcome.facts or {})
        facts["cost_rejected"] = True
        if catering_needed(facts):
            facts["catering_rejected"] = True
        facts["vendor_sla"] = {**(facts.get("vendor_sla") or {}), "status": "NOT_APPROVED"}
        self._save_facts(outcome, facts)
        task = self._task(outcome, "CATERING_APPROVAL")
        if task and task.status not in {"VERIFIED", "CLOSED"}:
            self.engine.update_task_status(  # type: ignore[attr-defined]
                task, "CLOSED", actor="approver", resolution=f"Cost not approved{': ' + note if note else ''}"
            )
        for code in ("SERVICE_ENTRY", "INVOICE_VALIDATE", "INVOICE_POST", "INVOICE_PAY"):
            self._na_task(outcome, code)
        req = self._requirement(outcome, "INVOICE")
        if req:
            req.applicability = "NOT_APPLICABLE"
            req.status = "COMPLETED"
            self.session.add(req)
        if facts.get("task_packages"):
            self._dispatch_packages(outcome, reason="rejected")
        self._maybe_send_ready(outcome)

    # ---------- per-owner task packages
    def _dispatch_packages(self, outcome: Outcome, *, reason: str) -> list[dict[str, Any]]:
        """Build each owner's consolidated task list; send only the ones that are new or changed."""
        from app.agent.directory import route_for

        facts = dict(outcome.facts or {})
        items = build_package_items(facts)
        deadline = readiness_deadline(facts)
        previous = {p.get("owner"): p for p in facts.get("task_packages") or []}
        packages: list[dict[str, Any]] = []
        changed: list[dict[str, Any]] = []
        withdrawn: list[dict[str, Any]] = []
        for code, category, title in PACKAGE_OWNERS:
            its = items.get(code) or []
            old = previous.get(code)
            if not its:
                if old and old.get("status") != "CANCELLED":
                    packages.append({**old, "status": "CANCELLED"})
                    if old.get("status") in OPEN_PACKAGE and not old.get("redirected"):
                        withdrawn.append(old)
                continue
            fingerprint = _fp(its)
            if old and old.get("fingerprint") == fingerprint and old.get("status") != "CANCELLED":
                packages.append(old)
                continue
            route = route_for(self.session, self.tenant_id, category)
            pkg = {
                "owner": code,
                "title": title,
                "department": route.department_name,
                "items": its,
                "recipients": list(route.recipients),
                "redirected": bool(route.redirected_to_admin),
                "status": "SENT",
                "fingerprint": fingerprint,
                "sent_at": utcnow().isoformat(),
                "due": deadline.isoformat() if deadline else None,
                "revision": int((old or {}).get("revision") or 0) + (1 if old else 0),
            }
            packages.append(pkg)
            changed.append(pkg)
        facts["task_packages"] = packages
        if changed:
            facts.pop("ready_sent_at", None)
        self._save_facts(outcome, facts)

        groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for pkg in changed:
            if not pkg["redirected"] and pkg["recipients"]:
                groups.setdefault(tuple(pkg["recipients"]), []).append(pkg)
                self._await_department(outcome, pkg)
        for recipients, pkgs in groups.items():
            self._send_package_mail(outcome, list(recipients), pkgs, updated=reason != "booked")
        for old in withdrawn:
            self.comms.send_case_update(
                outcome=outcome,
                communication_type="INFORMATION_ONLY",
                body=(
                    f"{outcome.case_reference} — {outcome.summary or 'Meeting'}\n\n"
                    f"The {old.get('title')} tasks sent earlier are no longer needed after a change. "
                    "Please don't arrange them.\n"
                ),
                recipients=list(old.get("recipients") or []),
                action_label="UPDATE",
                subject_hint=f"{old.get('title')} tasks withdrawn",
                suppress_fingerprint=f"pkg_withdrawn:{old.get('owner')}:{old.get('fingerprint')}",
            )
        redirected = [p for p in changed if p["redirected"]]
        if redirected and reason != "booked":
            self.admin_ops.notify(  # type: ignore[attr-defined]
                outcome,
                kind="update",
                headline="Task list updated" + (" after cost approval" if reason == "approved" else " after a change"),
                detail=package_text(redirected),
                fingerprint=f"pkgs:{outcome.outcome_id}:{'-'.join(p['fingerprint'] for p in redirected)}",
                facts=dict(outcome.facts or facts),
            )
        return changed

    def _await_department(self, outcome: Outcome, pkg: dict[str, Any]) -> None:
        """A real department owns these tasks now: they stay open until it replies "done"."""
        for code in _OWNER_TASKS.get(pkg["owner"], ()):
            task = self._task(outcome, code)
            if task is None or task.resolution == "Not applicable":
                continue
            task.status = "ASSIGNED"
            task.resolution = f"Sent to {pkg.get('department') or pkg['title']}"
            self.session.add(task)

    def _send_package_mail(self, outcome: Outcome, recipients: list[str], pkgs: list[dict[str, Any]], *, updated: bool) -> None:
        from app.services.admin_ops import _people_line, _when_line

        facts = dict(outcome.facts or {})
        booked = facts.get("booked_room") or {}
        titles = " + ".join(p["title"] for p in pkgs)
        deadline = readiness_deadline(facts)
        room = str(booked.get("name") or "")
        if facts.get("hold_start") and facts.get("hold_end"):
            room += f" (setup from {facts['hold_start']}, release by {facts['hold_end']})"
        lines = [f"{outcome.case_reference} — {outcome.summary or 'Meeting'}", ""]
        if updated:
            lines += ["UPDATED — this replaces the earlier task list for this case.", ""]
        lines += [f"{label}: {value}" for label, value in (
            ("When", _when_line(facts) + (f" (days: {', '.join(_day_labels(facts))})" if is_multi_day(facts) else "")),
            ("Room", room),
            ("People", _people_line(facts)),
        ) if value]
        lines += ["", package_text(pkgs), ""]
        if deadline:
            lines.append(f"Ready by: {fmt_local(deadline)}")
        lines.append('Reply "done" when everything above is ready, or "issue: <what\'s blocking>" if something can\'t be delivered.')
        self.comms.send_case_update(
            outcome=outcome,
            communication_type="ACTION_REQUIRED",
            body="\n".join(lines) + "\n",
            recipients=recipients,
            action_label="ACTION REQUIRED",
            subject_hint=f"{titles} tasks — {outcome.summary or 'meeting'}",
            suppress_fingerprint=f"pkg:{'-'.join(p['owner'] + p['fingerprint'] for p in pkgs)}",
        )

    def apply_package_reply(self, outcome: Outcome, text: str, sender: str, *, is_admin: bool) -> Optional[dict]:
        """A department (or the admin, for lists redirected to them) says their part is done, or blocked."""
        facts = dict(outcome.facts or {})
        packages = [dict(p) for p in facts.get("task_packages") or []]
        open_ = [p for p in packages if p.get("status") in OPEN_PACKAGE]
        if not open_ or not (text or "").strip():
            return None
        sender = (sender or "").strip().lower()
        mine = [p for p in open_ if sender in [str(r).lower() for r in p.get("recipients") or []]]
        if not mine and is_admin and not self._pending_cost_approvals(outcome):
            mine = open_
        if not mine:
            return None
        cleaned = _NO_ISSUE_RE.sub(" ", text)
        if is_admin and not _ADMIN_PACKAGE_RE.match(cleaned):
            # The admin's replies are usually commands (approve / reject / book …); only explicit ones count here
            return None
        issue = bool(_ISSUE_RE.search(cleaned))
        done = bool(_DONE_RE.match(cleaned)) and not issue
        if not (issue or done):
            return None
        owners = {p["owner"] for p in mine}
        titles = ", ".join(p["title"] for p in mine)
        now = utcnow().isoformat()
        for pkg in packages:
            if pkg.get("owner") not in owners:
                continue
            if issue:
                pkg.update(status="ISSUE", issue=text.strip()[:300], issue_at=now, issue_by=sender)
            else:
                pkg.update(status="DONE", done_at=now, done_by=sender)
        facts["task_packages"] = packages
        self._save_facts(outcome, facts)

        if issue:
            deadline = readiness_deadline(facts)
            self.engine.create_exception(  # type: ignore[attr-defined]
                outcome=outcome,
                exception_type="SERVICE_BLOCKER",
                title=f"{titles}: delivery blocked",
                description=text.strip()[:1000],
                severity="HIGH",
                owner_role="OPERATOR",
            )
            facts = dict(outcome.facts or facts)
            facts["needs_ops"] = True
            self._save_facts(outcome, facts)
            self.admin_ops.at_risk(  # type: ignore[attr-defined]
                outcome,
                blocker=f'{titles} — "{text.strip()[:200]}" (from {sender})',
                deadline=f"ready by {fmt_local(deadline)}" if deadline else "",
                impact=f"{titles} items may not be ready for the meeting on {facts.get('date')}.",
                action='Arrange an alternative or tell the requester; the owner replies "done" once it\'s sorted.',
                fingerprint=f"{outcome.outcome_id}:{'-'.join(sorted(owners))}:{_fp(text)}",
                facts=dict(outcome.facts or facts),
            )
            summary = f"Logged the issue on {titles}; the admin has been alerted."
        else:
            for owner in owners:
                for code in _OWNER_TASKS.get(owner, ()):
                    self._complete_task(outcome, code, f"dept:{sender}", f"{titles} confirmed ready")
            self.engine._recompute_readiness(outcome)  # type: ignore[attr-defined]
            summary = f"Marked {titles} as ready."
        self.comms.send_case_update(
            outcome=outcome,
            communication_type="INFORMATION_ONLY",
            body=f"{summary}\n\nCase: {outcome.case_reference}\n",
            recipients=[sender],
            action_label="UPDATE NOTED",
            subject_hint=f"{titles} — {'issue logged' if issue else 'marked ready'}",
            suppress_fingerprint=f"pkg_ack:{sender}:{_fp(text)}:{'-'.join(sorted(owners))}",
        )
        if done:
            self._maybe_send_ready(outcome)
        return {"applied": True, "action": "PACKAGE_ISSUE" if issue else "PACKAGE_DONE", "summary": summary}

    def _maybe_send_ready(self, outcome: Outcome) -> bool:
        facts = dict(outcome.facts or {})
        if not facts.get("booked_room") or facts.get("ready_sent_at"):
            return False
        if (facts.get("operational_status") or "") in {"CLOSED", "CANCELLED"}:
            return False
        packages = [p for p in facts.get("task_packages") or [] if p.get("status") != "CANCELLED"]
        if not packages or any(p.get("status") != "DONE" for p in packages):
            return False
        if self._pending_cost_approvals(outcome):
            return False
        facts["ready_sent_at"] = utcnow().isoformat()
        facts["orchestration_stage"] = MeetingStage.READY.value
        self._save_facts(outcome, facts)
        booked = facts.get("booked_room") or {}
        from app.services.admin_ops import _when_line

        ready = "\n".join(f"- {p['title']}: " + "; ".join((p.get("items") or [])[:3]) for p in packages)
        plan = facts.get("cost_plan") or {}
        charged = [line["name"] for line in chargeable_lines(plan)]
        lines = [
            "Everything for your meeting is ready.",
            f"Room: {booked.get('name')}\nWhen: {_when_line(facts)}",
            f"Confirmed ready:\n{ready}",
        ]
        if charged and approval_state(facts) == "approved":
            lines.append("Approved chargeable items: " + ", ".join(charged) + ".")
        lines.append("After the meeting I'll check with you that everything was delivered as planned.")
        self._mail_requester(
            outcome, label="READY", lines=lines, fingerprint=f"ready:{outcome.outcome_id}:{_fp([p.get('fingerprint') for p in packages])}",
        )
        return True

    # ---------- host verification (after the meeting)
    def request_completion(self, outcome: Outcome, *, now: Optional[datetime] = None) -> bool:
        facts = dict(outcome.facts or {})
        if facts.get("completion_requested_at") or (facts.get("operational_status") or "") in {"CLOSED", "CANCELLED"}:
            return False
        end = event_end(facts)
        if not end or local_now(now) < end:
            return False
        facts["completion_requested_at"] = utcnow().isoformat()
        facts["orchestration_stage"] = MeetingStage.HOST_VERIFICATION.value
        self._save_facts(outcome, facts)
        booked = facts.get("booked_room") or {}
        lines = [
            f"Your meeting in {booked.get('name') or 'the booked room'} has ended. How did it go? Just reply with one of these:",
            "- Fully delivered\n- Partially delivered, and what was short\n- Issue reported, and what went wrong",
        ]
        if chargeable_lines(facts.get("cost_plan")) and not facts.get("cost_rejected"):
            lines.append("After that I'll ask you to confirm the chargeable quantities so billing matches what was delivered.")
        self._mail_requester(
            outcome, label="COMPLETED", lines=lines, ctype="ACTION_REQUIRED",
            fingerprint=f"completed:{outcome.outcome_id}", hint="Please confirm delivery",
        )
        return True

    def handle_service_issue(self, outcome: Outcome, text: str) -> None:
        facts = dict(outcome.facts or {})
        facts["service_issue"] = {"text": text.strip()[:500], "at": utcnow().isoformat()}
        facts["orchestration_stage"] = MeetingStage.HOST_VERIFICATION.value
        facts["needs_ops"] = True
        facts["invoice_hold"] = bool(chargeable_lines(facts.get("cost_plan")))
        facts["last_action"] = "service_issue_reported"
        self._save_facts(outcome, facts)
        self.engine.create_exception(  # type: ignore[attr-defined]
            outcome=outcome,
            exception_type="SERVICE_ISSUE",
            title="Organiser reported a delivery issue",
            description=text.strip()[:1000],
            severity="MEDIUM",
            owner_role="OPERATOR",
        )
        lines = ["Sorry about that — I've logged it and the admin team will follow up with you."]
        if facts["invoice_hold"]:
            lines.append("Billing for the affected items is on hold until it's resolved.")
        self._mail_requester(outcome, label="UPDATE NOTED", lines=lines, fingerprint=f"issue:{_fp(text)}")
        self.admin_ops.notify(  # type: ignore[attr-defined]
            outcome,
            kind="decision",
            headline="Organiser reported a delivery issue",
            detail=f'They said: "{text.strip()[:400]}"\n'
            + ("Billing for chargeable items is on hold.\n" if facts["invoice_hold"] else "")
            + 'Reply "tell requester: <message>" to respond; the case closes when they confirm it\'s sorted.',
            fingerprint=f"service_issue:{outcome.outcome_id}:{_fp(text)}",
            facts=dict(outcome.facts or facts),
        )

    # ---------- service entry + financial closure
    def start_financial_closure(self, outcome: Outcome) -> None:
        """After operational close: chargeable lines need a service entry; no charges → close financially now."""
        facts = dict(outcome.facts or {})
        if (facts.get("financial_status") or "") in {"CLOSED", "SERVICE_ENTRY_PENDING"}:
            return
        plan = facts.get("cost_plan")
        lines = [] if facts.get("cost_rejected") else chargeable_lines(plan)
        if not lines:
            if plan is not None or not (catering_needed(facts) or facts.get("catering_assigned")):
                self.engine.close_financial(outcome, actor="system")  # type: ignore[attr-defined]
                return
            facts["invoice_stub"] = {
                "invoice_number": f"FS-{outcome.case_reference}",
                "amount_ex_tax": (facts.get("catering_quote") or {}).get("amount_ex_tax"),
                "status": "RECEIVED",
            }
            self._save_facts(outcome, facts)
            return
        entries = [
            {
                "code": line["code"],
                "name": line["name"],
                "owner": line.get("owner"),
                "unit": line.get("unit"),
                "planned_qty": line.get("chargeable_qty") or line.get("qty"),
                "rate": line.get("rate"),
                "planned_amount": line.get("amount"),
                "actual_qty": None,
                "status": "AWAITING_VERIFICATION",
            }
            for line in lines
        ]
        facts["service_entries"] = entries
        facts["financial_status"] = "SERVICE_ENTRY_PENDING"
        self._save_facts(outcome, facts)
        task = self._task(outcome, "SERVICE_ENTRY")
        if task and task.status in {"NOT_STARTED", "CLOSED", "CANCELLED"}:
            task.status = "ASSIGNED"
            self.session.add(task)
        currency = (plan or {}).get("currency") or "INR"
        planned = "\n".join(
            f"- {e['name']}: {e['planned_qty']:g}" + (f" x {_money(e['rate'], currency)}" if e.get("rate") else "")
            for e in entries
        )
        self._mail_requester(
            outcome,
            label="ACTION REQUIRED",
            ctype="ACTION_REQUIRED",
            hint="Confirm chargeable service entry",
            fingerprint=f"service_entry:{outcome.outcome_id}",
            lines=[
                "Before this goes to billing, please confirm what was actually delivered for the chargeable items:",
                planned,
                'Reply "confirmed" if these are right, or give the actual numbers (e.g. "lunch 10").',
            ],
        )

    def apply_service_entry_reply(self, outcome: Outcome, text: str) -> bool:
        """True when the reply was read as a service-entry confirmation or correction."""
        facts = dict(outcome.facts or {})
        entries = [dict(e) for e in facts.get("service_entries") or []]
        pending = [e for e in entries if e.get("status") == "AWAITING_VERIFICATION"]
        if not pending:
            return False
        parsed = {e["code"]: _actual_qty(text, e["code"]) for e in pending}
        if not any(v is not None for v in parsed.values()) and not _ENTRY_OK_RE.search(text):
            return False
        variances = []
        now = utcnow().isoformat()
        for entry in entries:
            if entry.get("status") != "AWAITING_VERIFICATION":
                continue
            planned = float(entry.get("planned_qty") or 0)
            actual = parsed.get(entry["code"])
            actual = planned if actual is None else actual
            entry["actual_qty"] = actual
            entry["actual_amount"] = round(actual * float(entry["rate"]), 2) if entry.get("rate") else None
            entry["verified_at"] = now
            entry["verified_by"] = outcome.requester_email
            if abs(actual - planned) > 1e-6:
                entry["status"] = "VARIANCE"
                variances.append(entry)
            else:
                entry["status"] = "ACCEPTED"
        total = round(sum(float(e.get("actual_amount") or 0) for e in entries), 2)
        facts["service_entries"] = entries
        facts["service_entry_total"] = total
        currency = (facts.get("cost_plan") or {}).get("currency") or "INR"
        summary = "\n".join(f"- {e['name']}: {float(e['actual_qty']):g}" for e in entries)
        if variances:
            facts["financial_status"] = "BILLING_EXCEPTION"
            facts["invoice_hold"] = True
            self._save_facts(outcome, facts)
            detail = "; ".join(f"{e['name']} planned {float(e['planned_qty']):g}, delivered {float(e['actual_qty']):g}" for e in variances)
            self.engine.create_exception(  # type: ignore[attr-defined]
                outcome=outcome,
                exception_type="SERVICE_ENTRY_VARIANCE",
                title="Delivered quantity differs from the plan",
                description=detail,
                severity="MEDIUM",
                owner_role="FINANCE",
            )
            self.admin_ops.billing_exception(  # type: ignore[attr-defined]
                outcome,
                headline="Service entry differs from the plan",
                lines=[
                    f"Organiser confirmed: {detail}.",
                    f"Bill only what was delivered: {_money(total, currency)} before tax.",
                    "Invoice is on hold for these lines until the provider bills the delivered quantity.",
                ],
                fingerprint=f"variance:{outcome.outcome_id}",
                facts=dict(outcome.facts or facts),
            )
        else:
            facts["financial_status"] = "FINANCIAL_CLOSURE_PENDING"
            self._save_facts(outcome, facts)
            self._complete_task(outcome, "SERVICE_ENTRY", "requester", f"Service entry accepted: {_money(total, currency)}")
            self.admin_ops.notify(  # type: ignore[attr-defined]
                outcome,
                kind="update",
                headline="Service entry accepted — waiting for the invoice",
                detail=f"Accepted amount: {_money(total, currency)} before tax. The provider's invoice should quote "
                f"{outcome.case_reference}; it's matched automatically when it arrives.",
                fingerprint=f"entry_ok:{outcome.outcome_id}",
                facts=dict(outcome.facts or facts),
                recipients=list(dict.fromkeys(_finance_recipients())),
            )
        self._mail_requester(
            outcome,
            label="UPDATE NOTED",
            fingerprint=f"entry_ack:{outcome.outcome_id}",
            lines=["Thanks — recorded for billing:", summary],
        )
        return True

    def match_event_invoice(self, outcome: Outcome, *, invoice_number: str, amount: float, actor: str) -> dict:
        facts = dict(outcome.facts or {})
        entries = facts.get("service_entries") or []
        currency = (facts.get("cost_plan") or {}).get("currency") or "INR"
        match: dict[str, Any] = {"invoice_number": invoice_number, "amount": amount, "at": utcnow().isoformat()}
        if facts.get("financial_status") == "CLOSED" and facts.get("invoice_match", {}).get("status") == "MATCHED":
            return {**facts["invoice_match"], "status": "ALREADY_CLOSED"}
        if not entries:
            match["status"] = "NO_CHARGEABLE_SERVICES"
            problem = "This event had no chargeable services, so there is nothing to bill."
        elif any(e.get("status") == "AWAITING_VERIFICATION" for e in entries):
            match["status"] = "HELD_AWAITING_SERVICE_ENTRY"
            problem = "The organiser hasn't confirmed the delivered quantities yet; the invoice is held until they do."
        else:
            total = float(facts.get("service_entry_total") or 0)
            match["expected"] = total
            if abs(amount - total) <= max(1.0, 0.01 * total):
                match["status"] = "MATCHED"
                facts["invoice_match"] = match
                facts["invoice_hold"] = False
                self._save_facts(outcome, facts)
                self.engine.close_financial(outcome, actor=actor)  # type: ignore[attr-defined]
                self.admin_ops.notify(  # type: ignore[attr-defined]
                    outcome,
                    kind="update",
                    headline="Invoice matched — financial closure done",
                    detail=f"Invoice {invoice_number} for {_money(amount, currency)} matches the accepted service entry.",
                    fingerprint=f"invoice_ok:{outcome.outcome_id}:{invoice_number}",
                    facts=dict(outcome.facts or facts),
                    recipients=list(dict.fromkeys(_finance_recipients())),
                )
                return match
            match["status"] = "MISMATCH"
            problem = (
                f"Invoice {invoice_number} is {_money(amount, currency)} but the accepted service entry is "
                f"{_money(total, currency)}."
            )
        facts["invoice_match"] = match
        facts["financial_status"] = "BILLING_EXCEPTION"
        facts["invoice_hold"] = True
        self._save_facts(outcome, facts)
        self.engine.create_exception(  # type: ignore[attr-defined]
            outcome=outcome,
            exception_type="INVOICE_MISMATCH",
            title="Event invoice doesn't match the service entry",
            description=problem,
            severity="HIGH",
            owner_role="FINANCE",
        )
        self.admin_ops.billing_exception(  # type: ignore[attr-defined]
            outcome,
            headline="Invoice doesn't match the event",
            lines=[problem, "Payment is on hold. Ask the provider for a corrected invoice, or reply with the decision."],
            fingerprint=f"invoice:{outcome.outcome_id}:{invoice_number}:{match['status']}",
            facts=dict(outcome.facts or facts),
        )
        return match

    # ---------- follow-ups: one reminder, then one escalation
    def run_followups(self, outcome: Outcome, *, now: Optional[datetime] = None) -> dict[str, int]:
        settings = get_settings()
        now = now or utcnow()
        remind = timedelta(hours=float(settings.followup_reminder_hours or 8))
        escalate = timedelta(hours=float(settings.followup_escalate_hours or 24))
        facts = dict(outcome.facts or {})
        state = dict(facts.get("followups") or {})
        deadline = readiness_deadline(facts)
        near_deadline = bool(deadline and local_now(now) >= deadline - timedelta(hours=2))
        counts = {"reminders": 0, "escalations": 0}

        for approval in self._pending_cost_approvals(outcome):
            key = f"approval:{approval.approval_id}"
            entry = dict(state.get(key) or {})
            age = now - approval.created_at
            if not entry.get("escalated_at") and (age >= escalate or (near_deadline and age >= timedelta(minutes=30))):
                sent = self.admin_ops.at_risk(  # type: ignore[attr-defined]
                    outcome,
                    blocker="Cost approval still pending",
                    deadline=f"ready by {fmt_local(deadline)}" if deadline else "",
                    impact="Chargeable items (" + ", ".join((facts.get("cost_plan") or {}).get("chargeable") or []) + ") can't be arranged.",
                    action='Approver: reply "approve" or "reject, <reason>" on the approval mail (or use its links).',
                    fingerprint=key,
                    facts=dict(outcome.facts or facts),
                )
                entry["escalated_at"] = now.isoformat()
                counts["escalations"] += int(bool(sent))
            elif not entry.get("reminded_at") and not entry.get("escalated_at") and age >= remind:
                approver = ((facts.get("cost_plan") or {}).get("cost_centre") or {}).get("approver_email")
                sent = self.admin_ops.action_approval(  # type: ignore[attr-defined]
                    outcome,
                    approval_type=approval.approval_type,
                    facts=dict(outcome.facts or facts),
                    include_admin=False,
                    extra_approvers=[approver] if approver else None,
                    reminder=True,
                )
                entry["reminded_at"] = now.isoformat()
                counts["reminders"] += int(bool(sent))
            state[key] = entry

        for pkg in facts.get("task_packages") or []:
            if pkg.get("status") != "SENT" or pkg.get("redirected") or not pkg.get("recipients"):
                continue
            key = f"package:{pkg['owner']}:{pkg.get('fingerprint')}"
            entry = dict(state.get(key) or {})
            try:
                age = now - datetime.fromisoformat(str(pkg.get("sent_at")))
            except ValueError:
                continue
            if not entry.get("escalated_at") and (age >= escalate or (near_deadline and age >= timedelta(minutes=30))):
                sent = self.admin_ops.at_risk(  # type: ignore[attr-defined]
                    outcome,
                    blocker=f"{pkg['title']} hasn't confirmed its tasks ({', '.join(pkg['recipients'])})",
                    deadline=f"ready by {fmt_local(deadline)}" if deadline else "",
                    impact=f"{pkg['title']} items may not be ready: " + "; ".join((pkg.get("items") or [])[:3]),
                    action=f"Chase {pkg.get('department') or pkg['title']} or arrange it another way.",
                    fingerprint=key,
                    facts=dict(outcome.facts or facts),
                )
                entry["escalated_at"] = now.isoformat()
                counts["escalations"] += int(bool(sent))
            elif not entry.get("reminded_at") and not entry.get("escalated_at") and age >= remind:
                self.comms.send_case_update(
                    outcome=outcome,
                    communication_type="ACTION_REQUIRED",
                    body=(
                        f"{outcome.case_reference} — {outcome.summary or 'Meeting'}\n\n"
                        f"Reminder: we haven't heard back on these {pkg['title']} tasks.\n\n"
                        + package_text([pkg])
                        + (f"\n\nReady by: {fmt_local(deadline)}" if deadline else "")
                        + '\n\nReply "done" when ready, or "issue: <what\'s blocking>".\n'
                    ),
                    recipients=list(pkg["recipients"]),
                    action_label="ACTION REQUIRED",
                    subject_hint=f"Reminder: {pkg['title']} tasks",
                    suppress_fingerprint=f"pkg_reminder:{key}",
                )
                entry["reminded_at"] = now.isoformat()
                counts["reminders"] += 1
            state[key] = entry

        if state != (facts.get("followups") or {}):
            fresh = dict(outcome.facts or {})
            fresh["followups"] = state
            self._save_facts(outcome, fresh)
        return counts


def _finance_recipients() -> list[str]:
    from app.services.admin_ops import admin_ops_email, approver_emails

    admin = admin_ops_email()
    return [e for e in approver_emails("INVOICE") + ([admin] if admin else []) if e]


def sweep_event_followups(session: Session, tenant_id: str, *, now: Optional[datetime] = None) -> dict[str, int]:
    """Background pass: approval / task-package follow-ups and the post-meeting COMPLETED check."""
    from app.connectors.factory import get_email_provider
    from app.engine.meeting_scenario import ClientMeetingOrchestrator
    from app.engine.outcome_engine import OutcomeEngine
    from app.services.communication import CommunicationService

    email = get_email_provider(session, tenant_id)
    comms = CommunicationService(session, tenant_id, email_sender=email if email.is_connected() else None)
    orch = ClientMeetingOrchestrator(session, tenant_id, OutcomeEngine(session, tenant_id), comms)
    totals = {"reminders": 0, "escalations": 0, "completed": 0}
    rows = session.exec(
        select(Outcome).where(
            Outcome.tenant_id == tenant_id,
            Outcome.template_code == "MEETING_ROOM",
            Outcome.status.notin_(["CLOSED", "CANCELLED", "VERIFIED"]),  # type: ignore[attr-defined]
        )
    ).all()
    for outcome in rows:
        facts = outcome.facts or {}
        if not facts.get("booked_room") or facts.get("orchestration_stage") == MeetingStage.CANCELLED.value:
            continue
        if (facts.get("operational_status") or "") != "CLOSED":
            counts = orch.run_followups(outcome, now=now)
            totals["reminders"] += counts["reminders"]
            totals["escalations"] += counts["escalations"]
            totals["completed"] += int(orch.request_completion(outcome, now=now))
    session.commit()
    if any(totals.values()):
        logger.info("event_followups_sweep", **totals)
    return totals
