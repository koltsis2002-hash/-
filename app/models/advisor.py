from dataclasses import dataclass, field

PRESENTATION_STATUSES = ("draft", "in_progress", "completed")
ANSWER_STATUSES = ("answered", "unknown", "skipped")
SCREEN_COUNT = 10

# Preparation fields the advisor may choose to show to the client. Internal notes are not among them.
SHAREABLE_FIELDS = (
    "business_name", "owner_name", "industry", "legal_form", "employees", "partners",
    "facilities", "existing_coverage", "financial_obligations",
)
# Shared by default because they only personalise the welcome screen; everything else is opt-in.
DEFAULT_SHARED_FIELDS = ("business_name", "owner_name")


@dataclass
class AdvisorPresentation:
    meeting_date: str
    contact_id: int | None = None
    previous_id: int | None = None
    status: str = "draft"
    current_screen: int = 0
    current_question: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class Preparation:
    presentation_id: int
    business_name: str | None = None
    owner_name: str | None = None
    industry: str | None = None
    legal_form: str | None = None
    employees: int | None = None
    partners: int | None = None
    facilities: str | None = None
    existing_coverage: str | None = None
    financial_obligations: str | None = None
    interests: list[str] = field(default_factory=list)
    shared_fields: list[str] = field(default_factory=lambda: list(DEFAULT_SHARED_FIELDS))
    updated_at: str | None = None


@dataclass
class Answer:
    question_id: str
    status: str
    value: object = None
    note: str | None = None
    updated_at: str | None = None


@dataclass
class StoredSummary:
    presentation_id: int
    content: dict
    edited: bool = False
    approved_at: str | None = None
    updated_at: str | None = None


@dataclass
class IndexedDocument:
    filename: str
    sha256: str
    page_count: int
    indexed_at: str
    id: int | None = None


@dataclass
class DocumentPage:
    filename: str
    page: int
    text: str
