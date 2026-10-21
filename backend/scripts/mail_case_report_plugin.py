"""Pytest plugin: after each test, record inbound mail and outbound replies.

Loaded only when requested: pytest -p scripts.mail_case_report_plugin
Writes docs/EMAIL_CASE_REPORT.md at the end of the session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import os

import pytest
from sqlmodel import select

_ROWS: list[dict] = []
_BEFORE: dict[str, tuple[set[str], set[str]]] = {}


def _clip(text: str, limit: int = 900) -> str:
    raw = (text or "").replace("\r\n", "\n").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1] + "…"


def _session(item):
    names = set(getattr(item, "fixturenames", []) or [])
    if not names.intersection({"session", "client", "auth_headers"}):
        return None
    try:
        return item._request.getfixturevalue("session")
    except Exception:
        return None


def _ids(session) -> tuple[set[str], set[str]]:
    from app.models.intake import RawEmailEvent
    from app.models.outcome import Communication

    events = set(session.exec(select(RawEmailEvent.event_id)).all())
    mails = set(session.exec(select(Communication.message_id)).all())
    return events, mails


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    key = item.nodeid
    if report.when == "setup" and report.passed:
        session = _session(item)
        if session is not None:
            try:
                _BEFORE[key] = _ids(session)
            except Exception:
                _BEFORE[key] = (set(), set())
        return
    if report.when == "setup" and not report.passed:
        _ROWS.append(
            {
                "nodeid": key,
                "file": Path(str(item.fspath)).name,
                "name": item.name,
                "doc": (item.obj.__doc__ or "").strip() if hasattr(item, "obj") else "",
                "outcome": "error",
                "error": _clip(str(report.longrepr), 500),
                "inbound": [],
                "outbound": [],
                "cases": [],
            }
        )
        return
    if report.when != "call":
        return
    row = {
        "nodeid": key,
        "file": Path(str(item.fspath)).name,
        "name": item.name,
        "doc": (item.obj.__doc__ or "").strip() if hasattr(item, "obj") else "",
        "outcome": "passed" if report.passed else ("failed" if report.failed else "skipped"),
        "error": "",
        "inbound": [],
        "outbound": [],
        "cases": [],
    }
    if report.failed:
        row["error"] = _clip(str(report.longrepr), 500)
    session = _session(item)
    if session is None:
        _ROWS.append(row)
        return
    try:
        from app.models.intake import RawEmailEvent
        from app.models.outcome import Communication, Outcome

        before_events, before_mails = _BEFORE.get(key, (set(), set()))
        events = session.exec(select(RawEmailEvent)).all()
        mails = session.exec(select(Communication)).all()
        cases = session.exec(select(Outcome)).all()
        for event in events:
            if event.event_id in before_events:
                continue
            row["inbound"].append(
                {
                    "sender": event.sender,
                    "subject": event.subject or "",
                    "body": _clip(event.body_text or event.body_for_ai or ""),
                }
            )
        for mail in mails:
            if mail.message_id in before_mails:
                continue
            recipients = mail.recipients if isinstance(mail.recipients, list) else [mail.recipients]
            row["outbound"].append(
                {
                    "sender": mail.sender,
                    "to": ", ".join(str(r) for r in recipients if r),
                    "type": mail.communication_type,
                    "subject": mail.subject or "",
                    "body": _clip(mail.body or ""),
                }
            )
        for case in cases:
            facts = case.facts or {}
            row["cases"].append(
                {
                    "ref": case.case_reference,
                    "title": case.title or "",
                    "status": case.status,
                    "stage": str(facts.get("agent_stage") or ""),
                    "priority": case.priority or "",
                    "decision": str((facts.get("record_decision") or {}).get("action") or ""),
                }
            )
    except Exception as exc:  # noqa: BLE001
        row["error"] = (row["error"] + "\n" + f"report capture: {exc}")[:500]
    _ROWS.append(row)


def pytest_sessionfinish(session, exitstatus):
    root = Path(__file__).resolve().parents[2]
    path = Path(os.environ.get("MAIL_CASE_REPORT") or (root / "docs" / "EMAIL_CASE_REPORT.md"))
    path.write_text(_render(exitstatus), encoding="utf-8")


def _render(exitstatus: int) -> str:
    passed = sum(1 for r in _ROWS if r["outcome"] == "passed")
    failed = sum(1 for r in _ROWS if r["outcome"] == "failed")
    errored = sum(1 for r in _ROWS if r["outcome"] == "error")
    skipped = sum(1 for r in _ROWS if r["outcome"] == "skipped")
    with_mail = sum(1 for r in _ROWS if r["inbound"] or r["outbound"])
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Email case report",
        "",
        f"Run at {when}. Pytest exit status {exitstatus}.",
        "Each case below is one automated test. Inbound is the mail the desk received. Outbound is the reply or work order it stored. Nothing here was sent to a real mailbox.",
        "",
        "## Summary",
        "",
        f"- Cases: {len(_ROWS)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Errors: {errored}",
        f"- Skipped: {skipped}",
        f"- Cases that stored mail: {with_mail}",
        "",
    ]
    if failed or errored:
        lines += ["## Failed cases", ""]
        for row in _ROWS:
            if row["outcome"] not in {"failed", "error"}:
                continue
            lines.append(f"- `{row['nodeid']}`")
        lines.append("")

    by_file: dict[str, list[dict]] = {}
    for row in _ROWS:
        by_file.setdefault(row["file"], []).append(row)

    lines.append("## Cases")
    lines.append("")
    for filename in sorted(by_file):
        rows = by_file[filename]
        file_failed = sum(1 for r in rows if r["outcome"] in {"failed", "error"})
        lines.append(f"### {filename}")
        lines.append("")
        lines.append(f"{len(rows)} cases, {file_failed} failed.")
        lines.append("")
        for row in rows:
            mark = row["outcome"].upper()
            lines.append(f"#### {row['name']} — {mark}")
            lines.append("")
            if row["doc"]:
                lines.append(row["doc"])
                lines.append("")
            if row["cases"]:
                lines.append("Case state:")
                lines.append("")
                for case in row["cases"]:
                    extra = f", decision {case['decision']}" if case["decision"] else ""
                    stage = f", stage {case['stage']}" if case["stage"] else ""
                    lines.append(
                        f"- {case['ref']}: {case['title']} ({case['status']}, {case['priority']}{stage}{extra})"
                    )
                lines.append("")
            if row["inbound"]:
                lines.append("Email received:")
                lines.append("")
                for mail in row["inbound"]:
                    lines.append(f"- From: {mail['sender']}")
                    lines.append(f"- Subject: {mail['subject']}")
                    lines.append("")
                    lines.append("```")
                    lines.append(mail["body"] or "(empty body)")
                    lines.append("```")
                    lines.append("")
            if row["outbound"]:
                lines.append("Reply sent:")
                lines.append("")
                for mail in row["outbound"]:
                    lines.append(f"- To: {mail['to'] or '(none)'}")
                    lines.append(f"- From: {mail['sender']}")
                    lines.append(f"- Type: {mail['type']}")
                    lines.append(f"- Subject: {mail['subject']}")
                    lines.append("")
                    lines.append("```")
                    lines.append(mail["body"] or "(empty body)")
                    lines.append("```")
                    lines.append("")
            if not row["inbound"] and not row["outbound"]:
                lines.append("No email was stored for this case.")
                lines.append("")
            if row["error"] and row["outcome"] in {"failed", "error"}:
                lines.append("Failure:")
                lines.append("")
                lines.append("```")
                lines.append(row["error"])
                lines.append("```")
                lines.append("")
    return "\n".join(lines) + "\n"
