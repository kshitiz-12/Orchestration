from __future__ import annotations

from sqlmodel import Session, desc, select

from app.core.database import get_engine
from app.models import Communication, Outcome, RawEmailEvent


def main() -> None:
    with Session(get_engine()) as s:
        print("=== LATEST INBOUND ===")
        for e in s.exec(select(RawEmailEvent).order_by(desc(RawEmailEvent.created_at)).limit(8)).all():
            subj = (e.subject or "")[:80]
            print(f"{e.created_at} from={e.sender} subj={subj!r}")
            body = (e.body_text or "")[:200].replace("\n", " ")
            if body:
                print(f"  body: {body}")

        outcomes = s.exec(select(Outcome).order_by(desc(Outcome.created_at)).limit(20)).all()
        print("\n=== RECENT CASES ===")
        travel = []
        for o in outcomes:
            f = o.facts or {}
            cat = str(f.get("agent_category") or o.category or "")
            title = o.title or ""
            is_travel = (
                "travel" in cat.lower()
                or "flight" in title.lower()
                or bool(f.get("flight_options"))
                or bool(f.get("travel_flight"))
            )
            mark = " [TRAVEL/FLIGHT]" if is_travel else ""
            print(
                f"{o.created_at} {o.case_reference} stage={f.get('agent_stage')} "
                f"cat={cat}{mark}"
            )
            print(f"  title={title!r} requester={o.requester_email}")
            if is_travel:
                travel.append(o)
                print(f"  details={f.get('details')}")
                print(f"  missing={f.get('missing')}")
                opts = f.get("flight_options")
                if opts is not None:
                    print(f"  flight_options_count={len(opts)}")
                    if opts:
                        print(f"  first_option={opts[0]}")

        target = travel[0] if travel else (outcomes[0] if outcomes else None)
        if not target:
            print("\nNo cases found")
            return

        print(f"\n=== OUTBOUND FOR {target.case_reference} ===")
        for c in s.exec(
            select(Communication)
            .where(Communication.outcome_id == target.outcome_id)
            .order_by(desc(Communication.sent_at))
        ).all()[:6]:
            print(f"--- {c.sent_at} to={c.recipients} subj={c.subject!r}")
            print((c.body or "")[:1200])
            print()


if __name__ == "__main__":
    main()
