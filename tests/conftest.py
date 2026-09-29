import pytest

from app.core.config import Settings
from app.database.connection import connect, migrate
from app.models.entities import Contact
from app.services.context import Services


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "jarvis.db"


@pytest.fixture
def settings(tmp_path, db_path):
    return Settings(db_path=db_path, backup_dir=tmp_path / "backups", host="127.0.0.1", port=0)


@pytest.fixture
def conn(db_path):
    conn = connect(db_path)
    migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def services(conn):
    return Services(conn)


@pytest.fixture
def contact(services):
    return services.crm.contacts.add(Contact(first_name="Γιώργος", last_name="Παπαδόπουλος", phone="6900000001"))
