"""QuestionFlowEngine: decides which questions are relevant, given the answers so far."""
from dataclasses import dataclass

from app.models.advisor import Answer


def is_answered(answer: Answer | None) -> bool:
    return answer is not None and answer.status == "answered" and answer.value not in (None, "", [])


@dataclass
class FlowContext:
    answers: dict
    visible: set

    def answered(self, qid) -> bool:
        return is_answered(self.answers.get(qid))


def evaluate(cond, ctx: FlowContext) -> bool:
    if cond is None:
        return True
    if "all" in cond:
        return all(evaluate(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, ctx) for c in cond["any"])
    if "not" in cond:
        return not evaluate(cond["not"], ctx)
    qid = cond["q"]
    if "unresolved" in cond:
        return (qid in ctx.visible and not ctx.answered(qid)) == bool(cond["unresolved"])
    if "answered" in cond:
        return ctx.answered(qid) == bool(cond["answered"])
    if not ctx.answered(qid):
        return False
    value = ctx.answers[qid].value
    if "eq" in cond:
        return value == cond["eq"]
    if "in" in cond:
        return value in cond["in"]
    if "includes" in cond:
        return isinstance(value, list) and cond["includes"] in value
    if "includes_any" in cond:
        return isinstance(value, list) and any(v in value for v in cond["includes_any"])
    if "gte" in cond:
        return isinstance(value, (int, float)) and value >= cond["gte"]
    if "lte" in cond:
        return isinstance(value, (int, float)) and value <= cond["lte"]
    raise ValueError(f"Unknown condition {cond}")


class QuestionFlow:
    """Visible questions in conversation order, and the answers that still count.

    Only questions of the selected categories are asked, always in the fixed category priority order.
    Visibility is computed in file order (a condition may only refer to earlier questions), so a changed
    answer hides its follow-ups and their stored answers stop counting without being deleted.
    """

    def __init__(self, content, answers: dict, topics=()):
        self.content = content
        self.stored = answers
        self.axis_order = content.topics(topics)
        active, visible_ids = {}, set()
        for q in content.questions:
            if q["axis"] in self.axis_order and evaluate(q["show_if"], FlowContext(active, visible_ids)):
                visible_ids.add(q["id"])
                if q["id"] in answers:
                    active[q["id"]] = answers[q["id"]]
        rank = {a: i for i, a in enumerate(self.axis_order)}
        file_rank = {q["id"]: i for i, q in enumerate(content.questions)}
        self.visible = sorted(
            (q for q in content.questions if q["id"] in visible_ids),
            key=lambda q: (rank[q["axis"]], file_rank[q["id"]]),
        )
        self.visible_ids = visible_ids
        self.active = active

    def context(self) -> FlowContext:
        return FlowContext(self.active, self.visible_ids)

    @property
    def handled(self) -> int:
        return sum(1 for q in self.visible if q["id"] in self.active)

    @property
    def total(self) -> int:
        return len(self.visible)

    def next_open(self):
        return next((q for q in self.visible if q["id"] not in self.active), None)

    def discussed_axes(self) -> list[str]:
        return [a for a in self.axis_order
                if any(q["axis"] == a and is_answered(self.active.get(q["id"])) for q in self.visible)]

    def answer_label(self, qid) -> str | None:
        answer = self.active.get(qid)
        if answer is None:
            return None
        if answer.status == "unknown":
            return "Δεν γνωρίζω"
        if answer.status == "skipped":
            return "Παράλειψη"
        q = self.content.question_by_id[qid]
        labels = {o["value"]: o["label"] for o in q["options"]}
        if q["type"] == "number":
            number = f"{answer.value:,.0f}".replace(",", ".") if isinstance(answer.value, (int, float)) else answer.value
            return f"{number} {q.get('unit', '')}".strip()
        if isinstance(answer.value, list):
            return ", ".join(labels.get(v, v) for v in answer.value)
        return labels.get(answer.value, str(answer.value))
