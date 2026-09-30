"""What the admin desk can do, as a catalogue the agent reasons over.

The model only picks intents and categories; code in `desk.py` (or an existing specialised
flow for `runner="legacy"`) carries each capability out under the risk policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.playbooks import PLAYBOOKS


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    categories: tuple[str, ...]
    risk: str = "low"  # low: desk acts and informs admin | admin: admin decides first
    runner: str = "desk"  # desk | legacy (existing meeting-room / invoice flows)


TOOLS: tuple[Tool, ...] = (
    Tool("book_meeting_room", "Find, hold and confirm a meeting room, with catering, AV and guest parking.",
         ("meeting_room",), runner="legacy"),
    Tool("process_invoice", "Three-way match a vendor invoice against PO and receipt; payment needs finance approval.",
         ("invoice",), risk="admin", runner="legacy"),
    Tool("create_service_ticket", "Log a repair / IT / housekeeping / general issue and send the right team a work order.",
         ("maintenance", "hvac", "electrical", "plumbing", "housekeeping", "it_support", "laptop", "network", "courier", "general")),
    Tool("register_visitor", "Pre-register visitors on the gate manifest and issue pass codes.", ("visitor",)),
    Tool("allocate_parking", "Allot guest parking slots for a date from the free visitor slots.", ("parking",)),
    Tool("request_supplies", "Order office supplies; spend above the limit goes for approval.", ("supplies", "catering")),
    Tool("travel_request", "Send a cab / hotel / flight request to the travel desk with policy checks.", ("travel",)),
    Tool("onboarding_checklist", "Fan out new-joiner tasks to HR, IT and facilities.", ("onboarding",)),
    Tool("escalate_to_admin", "Sensitive work (access, HR, payments, purchases, security): admin decides first.",
         ("access_card", "hr_query", "security", "payment", "reimbursement", "purchase", "offboarding"), risk="admin"),
    Tool("answer_from_knowledge", "Answer questions from OFFICE_KNOWLEDGE only.", ()),
    Tool("case_status", "Tell the requester where their open case stands.", ()),
    Tool("update_case", "Add details or changes to an open case.", ()),
    Tool("cancel_case", "Cancel an open case and tell the team.", ()),
)


def tool_catalogue() -> list[dict]:
    """Compact catalogue for the agent prompt."""
    sensitive = {p.category for p in PLAYBOOKS if p.sensitive}
    out = []
    for tool in TOOLS:
        risk = "admin" if tool.risk == "admin" or (tool.categories and set(tool.categories) <= sensitive) else "low"
        out.append({"tool": tool.name, "does": tool.description, "categories": list(tool.categories), "risk": risk})
    return out


def legacy_categories() -> set[str]:
    return {c for t in TOOLS if t.runner == "legacy" for c in t.categories}
