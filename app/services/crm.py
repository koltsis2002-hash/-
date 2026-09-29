from dataclasses import dataclass

from app.core.errors import NotFoundError
from app.database.repositories import (
    ActivityRepository, AppointmentRepository, ContactRepository, FollowUpRepository, ProductionRepository,
)
from app.models.entities import Activity, Appointment, Contact, FollowUp, Production


@dataclass
class ContactTimeline:
    contact: Contact
    activities: list[Activity]
    follow_ups: list[FollowUp]
    appointments: list[Appointment]
    production: list[Production]


class CrmService:
    def __init__(self, conn):
        self.contacts = ContactRepository(conn)
        self.activities = ActivityRepository(conn)
        self._follow_ups = FollowUpRepository(conn)
        self._appointments = AppointmentRepository(conn)
        self._production = ProductionRepository(conn)

    def search(self, query: str) -> list[Contact]:
        return self.contacts.search(query)

    def untouched_leads(self) -> list[Contact]:
        return self.contacts.without_activity("lead")

    def timeline(self, contact_id) -> ContactTimeline:
        contact = self.contacts.get(contact_id)
        if contact is None:
            raise NotFoundError(f"contacts #{contact_id} not found")
        return ContactTimeline(
            contact=contact,
            activities=self.activities.for_contact(contact_id),
            follow_ups=self._follow_ups.for_contact(contact_id),
            appointments=self._appointments.for_contact(contact_id),
            production=self._production.for_contact(contact_id),
        )

    def names(self, contact_ids) -> dict[int, str]:
        names = {}
        for contact_id in set(contact_ids) - {None}:
            contact = self.contacts.get(contact_id)
            if contact is not None:
                names[contact_id] = contact.full_name
        return names
