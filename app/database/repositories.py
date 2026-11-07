import json
import sqlite3
from contextlib import contextmanager
from dataclasses import fields

from app.core.errors import NotFoundError, ValidationError
from app.core.timeutil import now_iso
from app.database.connection import fold
from app.models.advisor import (
    AdvisorPresentation, Answer, DocumentPage, IndexedDocument, Preparation, StoredSummary,
)
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


class AdvisorPresentationRepository(Repository):
    table = "advisor_presentations"
    model = AdvisorPresentation
    default_order = "updated_at DESC, id DESC"


PREPARATION_COLUMNS = (
    "business_name", "owner_name", "industry", "legal_form", "employees", "partners",
    "facilities", "existing_coverage", "financial_obligations",
)


class PreparationRepository:
    def __init__(self, conn):
        self.conn = conn

    def get(self, presentation_id) -> Preparation | None:
        row = self.conn.execute(
            "SELECT * FROM advisor_preparations WHERE presentation_id = ?", (presentation_id,)
        ).fetchone()
        if row is None:
            return None
        values = dict(row)
        values["interests"] = json.loads(values["interests"])
        values["shared_fields"] = json.loads(values["shared_fields"])
        return Preparation(**values)

    def save(self, prep: Preparation) -> Preparation:
        values = {c: getattr(prep, c) for c in PREPARATION_COLUMNS}
        values.update(
            presentation_id=prep.presentation_id, interests=json.dumps(list(prep.interests)),
            shared_fields=json.dumps(list(prep.shared_fields)), updated_at=now_iso(),
        )
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        updates = ", ".join(f"{c} = excluded.{c}" for c in values if c != "presentation_id")
        with _write(self.conn):
            self.conn.execute(
                f"INSERT INTO advisor_preparations ({cols}) VALUES ({marks}) "
                f"ON CONFLICT (presentation_id) DO UPDATE SET {updates}",
                tuple(values.values()),
            )
        return self.get(prep.presentation_id)


class InternalNotesRepository:
    def __init__(self, conn):
        self.conn = conn

    def get(self, presentation_id) -> str:
        row = self.conn.execute(
            "SELECT notes FROM advisor_internal_notes WHERE presentation_id = ?", (presentation_id,)
        ).fetchone()
        return row["notes"] if row else ""

    def save(self, presentation_id, notes: str) -> None:
        with _write(self.conn):
            self.conn.execute(
                "INSERT INTO advisor_internal_notes (presentation_id, notes, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT (presentation_id) DO UPDATE SET notes = excluded.notes, updated_at = excluded.updated_at",
                (presentation_id, notes, now_iso()),
            )


class AnswerRepository:
    def __init__(self, conn):
        self.conn = conn

    def for_presentation(self, presentation_id) -> dict[str, Answer]:
        rows = self.conn.execute(
            "SELECT * FROM advisor_answers WHERE presentation_id = ? ORDER BY question_id", (presentation_id,)
        )
        return {
            r["question_id"]: Answer(
                question_id=r["question_id"], status=r["status"],
                value=None if r["value"] is None else json.loads(r["value"]),
                note=r["note"], updated_at=r["updated_at"],
            )
            for r in rows
        }

    def save(self, presentation_id, answer: Answer) -> None:
        value = None if answer.value is None else json.dumps(answer.value, ensure_ascii=False)
        with _write(self.conn):
            self.conn.execute(
                "INSERT INTO advisor_answers (presentation_id, question_id, status, value, note, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (presentation_id, question_id) DO UPDATE SET "
                "status = excluded.status, value = excluded.value, note = excluded.note, "
                "updated_at = excluded.updated_at",
                (presentation_id, answer.question_id, answer.status, value, answer.note, now_iso()),
            )

    def delete(self, presentation_id, question_id) -> None:
        with _write(self.conn):
            self.conn.execute(
                "DELETE FROM advisor_answers WHERE presentation_id = ? AND question_id = ?",
                (presentation_id, question_id),
            )


class SummaryRepository:
    def __init__(self, conn):
        self.conn = conn

    def get(self, presentation_id) -> StoredSummary | None:
        row = self.conn.execute(
            "SELECT * FROM advisor_summaries WHERE presentation_id = ?", (presentation_id,)
        ).fetchone()
        if row is None:
            return None
        return StoredSummary(
            presentation_id=row["presentation_id"], content=json.loads(row["content"]), edited=bool(row["edited"]),
            approved_at=row["approved_at"], updated_at=row["updated_at"],
        )

    def save(self, presentation_id, content: dict, edited: bool) -> StoredSummary:
        """Any change to the content withdraws a previous approval."""
        encoded = json.dumps(content, ensure_ascii=False, sort_keys=True)
        current = self.get(presentation_id)
        if current is not None and json.dumps(current.content, ensure_ascii=False, sort_keys=True) == encoded \
                and current.edited == edited:
            return current
        with _write(self.conn):
            self.conn.execute(
                "INSERT INTO advisor_summaries (presentation_id, content, edited, approved_at, updated_at) "
                "VALUES (?, ?, ?, NULL, ?) ON CONFLICT (presentation_id) DO UPDATE SET "
                "content = excluded.content, edited = excluded.edited, approved_at = NULL, "
                "updated_at = excluded.updated_at",
                (presentation_id, encoded, int(edited), now_iso()),
            )
        return self.get(presentation_id)

    def approve(self, presentation_id) -> StoredSummary:
        with _write(self.conn):
            cur = self.conn.execute(
                "UPDATE advisor_summaries SET approved_at = ? WHERE presentation_id = ?",
                (now_iso(), presentation_id),
            )
        if cur.rowcount == 0:
            raise NotFoundError(f"summary for presentation #{presentation_id} not found")
        return self.get(presentation_id)


class DocumentRepository:
    def __init__(self, conn):
        self.conn = conn

    def list_all(self) -> list[IndexedDocument]:
        return [IndexedDocument(**dict(r)) for r in self.conn.execute("SELECT * FROM documents ORDER BY filename")]

    def replace(self, filename: str, sha256: str, pages: list[str]) -> IndexedDocument:
        with _write(self.conn):
            self.conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))
            cur = self.conn.execute(
                "INSERT INTO documents (filename, sha256, page_count, indexed_at) VALUES (?, ?, ?, ?)",
                (filename, sha256, len(pages), now_iso()),
            )
            self.conn.executemany(
                "INSERT INTO document_pages (document_id, page, text, folded) VALUES (?, ?, ?, ?)",
                [(cur.lastrowid, i, text, fold(text)) for i, text in enumerate(pages, start=1)],
            )
        return next(d for d in self.list_all() if d.filename == filename)

    def delete(self, filename: str) -> None:
        with _write(self.conn):
            self.conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))

    def pages_containing_any(self, folded_terms: list[str], limit: int = 200) -> list[DocumentPage]:
        if not folded_terms:
            return []
        where = " OR ".join("p.folded LIKE ? ESCAPE '\\'" for _ in folded_terms)
        rows = self.conn.execute(
            f"SELECT d.filename, p.page, p.text FROM document_pages p JOIN documents d ON d.id = p.document_id "
            f"WHERE {where} ORDER BY d.filename, p.page LIMIT ?",
            (*(_like_pattern(t) for t in folded_terms), limit),
        )
        return [DocumentPage(filename=r["filename"], page=r["page"], text=r["text"]) for r in rows]
