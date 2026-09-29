from datetime import date
from pathlib import Path

from app.database import backup
from app.database.connection import open_database, schema_version, table_counts
from app.services.context import Services
from app.services.sample_data import seed


def init_database(settings) -> int:
    conn = open_database(settings.db_path, settings.backup_dir)
    try:
        return schema_version(conn)
    finally:
        conn.close()


def create_backup(settings) -> Path:
    conn = open_database(settings.db_path, settings.backup_dir)
    try:
        return backup.create_backup(conn, settings.backup_dir)
    finally:
        conn.close()


def restore_backup(settings, backup_file) -> Path | None:
    return backup.restore_backup(backup_file, settings.db_path, backup_dir=settings.backup_dir)


def load_sample_data(settings, today: date, force=False) -> dict | None:
    """Returns row counts, or None when contacts already exist and force is False."""
    with Services.open(settings.db_path, settings.backup_dir) as services:
        if services.crm.contacts.count() and not force:
            return None
        return seed(services, today)


def database_summary(settings) -> tuple[int, dict[str, int]]:
    conn = open_database(settings.db_path, settings.backup_dir)
    try:
        return schema_version(conn), table_counts(conn)
    finally:
        conn.close()
