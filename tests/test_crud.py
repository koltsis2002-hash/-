import pytest

from app.core.errors import NotFoundError, ValidationError
from app.models.entities import Activity, Appointment, Contact, FollowUp, Goal, Production


def test_contact_crud(services):
    repo = services.crm.contacts
    c = repo.add(Contact(first_name="Μαρία", last_name="Νικολάου", email="maria@example.com", company="Φαρμακείο"))
    assert c.id and c.status == "lead" and c.client_flag is False and c.created_at == c.updated_at

    updated = repo.update(c.id, status="client", client_flag=True, phone="6900000002")
    assert (updated.status, updated.client_flag, updated.phone) == ("client", True, "6900000002")
    assert repo.list_all() == [updated]

    repo.delete(c.id)
    assert repo.get(c.id) is None
    with pytest.raises(NotFoundError):
        repo.delete(c.id)
    with pytest.raises(NotFoundError):
        repo.update(c.id, status="lead")


def test_activity_crud(services, contact):
    repo = services.crm.activities
    a = repo.add(Activity(contact_id=contact.id, activity_type="call", timestamp="2026-09-01T10:00",
                          outcome="reached", product="Life", next_action="Send offer", followup_date="2026-09-05"))
    assert repo.get(a.id).next_action == "Send offer"
    assert repo.update(a.id, outcome="not_reached").outcome == "not_reached"
    repo.delete(a.id)
    assert repo.count() == 0


def test_follow_up_crud_and_completion(services, contact):
    planner = services.planner
    f = planner.follow_ups.add(FollowUp(contact_id=contact.id, due_at="2026-09-20T10:00", priority="high",
                                        reason="Call back"))
    assert f.status == "open" and f.completed_at is None
    done = planner.complete_follow_up(f.id)
    assert done.status == "done" and done.completed_at
    planner.follow_ups.delete(f.id)
    assert planner.follow_ups.get(f.id) is None


def test_appointment_crud(services, contact):
    repo = services.planner.appointments
    a = repo.add(Appointment(contact_id=contact.id, start_at="2026-09-27T10:00", end_at="2026-09-27T11:00",
                             location="Office", purpose="Review"))
    assert repo.update(a.id, status="completed", notes="Went well").status == "completed"
    repo.delete(a.id)
    assert repo.list_all() == []


def test_goal_crud(services):
    repo = services.performance.goals
    g = repo.add(Goal(metric="calls", period_type="month", period_start="2026-09-01",
                      period_end="2026-09-30", target_value=200))
    assert services.performance.active_goals("2026-09-15") == [g]
    assert services.performance.active_goals("2026-10-01") == []
    assert repo.update(g.id, target_value=250).target_value == 250
    repo.delete(g.id)
    assert repo.count() == 0


def test_production_crud(services, contact):
    repo = services.performance.production
    p = repo.add(Production(contact_id=contact.id, product="Life", date="2026-09-10", value=1200))
    assert p.status == "pending"
    assert repo.update(p.id, status="issued").status == "issued"
    repo.delete(p.id)
    assert repo.count() == 0


@pytest.mark.parametrize("bad", [
    Contact(first_name="  "),
    Contact(first_name="A", status="vip"),
])
def test_invalid_contacts_rejected(services, bad):
    with pytest.raises(ValidationError):
        services.crm.contacts.add(bad)


def test_invalid_values_rejected(services, contact):
    with pytest.raises(ValidationError):
        services.crm.activities.add(Activity(contact_id=contact.id, activity_type="fax", timestamp="2026-09-01"))
    with pytest.raises(ValidationError):
        services.planner.appointments.add(Appointment(start_at="2026-09-27T10:00", end_at="2026-09-27T09:00"))
    with pytest.raises(ValidationError):
        services.performance.goals.add(Goal(metric="happiness", period_type="month", period_start="2026-10-01",
                                            period_end="2026-10-31", target_value=1))
    with pytest.raises(ValidationError):
        services.performance.production.add(Production(contact_id=contact.id, product="Life", date="2026-09-10",
                                                        value=-5))
    with pytest.raises(ValidationError):
        services.crm.contacts.update(contact.id, medical_history="x")


def test_duplicate_goal_rejected(services):
    goal = Goal(metric="calls", period_type="month", period_start="2026-09-01", period_end="2026-09-30",
                target_value=1)
    services.performance.goals.add(goal)
    with pytest.raises(ValidationError):
        services.performance.goals.add(goal)


def test_contact_search_is_accent_and_case_insensitive(services, contact):
    services.crm.contacts.add(Contact(first_name="Ελένη", last_name="Γεωργίου"))
    assert [c.id for c in services.crm.search("γιωργο παπαδοπ")] == [contact.id]
    assert [c.id for c in services.crm.search("6900000001")] == [contact.id]
    assert services.crm.search("100%") == []
    assert len(services.crm.search("  ")) == 2
