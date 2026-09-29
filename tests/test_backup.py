import pytest

from app.core.errors import BackupError
from app.database.backup import create_backup, restore_backup, verify_backup
from app.database.connection import connect, schema_version
from app.models.entities import Contact
from app.services.context import Services


def test_backup_and_restore_to_clean_location(services, conn, tmp_path):
    services.crm.contacts.add(Contact(first_name="Σοφία", last_name="Ιωάννου"))
    backup = create_backup(conn, tmp_path / "backups")

    clean = tmp_path / "clean" / "restored.db"
    assert restore_backup(backup, clean) is None
    with Services.open(clean) as restored:
        assert [c.first_name for c in restored.crm.contacts.list_all()] == ["Σοφία"]
    check = connect(clean)
    assert schema_version(check) == schema_version(conn)
    check.close()


def test_restore_over_existing_database_keeps_safety_copy(services, conn, db_path, tmp_path):
    services.crm.contacts.add(Contact(first_name="Άννα"))
    backup = create_backup(conn, tmp_path / "backups")
    services.crm.contacts.add(Contact(first_name="Κώστας"))
    conn.close()

    safety = restore_backup(backup, db_path, backup_dir=tmp_path / "backups")

    with Services.open(db_path) as after:
        assert [c.first_name for c in after.crm.contacts.list_all()] == ["Άννα"]
    with Services.open(safety) as before:
        assert sorted(c.first_name for c in before.crm.contacts.list_all()) == ["Άννα", "Κώστας"]


def test_restore_rejects_invalid_backups(tmp_path, db_path):
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
