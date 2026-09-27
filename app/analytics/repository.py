from app.core.repository import Repository


class GoalRepository(Repository):
    table = "goals"
    columns = ("metric", "period_type", "period_start", "period_end", "target_value")
    default_order = "period_start, period_type, metric"

    def covering(self, day: str) -> list[dict]:
        return self._rows(
            f"SELECT * FROM goals WHERE period_start <= ? AND period_end >= ? ORDER BY {self.default_order}",
            (day, day),
        )


class ProductionRepository(Repository):
    table = "production"
    columns = ("contact_id", "product", "date", "value", "status")
    default_order = "date DESC, id DESC"

    def for_contact(self, contact_id) -> list[dict]:
        return self._rows(
            f"SELECT * FROM production WHERE contact_id = ? ORDER BY {self.default_order}", (contact_id,)
        )
