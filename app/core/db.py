import sqlite3
import unicodedata
from pathlib import Path

from app.core.backup import create_backup

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def fold(text):
    # Accent- and case-insensitive matching for Greek: "Γιώργο" must match "γιωργος".
    if text is None:
        return None
    decomposed = unicodedata.normalize("NFD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def connect(db_path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("jarvis_fold", 1, fold, deterministic=True)
    return conn


def schema_version(conn) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def available_migrations() -> list[tuple[int, Path]]:
    return sorted((int(p.name.split("_", 1)[0]), p) for p in MIGRATIONS_DIR.glob("*.sql"))


def migrate(conn, backup_dir=None) -> list[int]:
    current = schema_version(conn)
    pending = [(v, p) for v, p in available_migrations() if v > current]
    if pending and current > 0 and backup_dir is not None:
        create_backup(conn, backup_dir, label=f"pre-migration-v{current}")
    for version, path in pending:
        sql = path.read_text("utf-8")
        try:
            conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
    return [v for v, _ in pending]


def open_database(settings) -> sqlite3.Connection:
    conn = connect(settings.db_path)
    migrate(conn, backup_dir=settings.backup_dir)
    return conn
