from dataclasses import dataclass
from datetime import date, timedelta

from app.core.timeutil import now_iso
from app.database.repositories import AppointmentRepository, ContactRepository, FollowUpRepository
from app.models.entities import Appointment, Contact, FollowUp


@dataclass
class TodayOverview:
    date: str
    appointments: list[Appointment]
    overdue_follow_ups: list[FollowUp]
    due_today_follow_ups: list[FollowUp]
    untouched_leads: list[Contact]
    contact_count: int


class PlannerService:
    def __init__(self, conn):
        self.follow_ups = FollowUpRepository(conn)
        self.appointments = AppointmentRepository(conn)
        self._contacts = ContactRepository(conn)

    def complete_follow_up(self, follow_up_id) -> FollowUp:
        return self.follow_ups.update(follow_up_id, status="done", completed_at=now_iso())

    def today(self, today: date) -> TodayOverview:
        start = today.isoformat()
        end = (today + timedelta(days=1)).isoformat()
        due = self.follow_ups.open_due_before(end)
        return TodayOverview(
            date=start,
            appointments=self.appointments.starting_between(start, end),
            overdue_follow_ups=[f for f in due if f.due_at < start],
            due_today_follow_ups=[f for f in due if f.due_at >= start],
            untouched_leads=self._contacts.without_activity("lead"),
            contact_count=self._contacts.count(),
        )
