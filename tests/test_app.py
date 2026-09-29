import ast
import threading
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pytest

from app import __main__ as cli
from app.services.context import Services
from app.services.sample_data import seed
from app.ui.server import ThreadingHTTPServer, make_handler

TODAY = date(2026, 9, 27)
UI_DIR = Path(__file__).resolve().parents[1] / "app" / "ui"


def test_ui_never_touches_the_database_directly():
    for path in UI_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert name != "sqlite3" and not name.startswith("app.database"), f"{path.name} imports {name}"


@pytest.fixture
def seeded(services):
    seed(services, TODAY)
    return services


def test_sample_data_is_fictional_and_complete(seeded):
    contacts = seeded.crm.contacts.list_all()
    assert len(contacts) == 30
    assert all(c.email.endswith("@example.com") and c.phone.startswith("69000") for c in contacts)
    assert seeded.crm.activities.count() and seeded.performance.goals.count() and seeded.performance.production.count()


def test_today_overview(seeded):
    o = seeded.planner.today(TODAY)
    assert len(o.appointments) == 2
    assert all(f.due_at < "2026-09-27" for f in o.overdue_follow_ups)
    assert all(f.due_at.startswith("2026-09-27") for f in o.due_today_follow_ups)
    assert all(c.status == "lead" for c in o.untouched_leads)


@pytest.fixture
def base_url(seeded, db_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db_path, lambda: TODAY))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def fetch(url):
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def test_ui_pages(base_url, seeded):
    assert "Today · 2026-09-27" in fetch(base_url + "/")
    contact = seeded.crm.contacts.list_all()[0]
    assert contact.last_name in fetch(base_url + "/contacts")
    assert "Timeline" in fetch(f"{base_url}/contacts/{contact.id}")
    results = fetch(base_url + "/contacts?q=" + urllib.request.quote("<script>"))
    assert "<script>" not in results and "0 result(s)" in results
    for missing in ["/contacts/99999", "/nope"]:
        with pytest.raises(urllib.error.HTTPError) as exc:
            fetch(base_url + missing)
        assert exc.value.code == 404


def test_cli_end_to_end(tmp_path, monkeypatch, capsys):
    db = tmp_path / "data" / "jarvis.db"
    monkeypatch.setenv("JARVIS_CONFIG", str(tmp_path / "none.toml"))
    monkeypatch.setenv("JARVIS_DB_PATH", str(db))
    monkeypatch.setenv("JARVIS_BACKUP_DIR", str(tmp_path / "backups"))

    assert cli.main(["init"]) == 0
    assert cli.main(["seed"]) == 0
    assert cli.main(["seed"]) == 1
    assert cli.main(["status"]) == 0
    assert "contacts" in capsys.readouterr().out
    assert cli.main(["backup"]) == 0
    backup = next((tmp_path / "backups").glob("*.db"))

    with Services.open(db) as services:
        before = services.crm.contacts.count()
        services.crm.contacts.delete(services.crm.untouched_leads()[0].id)

    assert cli.main(["restore", str(backup)]) == 0
    with Services.open(db) as services:
        assert services.crm.contacts.count() == before
    assert cli.main(["restore", str(tmp_path / "missing.db")]) == 1
