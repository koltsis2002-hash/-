from dataclasses import dataclass

CONTACT_STATUSES = ("lead", "prospect", "client", "inactive")
ACTIVITY_TYPES = ("call", "meeting", "email", "message", "note")
FOLLOW_UP_PRIORITIES = ("low", "normal", "high")
FOLLOW_UP_STATUSES = ("open", "done", "cancelled")
APPOINTMENT_STATUSES = ("scheduled", "completed", "cancelled", "no_show")
GOAL_METRICS = ("calls", "contacts", "first_meetings", "second_meetings", "third_meetings", "contracts", "production")
GOAL_PERIOD_TYPES = ("year", "month", "week", "day")
PRODUCTION_STATUSES = ("pending", "issued", "cancelled")


@dataclass
class Contact:
    first_name: str
    last_name: str = ""
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    source: str | None = None
    status: str = "lead"
    product_interest: str | None = None
    client_flag: bool = False
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self):
        self.client_flag = bool(self.client_flag)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Activity:
    contact_id: int
    activity_type: str
    timestamp: str
    outcome: str | None = None
    notes: str | None = None
    product: str | None = None
    next_action: str | None = None
    followup_date: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class FollowUp:
    contact_id: int
    due_at: str
    priority: str = "normal"
    reason: str | None = None
    status: str = "open"
    completed_at: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Appointment:
    start_at: str
    contact_id: int | None = None
    end_at: str | None = None
    location: str | None = None
    purpose: str | None = None
    status: str = "scheduled"
    notes: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Goal:
    metric: str
    period_type: str
    period_start: str
    period_end: str
    target_value: float
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Production:
    contact_id: int
    product: str
    date: str
    value: float
    status: str = "pending"
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
