from app.models.entities import Contact, FollowUp
from app.services.context import Services


def test_data_survives_restart(db_path):
    with Services.open(db_path) as first_run:
        c = first_run.crm.contacts.add(Contact(first_name="Νίκος", last_name="Οικονόμου"))
        first_run.planner.follow_ups.add(FollowUp(contact_id=c.id, due_at="2026-09-30T09:00"))

    with Services.open(db_path) as second_run:
        assert second_run.crm.contacts.get(c.id).last_name == "Οικονόμου"
        assert second_run.crm.timeline(c.id).follow_ups[0].due_at == "2026-09-30T09:00"


def test_each_write_is_committed_immediately(db_path):
    services = Services.open(db_path)
    services.crm.contacts.add(Contact(first_name="Άννα"))
    services.close()
    with Services.open(db_path) as reopened:
        assert reopened.crm.contacts.count() == 1
