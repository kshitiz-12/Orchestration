"""Bring an existing database up to the current models without losing anything.

Only adds: missing tables, missing columns (nullable, with the model's simple default for existing rows) and missing
plain indexes. Never drops or alters. Unique indexes are only created with new tables, because adding one to a table
that already holds duplicates would fail.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

from app.core.logging import get_logger

logger = get_logger(__name__)

# Rows written by older code before the provider_* columns existed.
_BACKFILLS = {
    "raw_email_events": """
        UPDATE raw_email_events
        SET provider = COALESCE(provider, source, 'OUTLOOK'),
            provider_message_id = COALESCE(provider_message_id, gmail_message_id),
            provider_conversation_id = COALESCE(provider_conversation_id, gmail_thread_id)
        WHERE provider_message_id IS NULL OR provider IS NULL
    """,
    "communications": """
        UPDATE communications
        SET provider_message_id = gmail_message_id
        WHERE provider_message_id IS NULL AND gmail_message_id IS NOT NULL
    """,
}


@dataclass
class SyncPlan:
    tables: list[str] = field(default_factory=list)
    columns: list[tuple[str, sa.Column]] = field(default_factory=list)
    indexes: list[sa.Index] = field(default_factory=list)
    skipped_unique: list[str] = field(default_factory=list)
    # Postgres tables still readable through Supabase's public REST API (row-level security off)
    exposed: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.tables or self.columns or self.indexes or self.exposed)

    def describe(self) -> list[str]:
        out = [f"create table {t}" for t in self.tables]
        out += [f"add column {t}.{c.name}" for t, c in self.columns]
        out += [f"create index {i.name} on {i.table.name}" for i in self.indexes]
        out += [f"enable row level security on {t}" for t in self.exposed]
        out += [f"skipped unique index {n} (existing table - add by hand after checking for duplicates)"
                for n in self.skipped_unique]
        return out


def _metadata() -> sa.MetaData:
    from app import models  # noqa: F401

    return SQLModel.metadata


def plan(conn: Connection) -> SyncPlan:
    meta = _metadata()
    inspector = sa.inspect(conn)
    existing = set(inspector.get_table_names())
    result = SyncPlan()
    for table in meta.sorted_tables:
        if table.name not in existing:
            result.tables.append(table.name)
            continue
        have_cols = {c["name"] for c in inspector.get_columns(table.name)}
        result.columns += [(table.name, c) for c in table.columns if c.name not in have_cols]
        have_idx = {i["name"] for i in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in have_idx:
                continue
            if index.unique:
                result.skipped_unique.append(index.name)
            else:
                result.indexes.append(index)
    result.exposed = exposed_tables(conn)
    return result


def exposed_tables(conn: Connection) -> list[str]:
    """Our public-schema tables with row-level security off.

    Supabase serves every public table over its REST API to anyone holding the project's anon key; with RLS on and
    no policies that API sees nothing. The backend connects as the table owner, which RLS does not apply to.
    """
    if conn.dialect.name != "postgresql":
        return []
    rows = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname = 'public' AND tableowner = current_user AND NOT rowsecurity ORDER BY tablename"
    )).all()
    return [r[0] for r in rows]


def lock_down(conn: Connection) -> list[str]:
    tables = exposed_tables(conn)
    for table in tables:
        conn.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
    return tables


def _default_sql(column: sa.Column, dialect: sa.engine.Dialect) -> str | None:
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return None
    value = default.arg
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def _add_column(conn: Connection, table: str, column: sa.Column) -> None:
    dialect = conn.dialect
    col_type = column.type.compile(dialect=dialect)
    sql = f'ALTER TABLE "{table}" ADD COLUMN "{column.name}" {col_type}'
    default = _default_sql(column, dialect)
    if default is not None:
        sql += f" DEFAULT {default}"
    conn.execute(sa.text(sql))


def apply(conn: Connection) -> SyncPlan:
    todo = plan(conn)
    meta = _metadata()
    if todo.tables:
        meta.create_all(bind=conn, tables=[meta.tables[t] for t in todo.tables], checkfirst=True)
    for table, column in todo.columns:
        _add_column(conn, table, column)
    for index in todo.indexes:
        index.create(bind=conn, checkfirst=True)
    have = set(sa.inspect(conn).get_table_names())
    for table, sql in _BACKFILLS.items():
        if table in have:
            conn.execute(sa.text(sql))
    lock_down(conn)
    for line in todo.describe():
        logger.info("schema_sync", change=line)
    return todo
