from app.database.connection import open_database
from app.services.crm import CrmService
from app.services.performance import PerformanceService
from app.services.planner import PlannerService


class Services:
    """Entry point for the UI and CLI: one open database plus the services that use it."""

    def __init__(self, conn):
        self._conn = conn
        self.crm = CrmService(conn)
        self.planner = PlannerService(conn)
        self.performance = PerformanceService(conn)

    @classmethod
    def open(cls, db_path, backup_dir=None) -> "Services":
        return cls(open_database(db_path, backup_dir))

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
