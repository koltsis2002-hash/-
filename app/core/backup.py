import sqlite3
from datetime import datetime
from pathlib import Path


class BackupError(Exception):
    pass


def create_backup(conn, backup_dir, label="manual") -> Path:
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = backup_dir / f"jarvis-{stamp}-{label}.db"
    dest = sqlite3.connect(target)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    verify_backup(target)
    return target


def verify_backup(path) -> None:
    path = Path(path)
    if not path.is_file():
        raise BackupError(f"Backup file not found: {path}")
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"Not a valid JARVIS database: {path}") from exc
    if result != "ok":
        raise BackupError(f"Integrity check failed for {path}: {result}")
    if version < 1:
        raise BackupError(f"Backup has no JARVIS schema: {path}")


def restore_backup(backup_path, db_path, backup_dir=None) -> Path | None:
    """Replace db_path with backup_path. Returns the safety backup of the replaced database, if any."""
    verify_backup(backup_path)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    safety_copy = None
    if db_path.exists() and backup_dir is not None:
        current = sqlite3.connect(db_path)
        try:
            safety_copy = create_backup(current, backup_dir, label="pre-restore")
        finally:
            current.close()

    src = sqlite3.connect(f"{Path(backup_path).resolve().as_uri()}?mode=ro", uri=True)
    dest = sqlite3.connect(db_path)
    try:
        src.backup(dest)
    finally:
        src.close()
        dest.close()
    return safety_copy
