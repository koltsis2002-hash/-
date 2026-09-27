import pytest

from app.core.db import connect, migrate


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "database" / "jarvis.db"


@pytest.fixture
def conn(db_path):
    conn = connect(db_path)
    migrate(conn)
    yield conn
    conn.close()
