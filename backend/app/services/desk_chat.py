"""Admin chat: answer from company records, and save an Excel file once its sheets are recognised."""

from __future__ import annotations

import io
import os
import re

from sqlmodel import Session, func, select

from app.agent.company_seed import is_placeholder
from app.agent.importer import prepare_company_import, run_bundle_import
from app.api.routes.setup import last_excel_upload, remember_excel_upload
from app.models.company import Department
from app.models.org import Location, Person, Resource, StockSku, Vendor
from app.models.outcome import Outcome
from app.services.operator_inbox import OPEN_OUTCOME_STATUSES

_KIND_WORDS = {
    "locations": "offices",
    "departments": "teams",
    "employees": "people",
    "resources": "rooms",
    "vendors": "vendors",
    "stock": "stock items",
    "knowledge": "policies",
    "site_services": "services",
    "cost_centres": "cost centres",
}


def company_snapshot(session: Session, tenant_id: str) -> dict:
    def rows(model, limit: int = 25):
        return session.exec(
            select(model).where(model.tenant_id == tenant_id).order_by(model.created_at.desc()).limit(limit)
        ).all()

    offices = rows(Location, 40)
    people = rows(Person, 25)
    vendors = rows(Vendor, 25)
    stock = rows(StockSku, 25)
    rooms = session.exec(
        select(Resource).where(Resource.tenant_id == tenant_id, Resource.type == "MEETING_ROOM").limit(20)
    ).all()
    open_cases = session.exec(
        select(Outcome)
        .where(Outcome.tenant_id == tenant_id, Outcome.status.in_(list(OPEN_OUTCOME_STATUSES)))  # type: ignore
        .limit(8)
    ).all()
    people_total = session.exec(select(func.count()).select_from(Person).where(Person.tenant_id == tenant_id)).one()
    office_total = session.exec(select(func.count()).select_from(Location).where(Location.tenant_id == tenant_id)).one()
    pending_teams = [
        d.code
        for d in session.exec(select(Department).where(Department.tenant_id == tenant_id, Department.is_active == True)).all()  # noqa: E712
        if is_placeholder(d.primary_email)
    ]
    return {
        "offices": {"total": int(office_total or 0), "items": [
            {"code": p.code, "name": p.name, "type": p.type} for p in offices
        ]},
        "people": {"total": int(people_total or 0), "items": [
            {"name": p.name, "email": p.email, "role": p.role} for p in people
        ]},
        "vendors": [{"name": v.name, "category": v.category, "email": v.contact_email} for v in vendors],
        "stock": [{"sku": s.sku_code, "name": s.name, "qty": s.qty_on_hand} for s in stock],
        "meeting_rooms": [r.name for r in rooms],
        "open_requests": [
            {"case": o.case_reference, "title": o.title, "status": o.status, "from": o.requester_email}
            for o in open_cases
        ],
        "teams_needing_email": pending_teams[:20],
        "excel_upload": last_excel_upload(session, tenant_id),
    }


def answer_question(session: Session, tenant_id: str, message: str, history: list[dict] | None = None) -> str:
    facts = company_snapshot(session, tenant_id)
    text = (message or "").strip()
    if not text:
        return "Ask about offices, people, vendors, stock, or open requests. Or drop an Excel file in this chat."
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return _from_records(text, facts)
    from app.core.config import get_settings

    settings = get_settings()
    if settings.gemini_api_key or settings.gemini_api_key_secondary:
        try:
            from app.ai.gemini import GeminiProvider

            data, _meta = GeminiProvider().generate_json(
                system_instruction=(
                    "You are the workplace admin desk. Answer in plain sentences using ONLY the records JSON. "
                    "If the records do not contain the answer, say so. Do not invent emails, amounts, warranty, "
                    "or counts. Return JSON with one key: reply."
                ),
                payload={"question": text, "recent_chat": (history or [])[-6:], "records": facts},
                temperature=0.1,
            )
            reply = str((data or {}).get("reply") or "").strip()
            if reply:
                return reply
        except Exception:
            pass
    return _from_records(text, facts)


def import_workbook(session: Session, tenant_id: str, filename: str, content: bytes, note: str = "") -> dict:
    try:
        bundles, source = prepare_company_import(filename, content)
    except ValueError:
        reply = _outline(filename, content)
        if note.strip():
            reply = f"{reply}\n\n{answer_question(session, tenant_id, note)}"
        return {"reply": reply, "synced": False, "upload": None, "kinds": []}
    result = run_bundle_import(session, tenant_id, bundles, commit=True, source=source)
    upload = remember_excel_upload(session, tenant_id, filename, result)
    counts = {part["kind"]: part["total"] for part in result.get("parts") or []}
    words = [f"{counts[k]} {_KIND_WORDS.get(k, k)}" for k in counts]
    problems = len(result.get("errors") or [])
    reply = (
        f"This file is {', '.join(words) or 'company data'}. "
        f"I added {result.get('new', 0)}. {result.get('updated', 0)} were already on file and were refreshed."
    )
    if "locations" not in counts and "employees" not in counts:
        reply += " Offices and people stay as they are, because this file does not list them."
    if problems:
        reply += f" {problems} rows were left out because a required field was missing or invalid."
    if note.strip():
        reply = f"{reply}\n\n{answer_question(session, tenant_id, note)}"
    return {"reply": reply, "synced": True, "upload": upload, "kinds": list(counts)}


def _from_records(message: str, facts: dict) -> str:
    text = message.lower()
    offices = facts["offices"]["items"]
    people = facts["people"]
    if re.search(r"office|branch|location|campus", text):
        names = ", ".join(f"{o['name']} ({o['code']})" for o in offices[:12] if o.get("name")) or "none yet"
        return f"There are {facts['offices']['total']} offices on file: {names}."
    if re.search(r"people|employee|staff|who works", text):
        names = ", ".join(p["name"] for p in people["items"][:12] if p.get("name")) or "none yet"
        return f"{people['total']} people are on file. Recent names: {names}."
    if "vendor" in text:
        names = ", ".join(v["name"] for v in facts["vendors"][:12]) or "none yet"
        return f"{len(facts['vendors'])} vendors are on file: {names}."
    if re.search(r"stock|item|inventory", text):
        names = ", ".join(f"{s['name']} ({s['qty']})" for s in facts["stock"][:12]) or "none yet"
        return f"Stock on file: {names}."
    if re.search(r"room|meeting", text):
        names = ", ".join(facts["meeting_rooms"][:12]) or "none yet"
        return (
            f"{len(facts['meeting_rooms'])} meeting rooms are listed: {names}. "
            "A room is busy when a booking overlaps that time."
        )
    if re.search(r"open|request|case|past due|waiting", text):
        cases = facts["open_requests"]
        if not cases:
            return "There are no open requests."
        lines = "; ".join(f"{c['case']}: {c['title'] or c['status']}" for c in cases)
        return f"{len(cases)} open requests are in view: {lines}."
    if re.search(r"excel|upload|percent", text):
        upload = facts.get("excel_upload") or {}
        if not upload:
            return "No Excel file has been saved yet. Drop one in this chat."
        return (
            f"{upload.get('percent', 0)}% of {upload.get('filename') or 'the last Excel'} is saved "
            f"({upload.get('saved', 0)} of {upload.get('total', 0)} rows)."
        )
    if re.search(r"team|mailbox|email setup", text):
        pending = facts["teams_needing_email"]
        if not pending:
            return "Every team has a mailbox, or no teams are loaded yet."
        return f"{len(pending)} teams still need a work email: {', '.join(pending[:12])}."
    return (
        "I answer from the company records: offices, people, vendors, stock, meeting rooms, and open requests. "
        "Ask about one of those, or drop an Excel file and I will read it and save what fits."
    )


def _outline(filename: str, content: bytes) -> str:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        return f"I could not read {filename or 'that file'} as an Excel workbook, so nothing was saved."
    try:
        names = [sheet.title for sheet in wb.worksheets][:12]
    finally:
        wb.close()
    listed = ", ".join(names) or "no sheets"
    return (
        f"{filename or 'This file'} has sheets such as {listed}. "
        "None of them are offices, people, vendors, or stock, so I did not change the company records."
    )
