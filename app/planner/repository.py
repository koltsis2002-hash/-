from app.core.repository import Repository, now_iso


class FollowUpRepository(Repository):
    table = "follow_ups"
    columns = ("contact_id", "due_at", "priority", "reason", "status", "completed_at")
    default_order = "due_at, id"

    def for_contact(self, contact_id) -> list[dict]:
        return self._rows(
            f"SELECT * FROM follow_ups WHERE contact_id = ? ORDER BY {self.default_order}", (contact_id,)
        )

    def open_due_before(self, cutoff: str) -> list[dict]:
        return self._rows(
            "SELECT f.*, c.first_name, c.last_name FROM follow_ups f JOIN contacts c ON c.id = f.contact_id "
            "WHERE f.status = 'open' AND f.due_at < ? ORDER BY f.due_at, f.id",
            (cutoff,),
        )

    def complete(self, record_id) -> dict:
        return self.update(record_id, status="done", completed_at=now_iso())


class AppointmentRepository(Repository):
    table = "appointments"
    columns = ("contact_id", "start_at", "end_at", "location", "purpose", "status", "notes")
    default_order = "start_at, id"

    def for_contact(self, contact_id) -> list[dict]:
        return self._rows(
            f"SELECT * FROM appointments WHERE contact_id = ? ORDER BY {self.default_order}", (contact_id,)
        )

    def starting_between(self, start: str, end: str) -> list[dict]:
        return self._rows(
            "SELECT a.*, c.first_name, c.last_name FROM appointments a "
            "LEFT JOIN contacts c ON c.id = a.contact_id "
            "WHERE a.start_at >= ? AND a.start_at < ? ORDER BY a.start_at, a.id",
            (start, end),
        )
