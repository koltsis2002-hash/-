import threading
import urllib.error
import urllib.request
from datetime import date

import pytest

from app import __main__ as cli
from app.core.db import connect
from app.core.sample_data import seed
from app.crm.repository import ContactRepository
from app.planner.overview import today_overview
from app.ui.server import ThreadingHTTPServer, make_handler

TODAY = date(2026, 9, 27)


@pytest.fixture
def seeded(conn):
    seed(conn, TODAY)
    return conn


def test_sample_data_is_fictional_and_complete(seeded):
    counts = {t: seeded.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ["contacts", "activities", "follow_ups", "appointments", "goals", "production"]}
    assert all(counts.values()), counts
    for c in ContactRepository(seeded).list():
        assert c["email"].endswith("@example.com") and c["phone"].startswith("69000")


def test_today_overview(seeded):
    o = today_overview(seeded, TODAY)
    assert len(o["appointments"]) == 2
    assert all(f["due_at"] < "2026-09-27" for f in o["overdue_follow_ups"])
    assert all(f["due_at"].startswith("2026-09-27") for f in o["due_today_follow_ups"])
    assert all(c["status"] == "lead" for c in o["untouched_leads"])


@pytest.fixture
def base_url(seeded, db_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db_path, lambda: TODAY))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def fetch(url):
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def test_ui_pages(base_url, seeded):
    assert "Today · 2026-09-27" in fetch(base_url + "/")
    contact = ContactRepository(seeded).list()[0]
    assert contact["last_name"] in fetch(base_url + "/contacts")
    assert "Timeline" in fetch(f"{base_url}/contacts/{contact['id']}")
    results = fetch(base_url + "/contacts?q=" + urllib.request.quote("<script>"))
    assert "<script>" not in results and "0 result(s)" in results
    for missing in ["/contacts/99999", "/nope"]:
        with pytest.raises(urllib.error.HTTPError) as exc:
            fetch(base_url + missing)
        assert exc.value.code == 404


def test_cli_init_seed_backup_restore(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JARVIS_CONFIG", str(tmp_path / "none.toml"))
    assert cli.main(["init"]) == 0
    assert cli.main(["seed"]) == 0
    assert cli.main(["seed"]) == 1
    assert cli.main(["backup"]) == 0
    backup = next((tmp_path / "backups").glob("*.db"))

    conn = connect(tmp_path / "database" / "jarvis.db")
    before = ContactRepository(conn).count()
    ContactRepository(conn).create(first_name="Extra")
    conn.close()

    assert cli.main(["restore", str(backup)]) == 0
    conn = connect(tmp_path / "database" / "jarvis.db")
    assert ContactRepository(conn).count() == before
    conn.close()
    assert cli.main(["restore", str(tmp_path / "missing.db")]) == 1
