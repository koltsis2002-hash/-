import pytest

from app.core.errors import NotFoundError, ValidationError
from app.models.entities import Activity, Appointment, FollowUp, Production


def test_child_records_require_existing_contact(services):
    with pytest.raises(ValidationError):
        services.crm.activities.add(Activity(contact_id=999, activity_type="call", timestamp="2026-09-01T10:00"))
    with pytest.raises(ValidationError):
        services.planner.follow_ups.add(FollowUp(contact_id=999, due_at="2026-09-01T10:00"))
    with pytest.raises(ValidationError):
        services.performance.production.add(Production(contact_id=999, product="Life", date="2026-09-01", value=1))


def test_timeline_collects_everything_for_a_contact(services, contact):
    first = services.crm.activities.add(Activity(contact_id=contact.id, activity_type="call",
                                                 timestamp="2026-09-01T10:00"))
    second = services.crm.activities.add(Activity(contact_id=contact.id, activity_type="meeting",
                                                  timestamp="2026-09-02T10:00"))
    services.planner.follow_ups.add(FollowUp(contact_id=contact.id, due_at="2026-09-05T10:00"))
    services.planner.appointments.add(Appointment(contact_id=contact.id, start_at="2026-09-06T10:00"))
    services.performance.production.add(Production(contact_id=contact.id, product="Life", date="2026-09-07", value=1))

    t = services.crm.timeline(contact.id)
    assert [a.id for a in t.activities] == [second.id, first.id]
    assert (len(t.follow_ups), len(t.appointments), len(t.production)) == (1, 1, 1)
    with pytest.raises(NotFoundError):
        services.crm.timeline(999)


def test_deleting_contact_cascades_history_and_unlinks_appointments(services, contact):
    services.crm.activities.add(Activity(contact_id=contact.id, activity_type="call", timestamp="2026-09-01T10:00"))
    services.planner.follow_ups.add(FollowUp(contact_id=contact.id, due_at="2026-09-05T10:00"))
    appointment = services.planner.appointments.add(Appointment(contact_id=contact.id, start_at="2026-09-06T10:00"))

    services.crm.contacts.delete(contact.id)

    assert services.crm.activities.count() == 0
    assert services.planner.follow_ups.count() == 0
    assert services.planner.appointments.get(appointment.id).contact_id is None


def test_contact_with_production_cannot_be_deleted(services, contact):
    services.performance.production.add(Production(contact_id=contact.id, product="Life", date="2026-09-07", value=1))
    with pytest.raises(ValidationError):
        services.crm.contacts.delete(contact.id)
    assert services.crm.contacts.get(contact.id) is not None


def test_untouched_leads(services, contact):
    assert [c.id for c in services.crm.untouched_leads()] == [contact.id]
    services.crm.activities.add(Activity(contact_id=contact.id, activity_type="call", timestamp="2026-09-01T10:00"))
    assert services.crm.untouched_leads() == []
