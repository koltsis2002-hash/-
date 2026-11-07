"""Loads and validates the editable Business Advisor content (app/services/advisor/data/*.json)."""
import copy
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

QUESTION_TYPES = ("yes_no", "single", "multi", "number")
YES_NO_OPTIONS = [{"value": "yes", "label": "Ναι"}, {"value": "no", "label": "Όχι"}]
LEVELS = ("confirmed", "possible", "info_needed", "not_priority")
PILLARS = ("people", "staff", "savings", "operations")
CONDITION_OPERATORS = ("eq", "in", "includes", "includes_any", "gte", "lte", "answered", "unresolved")
KNOWLEDGE_KINDS = ("faq", "product", "term", "limitation", "argument", "example")


class ContentError(ValueError):
    pass


@dataclass(frozen=True)
class Content:
    axes: list
    questions: list
    question_by_id: dict
    levels: dict
    pillars: list
    priority_rules: list
    needs: list
    need_by_id: dict
    directions: dict
    solution_labels: dict
    knowledge: dict
    presentation: dict

    def axis_title(self, axis_id) -> str:
        return next(a["title"] for a in self.axes if a["id"] == axis_id)

    @property
    def default_topics(self) -> list:
        return [a["id"] for a in self.axes if a.get("priority")]

    def topics(self, selected) -> list:
        """Selected categories in their fixed priority order; none selected means the priority ones."""
        chosen = [a["id"] for a in self.axes if a["id"] in (selected or ())]
        return chosen or self.default_topics

    @property
    def categories(self) -> set:
        return {d["category"] for d in self.directions.values()}


def condition_questions(cond) -> set:
    if cond is None:
        return set()
    if "all" in cond or "any" in cond:
        return set().union(*(condition_questions(c) for c in cond.get("all", cond.get("any", []))))
    if "not" in cond:
        return condition_questions(cond["not"])
    return {cond["q"]}


def _check_condition(cond, where):
    if not isinstance(cond, dict) or len(cond) == 0:
        raise ContentError(f"{where}: η συνθήκη πρέπει να είναι αντικείμενο")
    if "all" in cond or "any" in cond:
        key = "all" if "all" in cond else "any"
        if len(cond) != 1 or not isinstance(cond[key], list) or not cond[key]:
            raise ContentError(f"{where}: το '{key}' θέλει μη κενή λίστα συνθηκών")
        for c in cond[key]:
            _check_condition(c, where)
        return
    if "not" in cond:
        if len(cond) != 1:
            raise ContentError(f"{where}: το 'not' δέχεται μία συνθήκη")
        _check_condition(cond["not"], where)
        return
    ops = [k for k in cond if k != "q"]
    if "q" not in cond or len(ops) != 1 or ops[0] not in CONDITION_OPERATORS:
        raise ContentError(f"{where}: μη έγκυρη συνθήκη {cond}")


def _read(data_dir, name):
    with open(Path(data_dir) / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_content(data_dir=DATA_DIR) -> Content:
    q_data = _read(data_dir, "questions.json")
    n_data = _read(data_dir, "needs.json")
    s_data = _read(data_dir, "solutions.json")
    k_data = _read(data_dir, "knowledge.json")
    p_data = _read(data_dir, "presentation.json")

    axes = q_data["axes"]
    axis_ids = [a["id"] for a in axes]
    if len(set(axis_ids)) != len(axis_ids):
        raise ContentError("Διπλό id άξονα")
    for a in axes:
        if a["pillar"] not in PILLARS:
            raise ContentError(f"Άξονας {a['id']}: άγνωστος πυλώνας {a['pillar']}")

    need_ids = [n["id"] for n in n_data["needs"]]
    if len(set(need_ids)) != len(need_ids):
        raise ContentError("Διπλό id ανάγκης")

    questions, seen = [], {}
    for raw in q_data["questions"]:
        q = copy.deepcopy(raw)
        qid = q.get("id")
        if not qid or qid in seen:
            raise ContentError(f"Ερώτηση χωρίς id ή με διπλό id: {qid}")
        if q.get("axis") not in axis_ids:
            raise ContentError(f"{qid}: άγνωστος άξονας {q.get('axis')}")
        if q.get("type") not in QUESTION_TYPES:
            raise ContentError(f"{qid}: άγνωστος τύπος {q.get('type')}")
        if not q.get("text") or not q.get("short"):
            raise ContentError(f"{qid}: λείπει κείμενο ή σύντομη ετικέτα")
        if q["type"] == "yes_no":
            q["options"] = copy.deepcopy(YES_NO_OPTIONS)
        if q["type"] in ("single", "multi"):
            values = [o["value"] for o in q.get("options", [])]
            if len(values) < 2 or len(set(values)) != len(values):
                raise ContentError(f"{qid}: χρειάζονται τουλάχιστον δύο μοναδικές επιλογές")
        if q["type"] == "number" and q.get("min", 0) > q.get("max", 10**12):
            raise ContentError(f"{qid}: min > max")
        q.setdefault("options", [])
        q.setdefault("exclusive", [])
        if not set(q["exclusive"]) <= {o["value"] for o in q["options"]}:
            raise ContentError(f"{qid}: τα exclusive πρέπει να είναι επιλογές της ερώτησης")
        q.setdefault("show_if", None)
        if q["show_if"] is not None:
            _check_condition(q["show_if"], qid)
            unknown = condition_questions(q["show_if"]) - set(seen)
            if unknown:
                raise ContentError(f"{qid}: η συνθήκη εμφάνισης αναφέρεται σε μεταγενέστερη ή άγνωστη ερώτηση {unknown}")
        q.setdefault("next", [])
        q.setdefault("needs", [])
        q.setdefault("core", False)
        q.setdefault("hint", None)
        q.setdefault("allow_unknown", True)
        q.setdefault("allow_note", True)
        if not set(q["needs"]) <= set(need_ids):
            raise ContentError(f"{qid}: άγνωστες ανάγκες {set(q['needs']) - set(need_ids)}")
        questions.append(q)
        seen[qid] = q
    for q in questions:
        if not set(q["next"]) <= set(seen):
            raise ContentError(f"{q['id']}: άγνωστες επόμενες ερωτήσεις {set(q['next']) - set(seen)}")

    levels = {lv["id"]: lv["label"] for lv in n_data["levels"]}
    if tuple(levels) != LEVELS:
        raise ContentError(f"Τα επίπεδα αναγκών πρέπει να είναι {LEVELS}")
    pillars = n_data["pillars"]
    if tuple(p["id"] for p in pillars) != PILLARS:
        raise ContentError(f"Οι πυλώνες πρέπει να είναι {PILLARS}")
    needs = []
    for n in n_data["needs"]:
        if n.get("pillar") not in PILLARS or n.get("axis") not in axis_ids:
            raise ContentError(f"Ανάγκη {n['id']}: άγνωστος πυλώνας ή άξονας")
        if set(n.get("statements", {})) != set(LEVELS):
            raise ContentError(f"Ανάγκη {n['id']}: χρειάζεται διατύπωση για κάθε επίπεδο")
        if not set(n.get("evidence", [])) <= set(seen):
            raise ContentError(f"Ανάγκη {n['id']}: άγνωστες ερωτήσεις τεκμηρίωσης")
        for i, rule in enumerate(n.get("rules", [])):
            where = f"Ανάγκη {n['id']} κανόνας {i + 1}"
            if rule.get("level") not in LEVELS or not rule.get("reason"):
                raise ContentError(f"{where}: χρειάζεται έγκυρο level και reason")
            _check_condition(rule.get("when"), where)
            if not condition_questions(rule["when"]) <= set(seen):
                raise ContentError(f"{where}: άγνωστες ερωτήσεις στη συνθήκη")
        needs.append(n)

    directions = {}
    for d in s_data["directions"]:
        if d.get("need") not in need_ids or d["need"] in directions:
            raise ContentError(f"Κατεύθυνση με άγνωστη ή διπλή ανάγκη: {d.get('need')}")
        for key in ("category", "title", "why", "direction", "benefits", "examine", "information_needed"):
            if not d.get(key):
                raise ContentError(f"Κατεύθυνση {d['need']}: λείπει το πεδίο {key}")
        directions[d["need"]] = d
    if set(directions) != set(need_ids):
        raise ContentError(f"Λείπουν κατευθύνσεις για: {set(need_ids) - set(directions)}")
    solution_labels = {k: s_data[k] for k in ("no_product_label", "tax_note", "disclaimer")}

    kinds = [k["id"] for k in k_data["kinds"]]
    if tuple(kinds) != KNOWLEDGE_KINDS:
        raise ContentError(f"Τα είδη γνωσιακής βάσης πρέπει να είναι {KNOWLEDGE_KINDS}")
    entry_ids = set()
    for e in k_data["entries"]:
        if e["id"] in entry_ids or e.get("kind") not in kinds:
            raise ContentError(f"Καταχώριση γνωσιακής βάσης {e['id']}: διπλό id ή άγνωστο είδος")
        entry_ids.add(e["id"])
        if not e.get("sources") or any(s["source"] not in k_data["sources"] for s in e["sources"]):
            raise ContentError(f"Καταχώριση {e['id']}: κάθε καταχώριση χρειάζεται γνωστή πηγή")
        if not set(e.get("needs", [])) <= set(need_ids):
            raise ContentError(f"Καταχώριση {e['id']}: άγνωστες ανάγκες")

    presentation = {k: v for k, v in p_data.items() if not k.startswith("_")}
    if len(presentation["screens"]) != 10:
        raise ContentError("Η παρουσίαση έχει ακριβώς 10 οθόνες")

    return Content(
        axes=axes, questions=questions, question_by_id=seen, levels=levels, pillars=pillars,
        priority_rules=n_data["priority_rules"], needs=needs, need_by_id={n["id"]: n for n in needs},
        directions=directions, solution_labels=solution_labels,
        knowledge={k: v for k, v in k_data.items() if not k.startswith("_")}, presentation=presentation,
    )


@cache
def default_content() -> Content:
    return load_content()
