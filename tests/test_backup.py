import pytest

from app.core.backup import BackupError, create_backup, restore_backup, verify_backup
from app.core.db import connect, schema_version
from app.crm.repository import ContactRepository


def test_backup_and_restore_to_clean_location(conn, tmp_path):
    ContactRepository(conn).create(first_name="Σοφία", last_name="Ιωάννου")
    backup = create_backup(conn, tmp_path / "backups")

    clean = tmp_path / "clean" / "restored.db"
    assert restore_backup(backup, clean) is None
    restored = connect(clean)
    assert [c["first_name"] for c in ContactRepository(restored).list()] == ["Σοφία"]
    assert schema_version(restored) == schema_version(conn)
    restored.close()


def test_restore_over_existing_database_keeps_safety_copy(conn, db_path, tmp_path):
    repo = ContactRepository(conn)
    repo.create(first_name="Άννα")
    backup = create_backup(conn, tmp_path / "backups")
    repo.create(first_name="Κώστας")
    conn.close()

    safety = restore_backup(backup, db_path, backup_dir=tmp_path / "backups")

    after = connect(db_path)
    assert [c["first_name"] for c in ContactRepository(after).list()] == ["Άννα"]
    after.close()
    pre_restore = connect(safety)
    assert sorted(c["first_name"] for c in ContactRepository(pre_restore).list()) == ["Άννα", "Κώστας"]
    pre_restore.close()


def test_restore_rejects_invalid_backup(tmp_path, db_path):
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database at all" * 100)
    with pytest.raises(BackupError):
        restore_backup(junk, db_path)
    with pytest.raises(BackupError):
        verify_backup(tmp_path / "missing.db")
    empty = tmp_path / "empty.db"
    connect(empty).close()
    with pytest.raises(BackupError):
        verify_backup(empty)
    assert not db_path.exists()
