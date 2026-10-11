from __future__ import annotations

from sqlmodel import Session, desc, select

from app.core.database import get_engine
from app.models import Communication, Outcome, RawEmailEvent, ServiceTicket


def main() -> None:
    with Session(get_engine()) as s:
        events = s.exec(select(RawEmailEvent).order_by(desc(RawEmailEvent.created_at)).limit(5)).all()
        print(f"=== RAW INBOUND ({len(events)} latest) ===")
        for e in events:
            print(
                f"{e.created_at} stage={e.processing_stage} from={e.sender} "
                f"subj={e.subject!r}"
            )

        outcomes = s.exec(select(Outcome).order_by(desc(Outcome.created_at)).limit(5)).all()
        if not outcomes:
            print("\nNo outcomes yet")
            return

        o = outcomes[0]
        print("\n=== LATEST CASE ===")
        print(f"case: {o.case_reference}")
        print(f"created: {o.created_at}")
        print(f"status: {o.status}")
        print(f"category: {o.category}")
        print(f"template: {o.template_code}")
        print(f"title: {o.title}")
        print(f"requester: {o.requester_email}")
        print(f"priority: {o.priority}")
        print(f"summary: {(o.summary or '')[:500]}")
        facts = o.facts or {}
        if facts:
            interesting = {
                k: facts[k]
                for k in (
                    "event_type",
                    "department",
                    "department_code",
                    "location",
                    "place",
                    "missing_information",
                    "waiting_on",
                )
                if k in facts
            }
            if interesting:
                print(f"facts: {interesting}")

        tickets = s.exec(
            select(ServiceTicket)
            .where(ServiceTicket.outcome_id == o.outcome_id)
            .order_by(desc(ServiceTicket.created_at))
        ).all()
        print(f"\n=== TICKETS ({len(tickets)}) ===")
        for t in tickets[:8]:
            print(
                f"  {t.reference} | {t.status} | dept={t.department_code} | "
                f"assignee={t.assignee_email} | {t.title}"
            )

        comms = s.exec(
            select(Communication)
            .where(Communication.outcome_id == o.outcome_id)
            .order_by(desc(Communication.sent_at))
        ).all()
        print(f"\n=== MAIL SENT/LOGGED ({len(comms)}) ===")
        for c in comms[:8]:
            print(
                f"  {c.sent_at} type={c.communication_type} from={c.sender} "
                f"to={c.recipients} subj={c.subject!r}"
            )
            print((c.body or "")[:500])
            print("---")

        print("\n=== RECENT CASES ===")
        for x in outcomes:
            print(
                f"  {x.created_at} {x.case_reference} {x.status} "
                f"{x.requester_email} | {x.title}"
            )


if __name__ == "__main__":
    main()
