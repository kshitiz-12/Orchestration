"""Darwinbox stand-in. Its own sqlite file, not the desk database.

People and offices live here. The desk copies them in with a sync.
This is the shape of an HR pull, not a copy of Darwinbox itself.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "darwinbox.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS offices (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employees (
    employee_code TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department TEXT,
    role TEXT NOT NULL DEFAULT 'EMPLOYEE',
    manager_email TEXT,
    office_code TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# A few rows so a sync has something to pull. Offices are codes the desk already uses.
SAMPLE_OFFICES = (
    ("WF", "Whitefield"),
    ("PUN", "Pune Hq"),
)
SAMPLE_EMPLOYEES = (
    ("E001", "priya.nair@example.com", "Priya Nair", "Engineering", "BRANCH_ADMIN", "", "WF", 1),
    ("E002", "riya.shah@example.com", "Riya Shah", "Engineering", "EMPLOYEE", "priya.nair@example.com", "WF", 1),
    ("E003", "arun.left@example.com", "Arun Left", "Engineering", "EMPLOYEE", "priya.nair@example.com", "WF", 0),
)


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_seeded(path: Path | None = None) -> Path:
    """Create the Darwinbox file and the sample people when the file is new."""
    db = path or DB_PATH
    fresh = not db.exists()
    conn = connect(db)
    try:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        if fresh or count == 0:
            conn.executemany("INSERT OR REPLACE INTO offices (code, name) VALUES (?, ?)", SAMPLE_OFFICES)
            conn.executemany(
                """
                INSERT OR REPLACE INTO employees
                    (employee_code, email, name, department, role, manager_email, office_code, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                SAMPLE_EMPLOYEES,
            )
        conn.commit()
    finally:
        conn.close()
    return db


def list_employees(path: Path | None = None) -> list[dict]:
    """Rows the desk can import. Managers come before the people who report to them."""
    db = ensure_seeded(path)
    conn = connect(db)
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM employees ORDER BY employee_code")]
    finally:
        conn.close()
    managers = {(r.get("manager_email") or "").lower() for r in rows}
    rows.sort(key=lambda r: (0 if (r.get("email") or "").lower() in managers else 1, r.get("employee_code") or ""))
    return rows
