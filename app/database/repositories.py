import sqlite3
from contextlib import contextmanager
from dataclasses import fields

from app.core.errors import NotFoundError, ValidationError
from app.core.timeutil import now_iso
from app.database.connection import fold
from app.models.entities import Activity, Appointment, Contact, FollowUp, Goal, Production

MANAGED_FIELDS = ("id", "created_at", "updated_at")


@contextmanager
def _write(conn):
    # Constraint violations surface as ValidationError so upper layers never depend on sqlite3.
    try:
        with conn:
            yield
    except sqlite3.IntegrityError as exc:
        raise ValidationError(str(exc)) from exc


class Repository:
    """The only layer that issues SQL. Table and column names come from code, never from input."""

    table: str
    model: type
    default_order = "id"

    def __init__(self, conn):
        self.conn = conn
        self.columns = tuple(f.name for f in fields(self.model) if f.name not in MANAGED_FIELDS)

    def _to_model(self, row):
        return self.model(**dict(row)) if row is not None else None

    def _select(self, where="1", params=(), order=None) -> list:
        sql = f"SELECT * FROM {self.table} WHERE {where} ORDER BY {order or self.default_order}"
        return [self._to_model(r) for r in self.conn.execute(sql, params)]

    def add(self, entity):
        values = {c: getattr(entity, c) for c in self.columns}
        now = now_iso()
        values.update(created_at=now, updated_at=now)
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        with _write(self.conn):
            cur = self.conn.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({marks})", tuple(values.values()))
        return self.get(cur.lastrowid)

    def get(self, entity_id):
        return self._to_model(self.conn.execute(f"SELECT * FROM {self.table} WHERE id = ?", (entity_id,)).fetchone())

    def list_all(self) -> list:
        return self._select()

    def update(self, entity_id, **changes):
        if not changes:
            raise ValidationError("No fields to update")
        unknown = set(changes) - set(self.columns)
        if unknown:
            raise ValidationError(f"Unknown {self.table} field(s): {', '.join(sorted(unknown))}")
        changes["updated_at"] = now_iso()
        assignments = ", ".join(f"{c} = ?" for c in changes)
        with _write(self.conn):
            cur = self.conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?", (*changes.values(), entity_id)
            )
        if cur.rowcount == 0:
            raise NotFoundError(f"{self.table} #{entity_id} not found")
        return self.get(entity_id)

    def delete(self, entity_id) -> None:
        with _write(self.conn):
            cur = self.conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (entity_id,))
        if cur.rowcount == 0:
            raise NotFoundError(f"{self.table} #{entity_id} not found")

    def count(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class ContactRepository(Repository):
    table = "contacts"
    model = Contact
    default_order = "last_name, first_name, id"

    def search(self, query: str) -> list[Contact]:
        terms = (fold(query) or "").split()
        if not terms:
            return self.list_all()
        haystack = (
            "jarvis_fold(first_name || ' ' || last_name || ' ' || coalesce(phone, '') || ' ' "
            "|| coalesce(email, '') || ' ' || coalesce(company, ''))"
        )
        where = " AND ".join(f"{haystack} LIKE ? ESCAPE '\\'" for _ in terms)
        return self._select(where, tuple(_like_pattern(t) for t in terms))

    def without_activity(self, status: str) -> list[Contact]:
        return self._select(
            "status = ? AND NOT EXISTS (SELECT 1 FROM activities a WHERE a.contact_id = contacts.id)",
            (status,), order="created_at, id",
        )


class ActivityRepository(Repository):
    table = "activities"
    model = Activity
    default_order = "timestamp DESC, id DESC"

    def for_contact(self, contact_id) -> list[Activity]:
        return self._select("contact_id = ?", (contact_id,))


class FollowUpRepository(Repository):
    table = "follow_ups"
    model = FollowUp
    default_order = "due_at, id"

    def for_contact(self, contact_id) -> list[FollowUp]:
        return self._select("contact_id = ?", (contact_id,))

    def open_due_before(self, cutoff: str) -> list[FollowUp]:
        return self._select("status = 'open' AND due_at < ?", (cutoff,))


class AppointmentRepository(Repository):
    table = "appointments"
    model = Appointment
    default_order = "start_at, id"

    def for_contact(self, contact_id) -> list[Appointment]:
        return self._select("contact_id = ?", (contact_id,))

    def starting_between(self, start: str, end: str) -> list[Appointment]:
        return self._select("start_at >= ? AND start_at < ?", (start, end))


class GoalRepository(Repository):
    table = "goals"
    model = Goal
    default_order = "period_start, period_type, metric"

    def covering(self, day: str) -> list[Goal]:
        return self._select("period_start <= ? AND period_end >= ?", (day, day))


class ProductionRepository(Repository):
    table = "production"
    model = Production
    default_order = "date DESC, id DESC"

    def for_contact(self, contact_id) -> list[Production]:
        return self._select("contact_id = ?", (contact_id,))

