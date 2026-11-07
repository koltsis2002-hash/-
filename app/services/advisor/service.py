"""BusinessAdvisorService: the only entry point the UI uses for the Business Advisor tab.

Advisor methods may return anything. Client methods (client_view, record_answer, set_position,
approve_summary) build their payload from an explicit allow-list: shared preparation fields, the
answers, need statements and documented recommendations. Internal notes, unshared fields and rule
reasons never enter it.
"""
import re
from dataclasses import dataclass
from datetime import date

from app.core.config import PROJECT_ROOT
from app.core.errors import NotFoundError, ValidationError
from app.database.repositories import (
    AdvisorPresentationRepository, AnswerRepository, ContactRepository, DocumentRepository,
    InternalNotesRepository, PreparationRepository, SummaryRepository,
)
from app.models.advisor import (
    ANSWER_STATUSES, SCREEN_COUNT, SHAREABLE_FIELDS, AdvisorPresentation, Answer, Preparation, StoredSummary,
)
from app.services.advisor.content import default_content
from app.services.advisor.documents import IndexReport, index_documents
from app.services.advisor.flow import QuestionFlow
from app.services.advisor.knowledge import AdvisorKnowledgeBase, KnowledgeAnswer
from app.services.advisor.needs import assess_needs
from app.services.advisor.products import Catalog, load_catalog
from app.services.advisor.recommendations import recommend
from app.services.advisor.summary import MAX_DIRECTIONS, build_summary, normalize_summary

DEFAULT_KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
MAX_TEXT = 2000
MAX_NOTE = 500

FIELD_LABELS = {
    "business_name": "Επωνυμία επιχείρησης",
    "owner_name": "Όνομα επιχειρηματία",
    "industry": "Κλάδος δραστηριότητας",
    "legal_form": "Νομική μορφή",
    "employees": "Αριθμός εργαζομένων",
    "partners": "Αριθμός συνεταίρων",
    "facilities": "Εγκαταστάσεις / εξοπλισμός",
    "existing_coverage": "Υφιστάμενες ασφαλιστικές καλύψεις",
    "financial_obligations": "Οικονομικές υποχρεώσεις",
}
NUMBER_FIELDS = ("employees", "partners")
STATUS_LABELS = {"draft": "Προσχέδιο", "in_progress": "Σε εξέλιξη", "completed": "Ολοκληρώθηκε"}


@dataclass
class PresentationOverview:
    presentation: AdvisorPresentation
    preparation: Preparation
    summary: StoredSummary | None

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.presentation.status]


@dataclass
class Assessment:
    flow: QuestionFlow
    needs: list
    recommendations: list
    catalog: Catalog


@dataclass
class Workspace:
    presentation: AdvisorPresentation
    preparation: Preparation
    internal_notes: str
    assessment: Assessment
    summary: StoredSummary
    previous_summary: StoredSummary | None
    contact_name: str | None


class BusinessAdvisorService:
    def __init__(self, conn, knowledge_dir=None, content=None):
        self.presentations = AdvisorPresentationRepository(conn)
        self.preparations = PreparationRepository(conn)
        self.notes = InternalNotesRepository(conn)
        self.answers = AnswerRepository(conn)
        self.summaries = SummaryRepository(conn)
        self.documents = DocumentRepository(conn)
        self._contacts = ContactRepository(conn)
        self.content = content or default_content()
        self.knowledge_dir = DEFAULT_KNOWLEDGE_DIR if knowledge_dir is None else knowledge_dir
        self.knowledge = AdvisorKnowledgeBase(self.content, self.documents)

    # ----- presentations (advisor) ---------------------------------------------------------------

    def get(self, presentation_id) -> AdvisorPresentation:
        p = self.presentations.get(presentation_id)
        if p is None:
            raise NotFoundError(f"presentation #{presentation_id} not found")
        return p

    def overview(self) -> list[PresentationOverview]:
        return [PresentationOverview(p, self.preparation(p.id), self.summaries.get(p.id))
                for p in self.presentations.list_all()]

    def contacts(self):
        return self._contacts.list_all()

    def create(self, meeting_date: str | None = None, contact_id=None, previous_id=None) -> AdvisorPresentation:
        meeting_date = _valid_date(meeting_date or date.today().isoformat())
        contact = None
        if contact_id is not None:
            contact = self._contacts.get(contact_id)
            if contact is None:
                raise ValidationError("Η επαφή δεν βρέθηκε")
        previous = self.get(previous_id) if previous_id is not None else None
        p = self.presentations.add(AdvisorPresentation(
            meeting_date=meeting_date, contact_id=contact_id if contact else (previous.contact_id if previous else None),
            previous_id=previous.id if previous else None,
        ))
        if previous is not None:
            prep = self.preparation(previous.id)
            prep.presentation_id = p.id
            self.preparations.save(prep)
            for answer in self.answers.for_presentation(previous.id).values():
                self.answers.save(p.id, answer)
        else:
            self.preparations.save(Preparation(
                presentation_id=p.id,
                business_name=contact.company if contact else None,
                owner_name=contact.full_name if contact else None,
                interests=self.content.default_topics,
            ))
        return p

    def delete(self, presentation_id) -> None:
        """Deletes the meeting and, by cascade, its preparation, answers, internal notes and summary."""
        self.get(presentation_id)
        self.presentations.delete(presentation_id)

    def set_meeting_date(self, presentation_id, meeting_date: str) -> AdvisorPresentation:
        self.get(presentation_id)
        return self.presentations.update(presentation_id, meeting_date=_valid_date(meeting_date))

    def preparation(self, presentation_id) -> Preparation:
        return self.preparations.get(presentation_id) or Preparation(presentation_id=presentation_id)

    def save_preparation(self, presentation_id, values: dict, shared, interests) -> Preparation:
        self.get(presentation_id)
        prep = Preparation(presentation_id=presentation_id)
        for name in SHAREABLE_FIELDS:
            raw = values.get(name)
            raw = raw.strip() if isinstance(raw, str) else raw
            if name in NUMBER_FIELDS:
                setattr(prep, name, _optional_int(raw, FIELD_LABELS[name]))
            else:
                if raw and len(raw) > MAX_TEXT:
                    raise ValidationError(f"{FIELD_LABELS[name]}: έως {MAX_TEXT} χαρακτήρες")
                setattr(prep, name, raw or None)
        unknown = set(shared) - set(SHAREABLE_FIELDS)
        if unknown:
            raise ValidationError(f"Μη επιτρεπτά πεδία για εμφάνιση: {', '.join(sorted(unknown))}")
        axis_ids = [a["id"] for a in self.content.axes]
        if set(interests) - set(axis_ids):
            raise ValidationError("Άγνωστη κατηγορία ερωτήσεων")
        prep.shared_fields = [f for f in SHAREABLE_FIELDS if f in shared]
        prep.interests = self.content.topics(interests)
        saved = self.preparations.save(prep)
        self._touch(presentation_id)
        return saved

    def internal_notes(self, presentation_id) -> str:
        return self.notes.get(presentation_id)

    def save_internal_notes(self, presentation_id, notes: str) -> None:
        self.get(presentation_id)
        if len(notes or "") > 20000:
            raise ValidationError("Οι σημειώσεις είναι πολύ μεγάλες")
        self.notes.save(presentation_id, notes or "")

    def assess(self, presentation_id) -> Assessment:
        prep = self.preparation(presentation_id)
        flow = QuestionFlow(self.content, self.answers.for_presentation(presentation_id), prep.interests)
        needs = assess_needs(self.content, flow)
        catalog = self.catalog()
        return Assessment(flow, needs, recommend(self.content, needs, catalog), catalog)

    def workspace(self, presentation_id) -> Workspace:
        p = self.get(presentation_id)
        contact = self._contacts.get(p.contact_id) if p.contact_id else None
        return Workspace(
            presentation=p, preparation=self.preparation(p.id), internal_notes=self.notes.get(p.id),
            assessment=self.assess(p.id), summary=self.summary(p.id),
            previous_summary=self.summaries.get(p.previous_id) if p.previous_id else None,
            contact_name=contact.full_name if contact else None,
        )

    # ----- summary ------------------------------------------------------------------------------

    def generated_summary(self, presentation_id) -> dict:
        p = self.get(presentation_id)
        prep = self.preparation(p.id)
        a = self.assess(p.id)
        business = prep.business_name if "business_name" in prep.shared_fields else None
        return build_summary(self.content, p, business, a.flow, a.needs, a.recommendations)

    def summary(self, presentation_id) -> StoredSummary:
        """The advisor's edited summary, or one regenerated from the current answers."""
        stored = self.summaries.get(presentation_id)
        if stored is not None and stored.edited:
            return stored
        return self.summaries.save(presentation_id, self.generated_summary(presentation_id), edited=False)

    def save_summary(self, presentation_id, raw: dict) -> StoredSummary:
        self.get(presentation_id)
        return self.summaries.save(presentation_id, normalize_summary(raw), edited=True)

    def regenerate_summary(self, presentation_id) -> StoredSummary:
        return self.summaries.save(presentation_id, self.generated_summary(presentation_id), edited=False)

    def approve_summary(self, presentation_id) -> StoredSummary:
        self.summary(presentation_id)
        return self.summaries.approve(presentation_id)

    # ----- client presentation ------------------------------------------------------------------

    def record_answer(self, presentation_id, question_id, status, value=None, note=None) -> dict:
        p = self.get(presentation_id)
        q = self.content.question_by_id.get(question_id)
        if q is None:
            raise ValidationError("Άγνωστη ερώτηση")
        flow = QuestionFlow(self.content, self.answers.for_presentation(p.id), self.preparation(p.id).interests)
        if question_id not in flow.visible_ids:
            raise ValidationError("Η ερώτηση δεν αφορά πλέον τη συζήτηση")
        if status not in ANSWER_STATUSES:
            raise ValidationError("Μη έγκυρη κατάσταση απάντησης")
        if status == "unknown" and not q["allow_unknown"]:
            raise ValidationError("Η ερώτηση δεν δέχεται «Δεν γνωρίζω»")
        note = (note or "").strip() or None
        if note and (not q["allow_note"] or len(note) > MAX_NOTE):
            raise ValidationError(f"Το σχόλιο επιτρέπεται έως {MAX_NOTE} χαρακτήρες")
        value = _validate_value(q, value) if status == "answered" else None
        self.answers.save(p.id, Answer(question_id=question_id, status=status, value=value, note=note))
        if p.status == "draft":
            self.presentations.update(p.id, status="in_progress")
        else:
            self._touch(p.id)
        return self.client_view(p.id)

    def set_topics(self, presentation_id, topics) -> dict:
        """Chooses the question categories for this meeting, from the preparation or during the presentation."""
        self.get(presentation_id)
        if not isinstance(topics, list) or set(topics) - {a["id"] for a in self.content.axes}:
            raise ValidationError("Άγνωστη κατηγορία ερωτήσεων")
        prep = self.preparation(presentation_id)
        prep.interests = self.content.topics(topics)
        self.preparations.save(prep)
        return self.client_view(presentation_id)

    def clear_answer(self, presentation_id, question_id) -> dict:
        self.get(presentation_id)
        self.answers.delete(presentation_id, question_id)
        return self.client_view(presentation_id)

    def set_position(self, presentation_id, screen, question_id=None) -> None:
        p = self.get(presentation_id)
        if not isinstance(screen, int) or not 0 <= screen < SCREEN_COUNT:
            raise ValidationError("Μη έγκυρη οθόνη")
        if question_id is not None and question_id not in self.content.question_by_id \
                and not re.fullmatch(r"slide:\d{1,2}", str(question_id)):
            raise ValidationError("Άγνωστη θέση παρουσίασης")
        changes = {"current_screen": screen, "current_question": question_id}
        if screen == SCREEN_COUNT - 1:
            changes["status"] = "completed"
        elif p.status == "draft" and screen > 0:
            changes["status"] = "in_progress"
        self.presentations.update(p.id, **changes)

    def client_view(self, presentation_id) -> dict:
        p = self.get(presentation_id)
        prep = self.preparation(p.id)
        a = self.assess(p.id)
        summary = self.summary(p.id)
        shared = {f: getattr(prep, f) for f in prep.shared_fields
                  if f in SHAREABLE_FIELDS and getattr(prep, f) not in (None, "")}
        content = self.content
        return {
            "id": p.id,
            "meeting_date": p.meeting_date,
            "position": {"screen": p.current_screen, "question": p.current_question},
            "business": shared,
            "business_labels": {f: FIELD_LABELS[f] for f in shared},
            "topics": a.flow.axis_order,
            "content": content.presentation,
            "axes": content.axes,
            "pillars": content.pillars,
            "levels": [{"id": k, "label": v} for k, v in content.levels.items()],
            "flow": {
                "questions": [_client_question(q, shared) for q in a.flow.visible],
                "answers": {qid: {"status": ans.status, "value": ans.value, "note": ans.note}
                            for qid, ans in a.flow.active.items()},
                "handled": a.flow.handled,
                "total": a.flow.total,
            },
            "needs": [{"id": n.id, "title": n.title, "pillar": n.pillar, "axis": n.axis, "level": n.level,
                       "level_label": n.level_label, "statement": n.statement,
                       "evidence": [{"label": e["label"], "answer": e["answer"]} for e in n.evidence]}
                      for n in a.needs],
            "recommendations": [_client_recommendation(r, content) for r in a.recommendations[:MAX_DIRECTIONS]],
            "more_topics": [r.need.title for r in a.recommendations[MAX_DIRECTIONS:]],
            "solution_labels": content.solution_labels,
            "summary": {"content": summary.content, "approved": summary.approved_at is not None},
        }

    # ----- knowledge & products -----------------------------------------------------------------

    def catalog(self) -> Catalog:
        page_counts = {d.filename: d.page_count for d in self.documents.list_all()}
        return load_catalog(self.knowledge_dir, self.content.categories, page_counts)

    def search_knowledge(self, query: str) -> KnowledgeAnswer:
        return self.knowledge.search(query[:300])

    def index_documents(self) -> IndexReport:
        return index_documents(self.knowledge_dir / "products", self.documents)

    def indexed_documents(self):
        return self.documents.list_all()

    def _touch(self, presentation_id) -> None:
        self.presentations.update(presentation_id, status=self.get(presentation_id).status)


def _client_question(q, shared) -> dict:
    keys = ("id", "axis", "core", "short", "text", "hint", "type", "options", "exclusive", "unit", "min", "max",
            "chart", "allow_unknown", "allow_note")
    out = {k: q.get(k) for k in keys}
    source = q.get("prefill_from")
    out["suggested"] = shared.get(source) if source else None
    return out


def _client_recommendation(r, content) -> dict:
    d = r.direction
    return {
        "need_id": r.need.id,
        "need_title": r.need.title,
        "level": r.need.level,
        "level_label": r.need.level_label,
        "title": d["title"],
        "why": d["why"],
        "direction": d["direction"],
        "benefits": d["benefits"],
        "examine": d["examine"] + ([content.solution_labels["tax_note"]] if d.get("tax") else []),
        "products": [{
            "name": p.name, "provider": p.provider, "summary": p.summary,
            "benefits": [{"text": c.text, "source": c.source} for c in p.benefits],
            "limitations": [{"text": c.text, "source": c.source} for c in p.limitations],
        } for p in r.products],
        "status_label": (content.solution_labels["no_product_label"] if not r.documented
                         else "Τεκμηριωμένη λύση από τα έγγραφα όρων"),
    }


def _valid_date(text: str) -> str:
    try:
        return date.fromisoformat(str(text).strip()).isoformat()
    except ValueError as exc:
        raise ValidationError("Μη έγκυρη ημερομηνία συνάντησης") from exc


def _optional_int(raw, label):
    if raw in (None, ""):
        return None
    try:
        number = int(str(raw).strip())
    except ValueError as exc:
        raise ValidationError(f"{label}: χρειάζεται ακέραιος αριθμός") from exc
    if number < 0:
        raise ValidationError(f"{label}: δεν μπορεί να είναι αρνητικός")
    return number


def _validate_value(q, value):
    options = [o["value"] for o in q["options"]]
    if q["type"] in ("yes_no", "single"):
        if value not in options:
            raise ValidationError("Μη έγκυρη επιλογή")
        return value
    if q["type"] == "multi":
        if not isinstance(value, list) or not value or not set(value) <= set(options):
            raise ValidationError("Επιλέξτε μία ή περισσότερες έγκυρες απαντήσεις")
        if len(value) > 1 and set(value) & set(q["exclusive"]):
            raise ValidationError("Αυτή η επιλογή δεν συνδυάζεται με άλλες")
        return [o for o in options if o in value]
    if isinstance(value, str):
        digits = value.replace(".", "").replace(" ", "").strip()
        if not digits.isdigit():
            raise ValidationError("Χρειάζεται ακέραιος αριθμός")
        value = int(digits)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise ValidationError("Χρειάζεται ακέραιος αριθμός")
    number = int(value)
    if not q.get("min", 0) <= number <= q.get("max", 10**12):
        raise ValidationError(f"Ο αριθμός πρέπει να είναι από {q.get('min', 0)} έως {q.get('max')}")
    return number
