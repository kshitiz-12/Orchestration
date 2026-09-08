"""Load ~30 fictional test emails (incl. duplicates, missing info, multi-issue)."""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.core.database import get_engine, init_db
from app.engine.pipeline import ProcessingPipeline
from app.ai.service import LLMService
from app.ai.gemini import HeuristicProvider
from app.models.org import Tenant
from app.services.intake import IntakeService
from scripts.seed import seed


EMAILS = [
    {
        "message_id": "demo-onb-1",
        "thread_id": "thread-onb-1",
        "sender": "hr@acme.demo",
        "subject": "New joiner workplace readiness",
        "body": "Please arrange onboarding for Riya Shah joining tomorrow in Engineering reporting to Priya Manager. Hybrid work model. No permanent seat available.",
    },
    {
        "message_id": "demo-onb-1-dup",
        "thread_id": "thread-onb-1",
        "sender": "hr@acme.demo",
        "subject": "New joiner workplace readiness",
        "body": "Please arrange onboarding for Riya Shah joining tomorrow in Engineering reporting to Priya Manager. Hybrid work model. No permanent seat available.",
        "force_same_id": "demo-onb-1",  # true duplicate message id handled separately
    },
    {
        "message_id": "demo-room-1",
        "thread_id": "thread-room-1",
        "sender": "employee4@acme.demo",
        "subject": "Need a room for 15 people",
        "body": "I need a room/resources for tomorrow for 15 people.",
    },
    {
        "message_id": "demo-room-1-reply",
        "thread_id": "thread-room-1",
        "sender": "employee4@acme.demo",
        "subject": "Re: Need a room for 15 people",
        "body": "2 PM to 4 PM.",
    },
    {
        "message_id": "demo-park-1",
        "thread_id": "thread-park-1",
        "sender": "employee1@acme.demo",
        "subject": "Assigned parking occupied",
        "body": "My assigned parking slot is occupied by another vehicle this morning.",
    },
    {
        "message_id": "demo-chair-1",
        "thread_id": "thread-chair-1",
        "sender": "employee2@acme.demo",
        "subject": "Chair missing at my seat",
        "body": "My chair is missing from my assigned seat. Please help.",
    },
    {
        "message_id": "demo-vnd-1",
        "thread_id": "thread-vnd-1",
        "sender": "procurement@acme.demo",
        "subject": "Vendor quality escalation - CleanSupply",
        "body": (
            "CleanSupply Partners delivered substituted items, some lots appear expired, "
            "quantity short, and billing looks overcharged vs rate card. Consider show-cause / suspend."
        ),
    },
    {
        "message_id": "demo-inv-1",
        "thread_id": "thread-inv-1",
        "sender": "billing@securechips.demo",
        "subject": "Invoice INV-2026-1001 for PO-2026-101",
        "body": "Please find invoice INV-2026-1001 amount as per PO-2026-101 quantity and unit rate. Vendor SecureChips Ltd.",
    },
    {
        "message_id": "demo-inv-2",
        "thread_id": "thread-inv-2",
        "sender": "billing@securechips.demo",
        "subject": "Invoice INV-2026-1002 mismatch",
        "body": "Invoice INV-2026-1002 for PO-2026-101 quantity 99 unit_rate 45000 amount 999999.",
    },
    {
        "message_id": "demo-inv-dup",
        "thread_id": "thread-inv-3",
        "sender": "billing@securechips.demo",
        "subject": "Invoice INV-2026-1001 resend",
        "body": "Resending invoice INV-2026-1001 for PO-2026-101.",
    },
    {
        "message_id": "demo-inv-bank",
        "thread_id": "thread-inv-4",
        "sender": "billing@securechips.demo",
        "subject": "Invoice INV-2026-1003 — update bank details",
        "body": "Invoice INV-2026-1003 for PO-2026-102. Please change our bank account and release payment immediately.",
    },
]

# Expand to ~30 with variations
for i in range(20):
    EMAILS.append(
        {
            "message_id": f"demo-burst-{i}",
            "thread_id": f"thread-burst-{i}",
            "sender": f"employee{(i % 10) + 1}@acme.demo",
            "subject": f"Facilities note {i}",
            "body": (
                "Chair missing near my desk."
                if i % 3 == 0
                else "Parking slot occupied again."
                if i % 3 == 1
                else f"General request {i} about workplace readiness."
            ),
        }
    )


def main(process: bool = True):
    init_db()
    with Session(get_engine()) as session:
        tid = seed(session)
        intake = IntakeService(session, tid)
        pipeline = ProcessingPipeline(session, tid, llm=LLMService(HeuristicProvider()))
        results = []
        for item in EMAILS:
            mid = item.get("force_same_id") or item["message_id"]
            res = intake.ingest(
                message_id=mid,
                thread_id=item["thread_id"],
                sender=item["sender"],
                recipients=["orchestration@prototype.local"],
                subject=item["subject"],
                body_text=item["body"],
                source="API",
            )
            if process and res["status"] == "queued":
                try:
                    out = pipeline.process_event(res["event_id"])
                    results.append({**res, **out})
                except Exception as exc:  # noqa: BLE001
                    results.append({**res, "error": str(exc)})
            else:
                results.append(res)
        queued = sum(1 for r in results if r.get("status") == "queued" or r.get("outcome_id"))
        dups = sum(1 for r in results if r.get("status") == "deduplicated")
        print(f"tenant={tid} processed_or_queued={queued} deduplicated={dups} total={len(results)}")


if __name__ == "__main__":
    main()
