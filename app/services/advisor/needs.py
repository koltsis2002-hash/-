"""NeedsAssessment: interpretable rules turn the active answers into need levels. No numeric risk scores."""
from dataclasses import dataclass

from app.services.advisor.content import LEVELS, PILLARS
from app.services.advisor.flow import QuestionFlow, evaluate, is_answered

FALLBACK_REASON = "Δεν ισχύει κανένας κανόνας: το θέμα δεν συζητήθηκε ή οι απαντήσεις ήταν «Δεν γνωρίζω» / «Παράλειψη»."


@dataclass
class AssessedNeed:
    id: str
    title: str
    pillar: str
    axis: str
    level: str
    level_label: str
    statement: str
    reason: str
    evidence: list
    discussed: bool

    @property
    def is_priority(self) -> bool:
        return self.level in ("confirmed", "possible")


def assess_needs(content, flow: QuestionFlow, interests=()) -> list[AssessedNeed]:
    ctx = flow.context()
    assessed = []
    for index, need in enumerate(content.needs):
        level, reason = "info_needed", FALLBACK_REASON
        for rule in need["rules"]:
            if evaluate(rule["when"], ctx):
                level, reason = rule["level"], rule["reason"]
                break
        evidence = [
            {"question": qid, "label": content.question_by_id[qid]["short"], "answer": flow.answer_label(qid)}
            for qid in need["evidence"] if is_answered(flow.active.get(qid))
        ]
        discussed = any(qid in flow.active for qid in need["evidence"])
        assessed.append((index, AssessedNeed(
            id=need["id"], title=need["title"], pillar=need["pillar"], axis=need["axis"], level=level,
            level_label=content.levels[level], statement=need["statements"][level], reason=reason,
            evidence=evidence, discussed=discussed,
        )))

    def priority(item):
        index, n = item
        return LEVELS.index(n.level), PILLARS.index(n.pillar), 0 if n.axis in interests else 1, index

    return [n for _, n in sorted(assessed, key=priority)]
