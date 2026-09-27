from datetime import date, timedelta

from app.crm.repository import ContactRepository
from app.planner.repository import AppointmentRepository, FollowUpRepository


def today_overview(conn, today: date) -> dict:
    start = today.isoformat()
    end = (today + timedelta(days=1)).isoformat()
    follow_ups = FollowUpRepository(conn).open_due_before(end)
    return {
        "date": start,
        "appointments": AppointmentRepository(conn).starting_between(start, end),
        "overdue_follow_ups": [f for f in follow_ups if f["due_at"] < start],
        "due_today_follow_ups": [f for f in follow_ups if f["due_at"] >= start],
        "untouched_leads": ContactRepository(conn).untouched_leads(),
        "contact_count": ContactRepository(conn).count(),
    }
