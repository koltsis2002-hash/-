from app.database.repositories import GoalRepository, ProductionRepository
from app.models.entities import Goal


class PerformanceService:
    def __init__(self, conn):
        self.goals = GoalRepository(conn)
        self.production = ProductionRepository(conn)

    def active_goals(self, day: str) -> list[Goal]:
        return self.goals.covering(day)
