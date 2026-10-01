"""The AI admin desk: reads a mail with its whole trail and decides what the person wants.

Output is a structured decision (intents + a reply draft). Code executes the intents and
enforces the risk policy; the model never performs actions directly.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from app.agent.playbooks import catalogue_for_prompt
from app.agent.tools import tool_catalogue
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.intake import Conversation, RawEmailEvent
from app.models.org import Person
from app.models.outcome import Communication, Outcome
from app.services.email_utils import strip_for_ai

logger = get_logger(__name__)

INTENT_TYPES = ("small_talk", "question", "new_request", "update_case", "status", "cancel", "close", "empty")


class AgentIntent(BaseModel):
    type: str = "new_request"
    category: str = "general"
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    case_reference: Optional[str] = None
    missing: list[str] = Field(default_factory=list)
    needs_admin_decision: bool = False
    decision_reason: str = ""
    priority: str = "MEDIUM"
    desired_outcome: str = ""
    risk_signals: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    # question intents: False when OFFICE_KNOWLEDGE does not hold the answer (no-guess rule)
    answer_verified: bool = True

    @field_validator("risk_signals", "tasks", mode="before")
    @classmethod
    def _signals(cls, v: Any) -> list:
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [str(x) for x in (v or []) if str(x).strip()]

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, v: Any) -> str:
        t = str(v or "").strip().lower()
        return t if t in INTENT_TYPES else "new_request"

    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, v: Any) -> str:
        p = str(v or "MEDIUM").strip().upper()
        return p if p in {"LOW", "MEDIUM", "HIGH", "URGENT"} else "MEDIUM"

    @field_validator("details", mode="before")
    @classmethod
    def _details(cls, v: Any) -> dict:
        return v if isinstance(v, dict) else {}

    @field_validator("missing", mode="before")
    @classmethod
    def _missing(cls, v: Any) -> list:
        if isinstance(v, str):
            return [v] if v.strip() else []
        return [str(x) for x in (v or []) if str(x).strip()]


class AgentDecision(BaseModel):
    intents: list[AgentIntent] = Field(default_factory=list)
    reply_to_requester: str = ""
    confidence: float = 0.7
    reason_summary: str = ""
    source: str = "gemini"

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5

    @property
    def primary(self) -> Optional[AgentIntent]:
        return self.intents[0] if self.intents else None


AGENT_INSTRUCTION = """You are the Admin Desk of a company - a capable, friendly office administrator who works over email.
Employees, visitors' hosts, HR and vendors write to you in any style: short, messy, Hinglish, typos, forwarded chains,
"pls find the same", replies with our own questions pasted back and answers typed in between.

Your job for EACH inbound mail:
1. Understand what the person actually wants, using the WHOLE trail (labelled turns), not only this mail.
   - Turns labelled "admin_desk" are OUR earlier mails. Never treat our wording (questions, option lists, summaries)
     as something the requester asked for. Only the requester's own words are their request.
   - Resolve references: "same as before", "pls find the same", "as below", "pls book", "go ahead", "that one"
     point at earlier turns in this trail. The newest message only changes what it actually changes.
   - A mail in an existing trail normally continues that case (update_case / status / cancel / close).
     Use new_request only for a clearly different piece of work.
2. Split the mail into intents (one mail may hold several requests - each is its own intent).
   Intent types:
   - small_talk: greetings, thanks, chit-chat with no work. ("hi", "hello team", "thanks!")
   - question: they ask for information (timings, address, policy, wifi, entitlement...). Set answer_verified=true
     only when OFFICE_KNOWLEDGE actually contains the answer. Otherwise answer_verified=false - never answer a
     company-specific question from general knowledge (no guessing about policies, rates, people, rooms or dates).
   - new_request: work to be done. Set category from REQUEST_TYPES (use the "category" value; "also_called" lists
     common words people use). Every kind of office work matters equally - a broken chair, a courier, a gate pass,
     a cab and a meeting room are all first-class requests. If nothing fits, use a short snake_case label or "general".
     Distinguish carefully:
       visitor (people coming in) vs material_gate_pass (goods/assets going out or coming in) vs parking;
       travel (one-off cab/flight/hotel) vs employee_transport (regular shuttle / pick-drop) vs guest_house (stay);
       catering (food for a meeting/event) vs pantry (tea/coffee/water machines) vs cafeteria (canteen, coupons, food quality);
       maintenance/hvac/electrical/plumbing/furniture (fix something) vs housekeeping (clean something);
       seating (desk allocation / moves) vs furniture (repair or new furniture);
       it_support (problem) vs laptop/software/phone_sim/asset (provide or move something).
   - update_case: new or changed details for an existing case (give case_reference). If an OPEN_CASES entry is
     RESOLVED and they say it is still not working / happened again, that is update_case on that case (it reopens).
   - status: they ask what is happening with a case.
   - cancel: they no longer need it.
   - close: they confirm it is done / resolved / satisfied.
   - empty: the mail has no real content (only a signature, blank, auto-reply).
3. For new_request/update_case put everything useful in details using clear snake_case keys, e.g. location, floor,
   issue, items, quantity, date, time, headcount, visitor_names, vehicle_numbers, pickup, drop, employee_name,
   joining_date, returnable (true/false for gate passes), amount, cost_centre, on_behalf_of.
   - Use what you already know: the requester profile (department, office), the trail, OPEN_CASES and today's date.
     Resolve "tomorrow", "Monday", "next week" to real dates. Never ask for something already given anywhere.
   - Use the exact keys in REQUEST_TYPES.detail_keys for the things each type needs (onboarding: employee_name,
     joining_date) - the desk checks those keys, so a different name makes it ask again for what was already given.
   - If someone writes for another person ("for my manager"), put that in on_behalf_of. The person a request is
     about (the new joiner, the leaver, the visitor) still goes in its own key, e.g. employee_name.
   - Recurring needs ("every Monday", "daily", "monthly") go in details.recurrence.
   - List in "missing" only the one to three things truly needed to act (REQUEST_TYPES.needs shows what each type
     needs); ask like a human would. Safety problems are never held back by questions.
   For meeting_room and invoice just capture the intent - specialised flows collect their details.
   - desired_outcome: one line on what "done" looks like for the requester (e.g. "AC cooling again in 4th floor bay").
   - risk_signals: short tags for anything risky you notice (safety, money, access, confidential, external party).
   - tasks: each concrete action the requester wants done, one short imperative line per action, keeping their
     specifics (e.g. ["Set up Windows laptop with marketing software", "Create company email ID",
     "Allocate desk near the Marketing team, 3rd floor", "Issue ID and access card for office and 3rd floor"]).
     Split combined asks into separate actions so each can go to the right team. Empty when nothing specific was asked.
   - SIMILAR_VERIFIED_CASES are past requests that were completed and verified here. Use them as precedent for the
     category, team and what to ask - but never copy their dates, names or amounts.
4. priority (impact x urgency): URGENT = safety risk or work stopped for many (fire, smoke, sparks, flooding, gas,
   lift stuck, injury, theft, no power / internet for a floor); HIGH = one person/team blocked or a hard deadline today,
   VIP/client visit; MEDIUM = normal requests; LOW = "no rush", routine, next week.
5. needs_admin_decision = true for sensitive work: money above small amounts, payments, bank details, access cards /
   security access, non-returnable material leaving, vendors, confidential, HR or personal matters, anything risky or
   unclear. Otherwise false - the desk does it.
6. Write reply_to_requester: the email body you would send, as a warm, concise human admin.
   - Greet by first name if known. Plain text, short paragraphs or bullets, no markdown headings.
   - small_talk "hi": greet back and say briefly what you can help with (repairs, IT, housekeeping, visitors,
     parking, gate passes, couriers, supplies, travel and cabs, seating, events, rooms...), ask how you can help.
     Do not open any case.
   - URGENT: say it has been flagged urgent and the team and admin alerted now; add one line of safety advice
     when relevant (e.g. keep away from sparking sockets, use the stairs).
   - question: answer only from OFFICE_KNOWLEDGE; if not there, say you could not verify it and have passed it to
     the admin team, who will reply on this thread.
   - new_request: acknowledge what you understood. Where the case reference goes write the token [[REF1]] for the
     first request intent, [[REF2]] for the second, and so on. If details are missing, ask only for those.
     If it needs admin approval, say you've passed it for approval. Otherwise say it's been assigned to the right team.
   - Never promise an outcome that has not happened (don't say "fixed", "booked", "approved").
   - status: answer from OPEN_CASES state only. Never open a new case for a status question.
   - question outside office matters: reply politely like an office admin would, help briefly if you can, otherwise
     say it's outside what the admin desk handles.
   - Sign off with the SIGNATURE given.
7. confidence: 0-1, how sure you are about the intents. reason_summary: one sentence on why you read it this way.

Return JSON only:
{"intents":[{"type":"...","category":"...","summary":"short title","details":{},"case_reference":null,
"missing":[],"needs_admin_decision":false,"decision_reason":"","priority":"MEDIUM","desired_outcome":"",
"risk_signals":[],"tasks":[],"answer_verified":true}],
"reply_to_requester":"...","confidence":0.0,"reason_summary":""}
"""


def _clip(text: str, n: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
    return text if len(text) <= n else text[: n - 1] + "…"


def build_trail(session: Session, conversation: Optional[Conversation], exclude_event_id: str, limit: int = 12) -> list[dict]:
    """Labelled turns of this thread, oldest first. Inbound shows only what the sender newly typed."""
    if conversation is None:
        return []
    requester = (conversation.requester_email or "").lower()
    turns: list[tuple[datetime, dict]] = []
    events = session.exec(
        select(RawEmailEvent).where(
            RawEmailEvent.conversation_id == conversation.conversation_id,
            RawEmailEvent.event_id != exclude_event_id,
        )
    ).all()
    for ev in events:
        sender = (ev.sender or "").lower()
        who = "requester" if sender == requester else "admin_or_team"
        text = strip_for_ai(ev.body_text or ev.body_for_ai or "")
        turns.append((ev.received_at or ev.created_at, {"from": who, "subject": ev.subject, "text": _clip(text, 1500)}))
    comms = session.exec(
        select(Communication).where(Communication.conversation_id == conversation.conversation_id)
    ).all()
    for c in comms:
        to_requester = requester in [str(r).lower() for r in (c.recipients or [])]
        who = "admin_desk" if to_requester else "admin_desk_to_team"
        turns.append((c.sent_at or c.created_at, {"from": who, "subject": c.subject, "text": _clip(c.body or "", 1200)}))
    turns.sort(key=lambda t: t[0] or datetime.min)
    return [t[1] for t in turns[-limit:]]


def case_state(outcome: Outcome) -> dict:
    facts = outcome.facts or {}
    state = {
        "case_reference": outcome.case_reference,
        "category": (facts.get("agent_category") or outcome.category or "").lower(),
        "title": outcome.title,
        "status": outcome.status,
        "stage": facts.get("agent_stage") or facts.get("orchestration_stage"),
        "opened": outcome.created_at.strftime("%d %b %Y") if outcome.created_at else None,
    }
    for key in ("department_name", "missing", "details", "decision_reason", "resolution_note"):
        if facts.get(key):
            state[key] = facts[key]
    room = facts.get("booked_room") or facts.get("proposed_room")
    if isinstance(room, dict) and room.get("name"):
        state["room"] = f"{room['name']} on {room.get('date')} {room.get('start')}-{room.get('end')}"
        state["room_status"] = "booked" if facts.get("booked_room") else "held, awaiting confirmation"
    return state


def open_cases(session: Session, tenant_id: str, requester_email: str, limit: int = 8) -> list[Outcome]:
    closed = {"CLOSED", "CANCELLED", "ADMINISTRATIVELY_CLOSED"}
    rows = session.exec(
        select(Outcome)
        .where(Outcome.tenant_id == tenant_id, Outcome.requester_email == (requester_email or "").lower())
        .order_by(Outcome.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    return [o for o in rows if o.status not in closed][:limit]


def requester_profile(session: Session, email: str, display_name: Optional[str]) -> dict:
    person = session.exec(select(Person).where(Person.email == (email or "").lower())).first()
    if not person:
        return {"email": email, "name": display_name, "known_employee": False}
    manager = session.get(Person, person.manager_id) if person.manager_id else None
    return {
        "email": person.email,
        "name": person.name,
        "department": person.department,
        "role": person.role,
        "manager": manager.name if manager else None,
        "known_employee": True,
    }


def _today_ist() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime("%A %d %B %Y")


def build_agent_payload(
    *,
    subject: str,
    this_message: str,
    trail: list[dict],
    cases: list[dict],
    current_case: Optional[str],
    profile: dict,
    knowledge: str,
    departments: list[dict],
    attachments: list[str],
    similar_cases: Optional[list[dict]] = None,
) -> dict:
    return {
        "SIMILAR_VERIFIED_CASES": similar_cases or [],
        "today": _today_ist(),
        "subject": subject,
        "this_message": this_message or "(empty)",
        "attachments": attachments,
        "trail_oldest_first": trail,
        "this_thread_case": current_case,
        "OPEN_CASES": cases,
        "requester": profile,
        "OFFICE_KNOWLEDGE": knowledge,
        "teams": departments,
        "REQUEST_TYPES": catalogue_for_prompt(),
        "TOOLS": tool_catalogue(),
        "SIGNATURE": get_settings().mail_signature,
    }


class AdminAgent:
    def __init__(self, provider: Any = None):
        self.provider = provider

    @property
    def can_reason(self) -> bool:
        from app.ai.gemini import HeuristicProvider

        if get_settings().ai_emergency_stop:
            return False
        return self.provider is not None and not isinstance(self.provider, HeuristicProvider) and hasattr(
            self.provider, "generate_json"
        )

    def decide(self, payload: dict, *, heuristic_hint: Optional[str] = None) -> AgentDecision:
        if self.can_reason:
            try:
                data, endpoint = self.provider.generate_json(system_instruction=AGENT_INSTRUCTION, payload=payload)
                decision = AgentDecision.model_validate(data)
                decision.source = f"gemini:{(endpoint or {}).get('label', '')}"
                if decision.intents:
                    return decision
                logger.warning("admin_agent_empty_decision")
            except Exception as exc:  # noqa: BLE001
                logger.warning("admin_agent_failed_using_rules", error=str(exc)[:300])
        return heuristic_decision(payload, legacy_event_type=heuristic_hint)


# ---------------------------------------------------------------------------
# Rule-based fallback (no Gemini). Deliberately conservative: it only takes over mail it is
# sure about and hands everything else to the existing flows.
# ---------------------------------------------------------------------------

_GREETING = re.compile(
    r"^\s*(?:hi+|hello+|hey+|hii+|good\s+(?:morning|afternoon|evening)|namaste|greetings|hello\s+team|hi\s+team|"
    r"dear\s+(?:team|admin|sir|madam))[\s,.!]*(?:team|admin|there|sir|madam|all)?[\s,.!]*$",
    re.I,
)
_THANKS = re.compile(r"^\s*(?:thanks?|thank\s+you|thx|ty|ok(?:ay)?\s+thanks?|noted|great,?\s+thanks?)[\s,.!]*(?:a\s+lot|so\s+much|team)?[\s,.!]*$", re.I)
_STATUS = re.compile(r"\b(?:any\s+update|status\s+(?:of|on)|what(?:'s|\s+is)\s+the\s+status|update\s+on|still\s+(?:not|waiting)|follow(?:ing)?\s*up)\b", re.I)

_CASE_REF = re.compile(r"\b([A-Z]{2,5}-\d{4}-\d{3,})\b", re.I)
_NO_REPLY_SENDER = re.compile(r"^(?:no-?reply|do-?not-?reply|donotreply|mailer-daemon|postmaster|bounces?|notifications?)(?:[+.\-_].*)?@", re.I)
_AUTO_SUBJECT = re.compile(
    r"^\s*(?:automatic\s+reply|auto(?:matic)?[\s-]?reply|autoreply|out\s+of\s+(?:the\s+)?office|ooo\b|undeliverable|"
    r"delivery\s+status\s+notification|mail\s+delivery\s+(?:failed|failure|subsystem)|returned\s+mail)",
    re.I,
)


def automated_reason(sender: str, subject: str, headers: Optional[dict]) -> Optional[str]:
    """Why a mail is machine-sent (never answer those), or None for a real person."""
    h = {str(k).lower(): str(v).lower() for k, v in (headers or {}).items()}
    if _NO_REPLY_SENDER.match((sender or "").strip()):
        return "no-reply sender"
    auto = h.get("auto-submitted", "")
    if auto and auto != "no":
        return f"auto-submitted: {auto}"
    if h.get("x-autoreply") or h.get("x-autorespond") or "x-auto-response-suppress" in h and "oof" in h.get("x-auto-response-suppress", ""):
        return "auto-reply header"
    if h.get("precedence", "") in {"bulk", "auto_reply", "junk", "list"}:
        return f"precedence: {h['precedence']}"
    if _AUTO_SUBJECT.match(subject or ""):
        return "auto-reply subject"
    return None


_RULE_CATEGORIES: list[tuple[str, re.Pattern]] = [
    ("health_safety", re.compile(r"\b(?:fire|smoke|sparking|short\s*circuit|gas\s+leak|injur\w*|first\s*aid|electric\s+shock|lift\s+stuck|trapped)\b", re.I)),
    ("material_gate_pass", re.compile(r"\b(?:gate\s*pass|material\s+(?:out|pass|going)|returnable|rgp|nrgp|take\s+(?:out|home)\s+(?:the\s+)?(?:laptop|monitor|equipment|material))\b", re.I)),
    ("pest_control", re.compile(r"\b(?:pest|rats?|rodents?|mice|cockroach\w*|termites?|mosquito\w*|lizards?)\b", re.I)),
    ("courier", re.compile(r"\b(?:courier|parcel|dispatch|consignment|awb|tracking\s+(?:no|number)|blue\s*dart|dtdc|delhivery|fedex|dhl)\b", re.I)),
    ("printing", re.compile(r"\b(?:business|visiting)\s+cards?\b|\b(?:print\s*outs?|photocop\w+|xerox|binding)\b", re.I)),
    ("employee_transport", re.compile(r"\b(?:shuttle|office\s+bus|pick\s*(?:up)?\s*(?:and|&)\s*drop|night\s+drop|cab\s+(?:route|roster)|transport\s+(?:facility|route))\b", re.I)),
    ("guest_house", re.compile(r"\b(?:guest\s*house|accommodation|company\s+flat|stay\s+arrangement)\b", re.I)),
    ("seating", re.compile(r"\b(?:seat(?:ing)?\s+(?:allocation|change|request)|desk\s+(?:allocation|move|change)|workstation|shift\s+(?:my\s+)?(?:seat|desk)|new\s+seat)\b", re.I)),
    ("visitor", re.compile(r"\b(?:visitors?|guests?\s+(?:coming|visiting|arriving)|candidate\s+(?:coming|visiting)|interview\s+candidate)\b", re.I)),
    ("parking", re.compile(r"\b(?:parking|car\s+park|parking\s+slot|parking\s+sticker)\b", re.I)),
    ("furniture", re.compile(r"\b(?:chair|desk|table|drawer|cabinet|pedestal)\b.*\b(?:broken|repair|wobbl\w*|not\s+working|need|new)\b", re.I)),
    ("electrical", re.compile(r"\b(?:socket|power\s+point|switch\s*board|ups|no\s+power|tripp\w*|mcb)\b", re.I)),
    ("plumbing", re.compile(r"\b(?:tap|flush|drain|clog\w*|blocked\s+(?:toilet|sink|drain)|water\s+leak\w*|seepage)\b", re.I)),
    ("pantry", re.compile(r"\b(?:coffee\s+machine|water\s+(?:dispenser|cooler|purifier)|tea\s+(?:machine|vending)|vending\s+machine)\b", re.I)),
    ("lost_found", re.compile(r"\b(?:lost|misplaced|left\s+behind|found\s+a)\b.*\b(?:wallet|phone|bag|keys?|card|bottle|laptop|umbrella)\b", re.I)),
    ("hvac", re.compile(r"\b(?:a\.?c\.?|air\s*con\w*|cooling|too\s+(?:hot|cold))\b.*\b(?:not|isn'?t|stopped|leak|noise|working|broken)\b|\bac\s+(?:not|is\s+not)\b", re.I)),
    ("maintenance", re.compile(r"\b(?:leak\w*|broken|repair|fix|not\s+working|tube\s*light|bulb|fan|socket|switch|door|lock|tap|flush|seepage)\b", re.I)),
    ("it_support", re.compile(r"\b(?:laptop|wi-?fi|internet|printer|password|vpn|outlook|monitor\s+not|system\s+not|keyboard\s+not)\b", re.I)),
    ("housekeeping", re.compile(r"\b(?:clean\w*|washroom|restroom|toilet|dustbin|garbage|sweep|mop|pantry)\b", re.I)),
    ("supplies", re.compile(r"\b(?:stationery|notebooks?|pens?|markers?|stapler|mouse|keyboard|headphones?|headset|chargers?|a4\s+paper)\b", re.I)),
    ("travel", re.compile(r"\b(?:cab|taxi|airport|pick\s*up|drop|flight|hotel|travel)\b", re.I)),
]


def heuristic_decision(payload: dict, *, legacy_event_type: Optional[str] = None) -> AgentDecision:
    text = (payload.get("this_message") or "").strip()
    if text == "(empty)":
        text = ""
    subject = payload.get("subject") or ""
    in_case = bool(payload.get("this_thread_case"))
    name = ((payload.get("requester") or {}).get("name") or "").split(" ")[0]
    hello = f"Hi {name}," if name else "Hi,"
    sign = payload.get("SIGNATURE") or "Admin Desk"
    legacy = (legacy_event_type or "").upper()

    if not text and not in_case:
        return AgentDecision(
            intents=[AgentIntent(type="empty", category="general")],
            reply_to_requester=(
                f"{hello}\n\nYour mail seems to have come through empty - could you resend it with the details?\n\n{sign}"
            ),
            confidence=0.9,
            source="rules",
        )
    first_line = text.splitlines()[0] if text else ""
    if not in_case and text and len(text.split()) <= 6 and (_GREETING.match(first_line) or _GREETING.match(text)):
        return AgentDecision(
            intents=[AgentIntent(type="small_talk", category="general")],
            reply_to_requester=_greeting_reply(hello, sign),
            confidence=0.85,
            source="rules",
        )
    if in_case and text and len(text.split()) <= 6 and _THANKS.match(text):
        return AgentDecision(intents=[AgentIntent(type="small_talk")], reply_to_requester="", confidence=0.8, source="rules")
    ref = _CASE_REF.search(f"{subject}\n{text}")
    if text and len(text.split()) <= 25 and _STATUS.search(text) and (in_case or ref or payload.get("OPEN_CASES")):
        return AgentDecision(
            intents=[AgentIntent(type="status", case_reference=ref.group(1).upper() if ref else None)],
            confidence=0.75,
            source="rules",
        )

    # Existing specialised flows keep ownership of what they already understand.
    if legacy and legacy not in {"GENERAL", "UNKNOWN"}:
        return AgentDecision(intents=[AgentIntent(type="new_request", category=_legacy_category(legacy))], source="rules")
    if in_case:
        return AgentDecision(intents=[AgentIntent(type="update_case", category="legacy")], source="rules")

    for category, pattern in _RULE_CATEGORIES:
        if pattern.search(f"{subject}\n{text}"):
            summary = _clip(first_line or subject, 80)
            return AgentDecision(
                intents=[AgentIntent(type="new_request", category=category, summary=summary, details={"description": _clip(text, 600)})],
                reply_to_requester=(
                    f"{hello}\n\nThanks for letting us know. I've logged this as [[REF1]] and passed it to the right team - "
                    f"we'll keep you posted here.\n\n{sign}"
                ),
                confidence=0.6,
                source="rules",
            )
    return AgentDecision(intents=[AgentIntent(type="new_request", category="legacy")], source="rules")


def _legacy_category(event_type: str) -> str:
    return {"MEETING_ROOM": "meeting_room", "INVOICE": "invoice"}.get(event_type, "legacy")


def _greeting_reply(hello: str, sign: str) -> str:
    return (
        f"{hello}\n\nGood to hear from you! This is the Admin Desk - I can help with repairs and facility issues, "
        "IT help, housekeeping, visitor passes, parking, gate passes, couriers, office supplies, travel and cabs, "
        "seating, events, onboarding and meeting rooms.\n\n"
        f"How can I help you today? Just reply with what you need.\n\n{sign}"
    )
