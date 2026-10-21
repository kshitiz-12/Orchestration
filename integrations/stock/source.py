"""Stock stand-in. Its own sqlite file, not the desk database and not Darwinbox.

Quantity, reorder level, and expiry live here, per office. The desk copies them in with a sync.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "stock.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    sku_code TEXT NOT NULL,
    name TEXT NOT NULL,
    office_code TEXT NOT NULL,
    qty_on_hand REAL NOT NULL DEFAULT 0,
    reorder_min REAL NOT NULL DEFAULT 0,
    reorder_qty REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL DEFAULT 'each',
    expires_on TEXT,
    vendor_email TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (sku_code, office_code)
);
"""

SAMPLE_ITEMS = (
    ("TEA", "Tea bags", "WF", 20, 5, 40, "box", "2020-01-01", ""),
    ("STAPLER", "Stapler", "PUN", 12, 4, 24, "each", "", ""),
)


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_seeded(path: Path | None = None) -> Path:
    """Create the stock file and the sample items when the file is new."""
    db = path or DB_PATH
    fresh = not db.exists()
    conn = connect(db)
    try:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if fresh or count == 0:
            conn.executemany(
                """
                INSERT OR REPLACE INTO items
                    (sku_code, name, office_code, qty_on_hand, reorder_min, reorder_qty, unit, expires_on, vendor_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                SAMPLE_ITEMS,
            )
        conn.commit()
    finally:
        conn.close()
    return db


def list_items(path: Path | None = None) -> list[dict]:
    db = ensure_seeded(path)
    conn = connect(db)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM items ORDER BY office_code, sku_code")]
    finally:
        conn.close()
