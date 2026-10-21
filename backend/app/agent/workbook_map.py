"""Read company workbooks whose column names are not on the first row.

Onboarding files put a title and an instruction above the real header. Matching
those columns here avoids sending the whole file to Gemini.
"""

from __future__ import annotations

import io
import re
from typing import Optional

from app.agent.importer import TEMPLATES, _key
from app.agent.places import PLACE_TYPES

_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")

# Sheet-title fragments, most specific first.
_SHEET_KINDS: list[tuple[str, tuple[str, ...]]] = [
    ("cost_centres", ("cost_centre", "cost_center")),
    ("site_services", ("service_catalogue", "service_catalog")),
    ("knowledge", ("policy_register",)),
    ("stock", ("item_master", "stock_master")),
    ("vendors", ("vendor_master",)),
    ("resources", ("area_space", "space_register", "room_register")),
    ("employees", ("key_contact", "employee_master", "staff_register")),
    ("departments", ("org_hierarchy", "department_master", "team_register")),
    ("locations", ("location_register", "office_register", "branch_master", "location_master")),
]

_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "locations": {
        "code": ("location_code", "office_code", "branch_code", "site_code", "code"),
        "name": ("location_name", "office_name", "branch_name", "site_name", "name"),
        "type": ("location_type", "office_type", "place_type", "type"),
        "parent_code": ("parent_location_code", "parent_code", "parent_office_code"),
        "aliases": ("legacy_location_branch_code", "aliases", "alias"),
    },
    "departments": {
        "code": ("org_unit_code", "department_code", "team_code", "code"),
        "name": ("org_unit_name", "department_name", "team_name", "name"),
        "categories": ("categories", "category"),
        "primary_email": ("primary_email", "team_email", "email"),
        "location": ("location_code", "location", "office_code"),
    },
    "employees": {
        "email": ("email", "work_email", "primary_email"),
        "name": ("full_name", "employee_name", "name"),
        "department": ("department_organisation", "department", "org_unit_name"),
        "role": ("designation_role", "designation", "role"),
        "manager_email": ("manager_email",),
        "location": ("location_code", "location", "office_code"),
    },
    "resources": {
        "name": ("space_room_name", "room_name", "name"),
        "type": ("space_type", "room_type", "type"),
        "capacity": ("capacity", "seating_capacity"),
        "floor": ("floor_name_number", "floor_name", "floor"),
    },
    "vendors": {
        "name": ("vendor_legal_name", "vendor_name", "trade_name", "name"),
        "contact_email": ("primary_contact_email", "contact_email", "email"),
        "category": ("service_categories", "vendor_category", "category"),
        "location": ("country", "location"),
    },
    "stock": {
        "sku_code": ("item_code", "sku_code", "sku"),
        "name": ("item_name", "sku_name", "name"),
        "qty_on_hand": ("qty_on_hand", "quantity", "stock_on_hand"),
        "reorder_min": ("reorder_min", "min_qty", "minimum_qty"),
        "reorder_qty": ("reorder_qty", "reorder_quantity"),
        "unit": ("base_uom", "uom", "unit"),
        "location": ("location_code", "location"),
        "vendor_email": ("vendor_email",),
    },
    "knowledge": {
        "key": ("policy_code", "key"),
        "section": ("section", "policy_section"),
        "title": ("policy_name", "title", "name"),
        "content": ("policy_text", "policy_summary", "description", "content"),
    },
    "site_services": {
        "site": ("location_code", "site", "location"),
        "code": ("service_code", "code"),
        "name": ("service_name", "name"),
        "delivery_model": ("delivery_model",),
        "owner_department": ("owner_department", "department"),
    },
    "cost_centres": {
        "code": ("cost_centre_code", "cost_center_code", "code"),
        "name": ("cost_centre_name", "cost_center_name", "name"),
        "department": ("department",),
        "approver_name": ("approver_name",),
        "approver_email": ("approver_email",),
    },
}


def workbook_is_titled(content: bytes) -> bool:
    """True when the first sheet opens with a title, not a column header."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        sheet = wb.worksheets[0] if wb.worksheets else None
        if sheet is None:
            return False
        for row in sheet.iter_rows(max_row=3, values_only=True):
            cells = [c for c in row if c not in (None, "")]
            if not cells:
                continue
            return len(cells) < 3
        return False
    finally:
        wb.close()


def read_flexible_workbook(content: bytes) -> dict[str, list[dict[str, str]]]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    out: dict[str, list[dict[str, str]]] = {}
    try:
        for sheet in wb.worksheets:
            kind = _sheet_kind(sheet.title)
            if not kind:
                continue
            rows = [row for row in sheet.iter_rows(values_only=True) if any(c not in (None, "") for c in row)]
            header_at = _header_index(rows)
            if header_at is None:
                continue
            index = {_key(cell): i for i, cell in enumerate(rows[header_at]) if cell not in (None, "")}
            mapped = _map_rows(kind, index, rows[header_at + 1 :])
            if mapped:
                out.setdefault(kind, []).extend(mapped)
    finally:
        wb.close()
    return out


def _sheet_kind(title: str) -> Optional[str]:
    key = _key(title)
    for kind, hints in _SHEET_KINDS:
        if any(hint in key for hint in hints):
            return kind
    return None


def _header_index(rows: list[tuple]) -> Optional[int]:
    for i, row in enumerate(rows[:8]):
        cells = [str(c).strip() for c in row if c not in (None, "")]
        if len(cells) >= 3 and all(len(c) <= 48 for c in cells):
            return i
    return None


def _map_rows(kind: str, index: dict[str, int], data_rows: list[tuple]) -> list[dict[str, str]]:
    aliases = _COLUMNS[kind]
    if not any(name in index for name in aliases.get("name", aliases.get("email", ()))) and kind != "locations":
        if "code" not in aliases or not any(name in index for name in aliases["code"]):
            return []
    found = {field: next((name for name in names if name in index), None) for field, names in aliases.items()}
    if kind == "locations" and not (found.get("code") and found.get("name")):
        return []
    if kind == "employees" and not found.get("email"):
        return []
    if kind == "vendors" and not (found.get("name") and found.get("contact_email")):
        return []
    if kind == "stock" and not (found.get("sku_code") and found.get("name")):
        return []
    columns = TEMPLATES[kind]
    cleaned: list[dict[str, str]] = []
    for raw in data_rows:
        item = {col: "" for col in columns}
        for field, header in found.items():
            if header is None or field not in item:
                continue
            pos = index[header]
            if pos < len(raw) and raw[pos] not in (None, ""):
                item[field] = str(raw[pos]).strip()
        if not any(item.values()):
            continue
        if not _keep(kind, item):
            continue
        cleaned.append(item)
    return cleaned


def _keep(kind: str, item: dict[str, str]) -> bool:
    if kind == "locations":
        if not item.get("code") or not item.get("name"):
            return False
        item["code"] = item["code"].upper()
        item["type"] = _place_type(item.get("type") or "")
        if item.get("parent_code"):
            item["parent_code"] = item["parent_code"].upper()
        return True
    if kind == "employees":
        return bool(item.get("name")) and bool(_EMAIL.match((item.get("email") or "").lower()))
    if kind == "vendors":
        return bool(item.get("name")) and bool(_EMAIL.match((item.get("contact_email") or "").lower()))
    if kind == "departments":
        return bool(item.get("name"))
    if kind == "stock":
        return bool(item.get("sku_code") and item.get("name"))
    if kind == "resources":
        rtype = _resource_type(item.get("type") or "")
        if not item.get("name") or not rtype:
            return False
        item["type"] = rtype
        return True
    if kind == "cost_centres":
        return bool(item.get("code") and item.get("name"))
    if kind == "knowledge":
        return bool(item.get("title") and item.get("content"))
    if kind == "site_services":
        return bool(item.get("name"))
    return False


def _place_type(value: str) -> str:
    text = (value or "").strip().lower()
    for needle, kind in (
        ("headquarter", "BRANCH"),
        ("campus", "CAMPUS"),
        ("branch", "BRANCH"),
        ("office", "BRANCH"),
        ("city", "CITY"),
        ("region", "REGION"),
        ("building", "BUILDING"),
        ("floor", "FLOOR"),
        ("room", "ROOM"),
        ("zone", "ZONE"),
        ("country", "COUNTRY"),
        ("state", "STATE"),
        ("site", "SITE"),
    ):
        if needle in text:
            return kind
    upper = text.upper().replace(" ", "_").replace("-", "_")
    if upper in PLACE_TYPES:
        return upper
    return "BRANCH"


def _resource_type(value: str) -> Optional[str]:
    text = (value or "").strip().lower()
    if any(word in text for word in ("meet", "board", "conference", "collab", "huddle")):
        return "MEETING_ROOM"
    if "cabin" in text:
        return "CABIN"
    if "pantry" in text or "cafeteria" in text:
        return "PANTRY"
    if "park" in text:
        return "PARKING_SLOT"
    if "desk" in text:
        return "DESK"
    if "train" in text:
        return "TRAINING_ROOM"
    if "server" in text:
        return "SERVER_ROOM"
    if "locker" in text:
        return "LOCKER"
    if "first aid" in text or "medical" in text:
        return "FIRST_AID_STATION"
    return None
