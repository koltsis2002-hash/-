import sqlite3
from dataclasses import fields

import pytest

from app.database import connection
from app.database.connection import available_migrations, connect, fold, migrate, schema_version
from app.database.repositories import (
    ActivityRepository, AppointmentRepository, ContactRepository, FollowUpRepository, GoalRepository,
    ProductionRepository,
)

REPOSITORIES = [ContactRepository, ActivityRepository, FollowUpRepository, AppointmentRepository,
                GoalRepository, ProductionRepository]


def test_new_database_gets_full_schema(db_path):
    assert not db_path.exists()
    conn = connect(db_path)
    assert migrate(conn) == [v for v, _ in available_migrations()]
    assert db_path.exists()
    assert schema_version(conn) == available_migrations()[-1][0]
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"contacts", "activities", "follow_ups", "appointments", "goals", "production"} <= tables
    conn.close()


def test_migrate_is_idempotent(conn):
    assert migrate(conn) == []


@pytest.mark.parametrize("repo_cls", REPOSITORIES)
def test_models_match_table_columns(conn, repo_cls):
    table_columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({repo_cls.table})")}
    assert {f.name for f in fields(repo_cls.model)} == table_columns


def test_failed_migration_rolls_back_and_keeps_backup(tmp_path, monkeypatch, conn):
    version = schema_version(conn)
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for _, p in available_migrations():
        (migrations / p.name).write_text(p.read_text("utf-8"), "utf-8")
    (migrations / f"{version + 1:04d}_broken.sql").write_text("CREATE TABLE half_done (id INTEGER);\nNOT SQL;", "utf-8")
    monkeypatch.setattr(connection, "MIGRATIONS_DIR", migrations)
    backups = tmp_path / "backups"

    with pytest.raises(sqlite3.OperationalError):
        migrate(conn, backup_dir=backups)

    assert schema_version(conn) == version
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'half_done'").fetchone() is None
    assert len(list(backups.glob("*pre-migration*.db"))) == 1


def test_fold_ignores_greek_accents_and_case():
    assert fold("Γιώργος ΠΑΠΑΔΌΠΟΥΛΟΣ") == fold("γιωργος παπαδοπουλος")
