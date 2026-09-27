import sqlite3

import pytest

from app.analytics.repository import GoalRepository, ProductionRepository
from app.core.db import connect, migrate
from app.core.repository import NotFoundError
from app.crm.repository import ActivityRepository, ContactRepository
from app.planner.repository import AppointmentRepository, FollowUpRepository


@pytest.fixture
def contact(conn):
    return ContactRepository(conn).create(first_name="Γιώργος", last_name="Παπαδόπουλος", phone="6900000001")


def test_contact_crud(conn):
    repo = ContactRepository(conn)
    c = repo.create(first_name="Μαρία", last_name="Νικολάου", email="maria@example.com")
    assert c["status"] == "lead" and c["created_at"] == c["updated_at"]

    updated = repo.update(c["id"], status="prospect", phone="6900000002")
    assert updated["status"] == "prospect" and updated["phone"] == "6900000002"
    assert repo.list() == [updated]

    repo.delete(c["id"])
    assert repo.get(c["id"]) is None
    with pytest.raises(NotFoundError):
        repo.delete(c["id"])
    with pytest.raises(NotFoundError):
        repo.update(c["id"], status="client")


def test_rejects_unknown_fields_and_invalid_values(conn):
    repo = ContactRepository(conn)
    with pytest.raises(ValueError):
        repo.create(first_name="A", medical_history="x")
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(first_name="A", status="vip")
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(first_name="  ")


def test_contact_search_is_accent_and_case_insensitive(conn, contact):
    repo = ContactRepository(conn)
    repo.create(first_name="Ελένη", last_name="Γεωργίου")
    assert [c["id"] for c in repo.search("γιωργο παπαδοπ")] == [contact["id"]]
    assert [c["id"] for c in repo.search("6900000001")] == [contact["id"]]
    assert repo.search("100%") == []
    assert len(repo.search("  ")) == 2


def test_untouched_leads(conn, contact):
    repo = ContactRepository(conn)
    assert [c["id"] for c in repo.untouched_leads()] == [contact["id"]]
    ActivityRepository(conn).create(contact_id=contact["id"], type="call", timestamp="2026-09-01T10:00")
    assert repo.untouched_leads() == []


def test_activity_timeline_and_cascade(conn, contact):
    repo = ActivityRepository(conn)
    first = repo.create(contact_id=contact["id"], type="call", timestamp="2026-09-01T10:00", outcome="not_reached")
    second = repo.create(contact_id=contact["id"], type="call", timestamp="2026-09-02T10:00", outcome="reached")
    assert [a["id"] for a in repo.for_contact(contact["id"])] == [second["id"], first["id"]]
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(contact_id=contact["id"], type="fax", timestamp="2026-09-02T10:00")

    ContactRepository(conn).delete(contact["id"])
    assert repo.count() == 0


def test_follow_ups(conn, contact):
    repo = FollowUpRepository(conn)
    overdue = repo.create(contact_id=contact["id"], due_at="2026-09-20T10:00", priority="high")
    later = repo.create(contact_id=contact["id"], due_at="2026-10-05T10:00")
    assert [f["id"] for f in repo.open_due_before("2026-09-28")] == [overdue["id"]]

    done = repo.complete(overdue["id"])
    assert done["status"] == "done" and done["completed_at"]
    assert repo.open_due_before("2026-09-28") == []
    assert [f["id"] for f in repo.for_contact(contact["id"])] == [overdue["id"], later["id"]]


def test_appointments(conn, contact):
    repo = AppointmentRepository(conn)
    a = repo.create(contact_id=contact["id"], start_at="2026-09-27T10:00", end_at="2026-09-27T11:00")
    repo.create(start_at="2026-09-28T10:00", purpose="Internal")
    assert [x["id"] for x in repo.starting_between("2026-09-27", "2026-09-28")] == [a["id"]]
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(start_at="2026-09-27T10:00", end_at="2026-09-27T09:00")

    ContactRepository(conn).delete(contact["id"])
    assert repo.get(a["id"])["contact_id"] is None


def test_goals(conn):
    repo = GoalRepository(conn)
    g = repo.create(metric="calls", period_type="month", period_start="2026-09-01",
                    period_end="2026-09-30", target_value=200)
    assert repo.covering("2026-09-15") == [g]
    assert repo.covering("2026-10-01") == []
    assert repo.update(g["id"], target_value=250)["target_value"] == 250
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(metric="calls", period_type="month", period_start="2026-09-01",
                    period_end="2026-09-30", target_value=1)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(metric="happiness", period_type="month", period_start="2026-10-01",
                    period_end="2026-10-31", target_value=1)


def test_production_blocks_contact_deletion(conn, contact):
    repo = ProductionRepository(conn)
    p = repo.create(contact_id=contact["id"], product="Life", date="2026-09-10", value=1200)
    assert repo.for_contact(contact["id"]) == [p]
    with pytest.raises(sqlite3.IntegrityError):
        ContactRepository(conn).delete(contact["id"])
    with pytest.raises(sqlite3.IntegrityError):
        repo.create(contact_id=contact["id"], product="Life", date="2026-09-10", value=-5)


def test_data_persists_after_restart(db_path):
    conn = connect(db_path)
    migrate(conn)
    c = ContactRepository(conn).create(first_name="Νίκος", last_name="Οικονόμου")
    FollowUpRepository(conn).create(contact_id=c["id"], due_at="2026-09-30T09:00")
    conn.close()

    reopened = connect(db_path)
    assert migrate(reopened) == []
    assert ContactRepository(reopened).get(c["id"])["last_name"] == "Οικονόμου"
    assert FollowUpRepository(reopened).for_contact(c["id"])[0]["due_at"] == "2026-09-30T09:00"
    reopened.close()
