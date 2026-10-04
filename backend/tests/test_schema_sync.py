"""The database catches up with the models, from empty or from an old schema, without losing data."""

import sqlalchemy as sa
from sqlmodel import SQLModel

from app.core.schema_sync import apply, plan


def _engine(tmp_path, name="db.sqlite"):
    return sa.create_engine(f"sqlite:///{tmp_path / name}")


def _models():
    from app import models  # noqa: F401

    return SQLModel.metadata


def test_empty_database_gets_every_table(tmp_path):
    eng = _engine(tmp_path)
    with eng.begin() as conn:
        apply(conn)
    with eng.connect() as conn:
        assert plan(conn).empty
        assert set(_models().tables) <= set(sa.inspect(conn).get_table_names())


def test_old_database_gets_new_tables_and_columns_and_keeps_rows(tmp_path):
    eng = _engine(tmp_path)
    meta = _models()
    with eng.begin() as conn:
        meta.create_all(conn)
        # Make it look like a database from before departments had branches and places had codes.
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_departments_location_id"))
        conn.execute(sa.text("ALTER TABLE departments DROP COLUMN location_id"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_locations_code"))
        conn.execute(sa.text("ALTER TABLE locations DROP COLUMN code"))
        conn.execute(sa.text("DROP TABLE learning_records"))
        conn.execute(sa.text(
            "INSERT INTO tenants (tenant_id, name, region, status, created_at, updated_at) "
            "VALUES ('t1', 'Acme', 'IN', 'ACTIVE', '2026-01-01', '2026-01-01')"
        ))
        conn.execute(sa.text(
            "INSERT INTO departments (department_id, tenant_id, code, name, categories, backup_emails, sla_hours, "
            "spend_approval_limit, is_active, created_at, updated_at) "
            "VALUES ('d1', 't1', 'FACILITIES', 'Facilities', '[]', '[]', 8, 0, 1, '2026-01-01', '2026-01-01')"
        ))

    with eng.connect() as conn:
        todo = plan(conn)
        described = todo.describe()
        assert "create table learning_records" in described
        assert "add column departments.location_id" in described
        assert "add column locations.code" in described

    with eng.begin() as conn:
        apply(conn)
    with eng.begin() as conn:
        assert plan(conn).empty, plan(conn).describe()
        assert apply(conn).empty, "running it again changes nothing"
        row = conn.execute(sa.text("SELECT code, location_id, sla_hours FROM departments")).one()
        assert row == ("FACILITIES", None, 8)
        idx = {i["name"] for i in sa.inspect(conn).get_indexes("departments")}
        assert "ix_departments_location_id" in idx


def test_new_column_with_a_simple_default_fills_existing_rows(tmp_path):
    eng = _engine(tmp_path)
    with eng.begin() as conn:
        _models().create_all(conn)
        conn.execute(sa.text(
            "INSERT INTO tenants (tenant_id, name, region, status, created_at, updated_at) "
            "VALUES ('t1', 'Acme', 'IN', 'ACTIVE', '2026-01-01', '2026-01-01')"
        ))
        conn.execute(sa.text(
            "INSERT INTO departments (department_id, tenant_id, code, name, categories, backup_emails, sla_hours, "
            "spend_approval_limit, is_active, created_at, updated_at) "
            "VALUES ('d1', 't1', 'IT', 'IT', '[]', '[]', 8, 0, 1, '2026-01-01', '2026-01-01')"
        ))
        conn.execute(sa.text("ALTER TABLE departments DROP COLUMN is_active"))
    with eng.begin() as conn:
        apply(conn)
        assert conn.execute(sa.text("SELECT is_active FROM departments")).scalar() in (1, True)


def test_alembic_upgrade_builds_a_fresh_database(tmp_path, monkeypatch):
    from alembic import command

    from app.core.config import get_settings
    from app.core.database import alembic_config

    url = f"sqlite:///{(tmp_path / 'migrated.sqlite').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        command.upgrade(alembic_config(), "head")
        eng = sa.create_engine(url)
        with eng.connect() as conn:
            assert plan(conn).empty, plan(conn).describe()
            version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
        assert version == "0006_lock_down_api_access"
        command.upgrade(alembic_config(), "head")
    finally:
        monkeypatch.setenv("DATABASE_URL", "sqlite://")
        get_settings.cache_clear()
