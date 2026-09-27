import sqlite3

import pytest

from app.core import db
from app.core.db import available_migrations, connect, fold, migrate, schema_version


def test_migrate_creates_schema_and_is_idempotent(db_path):
    conn = connect(db_path)
    applied = migrate(conn)
    latest = available_migrations()[-1][0]
    assert applied == [v for v, _ in available_migrations()]
    assert schema_version(conn) == latest
    assert migrate(conn) == []
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"contacts", "activities", "follow_ups", "appointments", "goals", "production"} <= tables


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO activities (contact_id, type, timestamp, created_at, updated_at) "
            "VALUES (999, 'call', '2026-01-01T10:00', 'x', 'x')"
        )


def test_failed_migration_rolls_back(tmp_path, monkeypatch, db_path):
    conn = connect(db_path)
    migrate(conn)
    version = schema_version(conn)
    bad = tmp_path / "migrations"
    bad.mkdir()
    for v, p in available_migrations():
        (bad / p.name).write_text(p.read_text("utf-8"), "utf-8")
    (bad / f"{version + 1:04d}_broken.sql").write_text(
        "CREATE TABLE half_done (id INTEGER);\nTHIS IS NOT SQL;", "utf-8"
    )
    monkeypatch.setattr(db, "MIGRATIONS_DIR", bad)
    backups = tmp_path / "backups"

    with pytest.raises(sqlite3.OperationalError):
        migrate(conn, backup_dir=backups)

    assert schema_version(conn) == version
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'half_done'").fetchone() is None
    assert len(list(backups.glob("*pre-migration*.db"))) == 1


def test_fold_ignores_greek_accents_and_case():
    assert fold("Γιώργος ΠΑΠΑΔΌΠΟΥΛΟΣ") == fold("γιωργος παπαδοπουλος")
