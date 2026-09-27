from app.core.db import fold
from app.core.repository import Repository


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class ContactRepository(Repository):
    table = "contacts"
    columns = (
        "first_name", "last_name", "phone", "email", "company", "source",
        "status", "product_interest", "client_flag",
    )
    default_order = "last_name, first_name, id"

    def search(self, query: str) -> list[dict]:
        terms = fold(query).split()
        if not terms:
            return self.list()
        haystack = (
            "jarvis_fold(first_name || ' ' || last_name || ' ' || coalesce(phone, '') || ' ' "
            "|| coalesce(email, '') || ' ' || coalesce(company, ''))"
        )
        where = " AND ".join(f"{haystack} LIKE ? ESCAPE '\\'" for _ in terms)
        return self._rows(
            f"SELECT * FROM contacts WHERE {where} ORDER BY {self.default_order}",
            tuple(_like_pattern(t) for t in terms),
        )

    def untouched_leads(self) -> list[dict]:
        return self._rows(
            "SELECT * FROM contacts c WHERE status = 'lead' "
            "AND NOT EXISTS (SELECT 1 FROM activities a WHERE a.contact_id = c.id) "
            "ORDER BY created_at, id"
        )


class ActivityRepository(Repository):
    table = "activities"
    columns = (
        "contact_id", "type", "timestamp", "outcome", "notes", "product", "next_action", "followup_date",
    )
    default_order = "timestamp DESC, id DESC"

    def for_contact(self, contact_id) -> list[dict]:
        return self._rows(
            f"SELECT * FROM activities WHERE contact_id = ? ORDER BY {self.default_order}", (contact_id,)
        )
