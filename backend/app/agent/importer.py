"""Bulk company data import (CSV or Excel) with a preview before anything is saved."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Callable

from sqlmodel import Session, select

from app.models.company import Department, KnowledgeEntry
from app.models.org import Person, Resource, Vendor

TEMPLATES: dict[str, list[str]] = {
    "employees": ["email", "name", "department", "role", "manager_email"],
    "departments": ["code", "name", "categories", "primary_email", "backup_emails", "approver_email", "sla_hours", "spend_approval_limit"],
    "resources": ["name", "type", "capacity", "floor", "video_conferencing", "display", "near_department"],
    "vendors": ["name", "category", "contact_email", "location"],
    "knowledge": ["key", "section", "title", "content"],
}

EXAMPLES: dict[str, list[str]] = {
    "employees": ["riya.shah@yourco.com", "Riya Shah", "Engineering", "EMPLOYEE", "priya.manager@yourco.com"],
    "departments": ["FACILITIES", "Facilities & Maintenance", "maintenance; hvac; electrical", "facilities@yourco.com", "", "", "8", "0"],
    "resources": ["Board Room 1", "MEETING_ROOM", "12", "3", "yes", "yes", "Sales"],
    "vendors": ["QuickRide Corporate Cabs", "transport", "bookings@quickride.com", "Gurugram"],
    "knowledge": ["faq_canteen", "faq", "Canteen timings", "Canteen is open 8:30 AM - 6 PM on weekdays."],
}

_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")


def template_csv(kind: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(TEMPLATES[kind])
    writer.writerow(EXAMPLES[kind])
    return buf.getvalue()


def read_rows(filename: str, content: bytes) -> list[dict[str, str]]:
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        rows = list(wb.active.iter_rows(values_only=True))
        if not rows:
            return []
        header = [_key(h) for h in rows[0]]
        return [
            {header[i]: ("" if v is None else str(v).strip()) for i, v in enumerate(r) if i < len(header) and header[i]}
            for r in rows[1:]
            if any(v not in (None, "") for v in r)
        ]
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [{_key(k): (v or "").strip() for k, v in row.items() if k} for row in reader if any((v or "").strip() for v in row.values())]


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _list(value: str) -> list[str]:
    return [p.strip() for p in re.split(r"[;,|]", value or "") if p.strip()]


def _bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"yes", "y", "true", "1", "available"}


def _num(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "")) if str(value).strip() else default
    except ValueError:
        return default


def run_import(session: Session, tenant_id: str, kind: str, rows: list[dict[str, str]], *, commit: bool) -> dict:
    if kind not in TEMPLATES:
        raise ValueError(f"Unknown import type: {kind}")
    handler: Callable = globals()[f"_import_{kind}"]
    created, updated, errors = 0, 0, []
    preview = []
    for i, row in enumerate(rows, start=2):
        try:
            action, label = handler(session, tenant_id, row, apply=commit)
        except ValueError as exc:
            errors.append({"row": i, "error": str(exc)})
            continue
        created += action == "new"
        updated += action == "update"
        if len(preview) < 50:
            preview.append({"row": i, "action": action, "item": label})
    if commit:
        session.commit()
    else:
        session.rollback()
    return {"kind": kind, "committed": commit, "new": created, "updated": updated, "errors": errors, "preview": preview, "total": len(rows)}


def _import_employees(session: Session, tid: str, row: dict, *, apply: bool) -> tuple[str, str]:
    email = row.get("email", "").lower()
    if not _EMAIL.match(email):
        raise ValueError(f"invalid email '{email}'")
    name = row.get("name") or ""
    if not name:
        raise ValueError("name is required")
    person = session.exec(select(Person).where(Person.email == email)).first()
    action = "update" if person else "new"
    manager = None
    if row.get("manager_email"):
        manager = session.exec(select(Person).where(Person.email == row["manager_email"].lower())).first()
    if apply:
        person = person or Person(tenant_id=tid, email=email, name=name)
        person.name = name
        person.department = row.get("department") or person.department
        person.role = (row.get("role") or person.role or "EMPLOYEE").upper()
        if manager:
            person.manager_id = manager.person_id
        session.add(person)
        session.flush()
    return action, f"{name} <{email}>"


def _import_departments(session: Session, tid: str, row: dict, *, apply: bool) -> tuple[str, str]:
    code = re.sub(r"[^A-Z0-9_]+", "_", (row.get("code") or "").upper()).strip("_")
    if not code or not row.get("name"):
        raise ValueError("code and name are required")
    for field in ("primary_email", "approver_email"):
        if row.get(field) and not _EMAIL.match(row[field].lower()):
            raise ValueError(f"invalid {field} '{row[field]}'")
    dept = session.exec(select(Department).where(Department.tenant_id == tid, Department.code == code)).first()
    action = "update" if dept else "new"
    if apply:
        dept = dept or Department(tenant_id=tid, code=code, name=row["name"])
        dept.name = row["name"]
        if row.get("categories"):
            dept.categories = [c.lower().replace(" ", "_") for c in _list(row["categories"])]
        if row.get("primary_email"):
            dept.primary_email = row["primary_email"].lower()
        if row.get("backup_emails"):
            dept.backup_emails = [e.lower() for e in _list(row["backup_emails"]) if _EMAIL.match(e.lower())]
        if row.get("approver_email"):
            dept.approver_email = row["approver_email"].lower()
        if row.get("sla_hours"):
            dept.sla_hours = int(_num(row["sla_hours"], 24))
        if row.get("spend_approval_limit"):
            dept.spend_approval_limit = _num(row["spend_approval_limit"])
        session.add(dept)
        session.flush()
    return action, f"{code} - {row['name']}"


def _import_resources(session: Session, tid: str, row: dict, *, apply: bool) -> tuple[str, str]:
    name = row.get("name") or ""
    rtype = (row.get("type") or "MEETING_ROOM").upper().replace(" ", "_")
    if not name:
        raise ValueError("name is required")
    if rtype not in {"MEETING_ROOM", "PARKING_SLOT", "DESK", "CABIN", "LOCKER"}:
        raise ValueError(f"type must be MEETING_ROOM, PARKING_SLOT, DESK, CABIN or LOCKER (got '{rtype}')")
    res = session.exec(select(Resource).where(Resource.tenant_id == tid, Resource.name == name)).first()
    action = "update" if res else "new"
    if apply:
        res = res or Resource(tenant_id=tid, type=rtype, name=name)
        res.type = rtype
        attrs = dict(res.attributes or {})
        if row.get("capacity"):
            attrs["capacity"] = int(_num(row["capacity"]))
        if row.get("floor"):
            attrs["floor"] = row["floor"]
        if row.get("video_conferencing"):
            attrs["video_conferencing"] = _bool(row["video_conferencing"])
        if row.get("display"):
            attrs["display"] = attrs["presentation_display"] = _bool(row["display"])
        if row.get("near_department"):
            attrs["near_department"] = row["near_department"]
        res.attributes = attrs
        session.add(res)
        session.flush()
    return action, f"{rtype} {name}"


def _import_vendors(session: Session, tid: str, row: dict, *, apply: bool) -> tuple[str, str]:
    name = row.get("name") or ""
    email = (row.get("contact_email") or "").lower()
    if not name or not _EMAIL.match(email):
        raise ValueError("name and a valid contact_email are required")
    vendor = session.exec(select(Vendor).where(Vendor.tenant_id == tid, Vendor.name == name)).first()
    action = "update" if vendor else "new"
    if apply:
        vendor = vendor or Vendor(tenant_id=tid, name=name, category=row.get("category") or "general", contact_email=email)
        vendor.category = row.get("category") or vendor.category
        vendor.contact_email = email
        vendor.location = row.get("location") or vendor.location
        session.add(vendor)
        session.flush()
    return action, name


def _import_knowledge(session: Session, tid: str, row: dict, *, apply: bool) -> tuple[str, str]:
    key = _key(row.get("key") or row.get("title"))
    if not key or not row.get("content"):
        raise ValueError("key (or title) and content are required")
    entry = session.exec(select(KnowledgeEntry).where(KnowledgeEntry.tenant_id == tid, KnowledgeEntry.key == key)).first()
    action = "update" if entry else "new"
    if apply:
        entry = entry or KnowledgeEntry(tenant_id=tid, key=key, title=row.get("title") or key, content=row["content"])
        entry.title = row.get("title") or entry.title
        entry.section = row.get("section") or entry.section
        entry.content = row["content"]
        session.add(entry)
        session.flush()
    return action, row.get("title") or key
