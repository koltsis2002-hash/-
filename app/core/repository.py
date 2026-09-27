from datetime import datetime


class NotFoundError(LookupError):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Repository:
    table: str
    columns: tuple[str, ...]
    default_order = "id"

    def __init__(self, conn):
        self.conn = conn

    def _check(self, fields):
        unknown = set(fields) - set(self.columns)
        if unknown:
            raise ValueError(f"Unknown {self.table} field(s): {', '.join(sorted(unknown))}")

    def _rows(self, sql, params=()) -> list[dict]:
        return [dict(r) for r in self.conn.execute(sql, params)]

    def create(self, **fields) -> dict:
        self._check(fields)
        now = now_iso()
        fields = {**fields, "created_at": now, "updated_at": now}
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self.conn:
            cur = self.conn.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({marks})", tuple(fields.values()))
        return self.get(cur.lastrowid)

    def get(self, record_id) -> dict | None:
        row = self.conn.execute(f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)).fetchone()
        return dict(row) if row else None

    def list(self) -> list[dict]:
        return self._rows(f"SELECT * FROM {self.table} ORDER BY {self.default_order}")

    def update(self, record_id, **fields) -> dict:
        if not fields:
            raise ValueError("No fields to update")
        self._check(fields)
        fields = {**fields, "updated_at": now_iso()}
        assignments = ", ".join(f"{c} = ?" for c in fields)
        with self.conn:
            cur = self.conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?", (*fields.values(), record_id)
            )
        if cur.rowcount == 0:
            raise NotFoundError(f"{self.table} #{record_id} not found")
        return self.get(record_id)

    def delete(self, record_id) -> None:
        with self.conn:
            cur = self.conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (record_id,))
        if cur.rowcount == 0:
            raise NotFoundError(f"{self.table} #{record_id} not found")

    def count(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]
