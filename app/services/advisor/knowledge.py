"""AdvisorKnowledgeBase: search over the curated entries and the indexed product PDFs.
Answers come only from those sources; nothing found means "not found", never a guess."""
import re
from dataclasses import dataclass, field

from app.database.connection import fold

STOPWORDS = {fold(w) for w in (
    "πως", "τι", "ποιο", "ποια", "ποιος", "ποιες", "ποιοι", "ποιον", "ειναι", "να", "και", "η", "ο", "το", "οι",
    "τα", "της", "του", "των", "τον", "την", "τη", "σε", "στο", "στη", "στην", "στον", "στα", "στις", "στους",
    "με", "για", "απο", "ως", "μια", "ενα", "ενας", "μου", "σας", "μας", "αν", "δεν", "θα", "που", "ή", "η",
    "πιο", "οταν", "εχω", "εχει", "εχουμε", "μπορω", "μπορει", "κανω", "λειτουργει", "δουλευει", "οτι", "πει",
    "λεει", "αυτο", "αυτη", "αυτα", "ειμαστε", "εινα", "κατι", "ολα", "ποτε", "εδω",
)}
SUFFIXES = sorted(
    {fold(x) for x in ("ουμε", "ετε", "ουν", "ους", "εις", "ων", "ος", "ου", "οι", "ες", "ης", "ας", "ει",
                       "α", "η", "ο", "ι", "ε", "υ", "ς")},
    key=len, reverse=True,
)
WORD = re.compile(r"[\w-]+", re.UNICODE)


def stem(word: str) -> str:
    word = fold(word)
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def stems(text: str) -> list[str]:
    result = []
    for w in WORD.findall(text or ""):
        f = fold(w)
        if f in STOPWORDS or len(f) < 2:
            continue
        s = stem(w)
        if len(s) >= 3 and s not in result:
            result.append(s)
    return result


def _matches(query_stem: str, candidates) -> bool:
    for c in candidates:
        if c == query_stem:
            return True
        short, long = sorted((c, query_stem), key=len)
        if len(short) >= 4 and long.startswith(short):
            return True
    return False


@dataclass
class KnowledgeHit:
    entry: dict
    score: int
    sources: list


@dataclass
class DocumentHit:
    filename: str
    page: int
    snippet: str
    score: int


@dataclass
class KnowledgeAnswer:
    query: str
    best: KnowledgeHit | None = None
    related: list = field(default_factory=list)
    documents: list = field(default_factory=list)

    @property
    def found(self) -> bool:
        return self.best is not None or bool(self.documents)


class AdvisorKnowledgeBase:
    def __init__(self, content, documents_repo):
        self.content = content
        self.documents = documents_repo
        self.kb = content.knowledge
        self._index = [
            (e, stems(e["question"]), stems(" ".join(e.get("keywords", []))), stems(e["answer"]))
            for e in self.kb["entries"]
        ]

    def source_labels(self, entry) -> list[str]:
        labels = []
        for s in entry["sources"]:
            title = self.kb["sources"][s["source"]]["title"]
            labels.append(f"{title}, σ. {s['page']}" if s.get("page") else title)
        return labels

    def search(self, query: str, limit: int = 6) -> KnowledgeAnswer:
        terms = stems(query)
        answer = KnowledgeAnswer(query=query)
        if not terms:
            return answer
        hits = []
        for entry, q_stems, k_stems, a_stems in self._index:
            score = 0
            strong = 0
            for t in terms:
                if _matches(t, q_stems):
                    score, strong = score + 3, strong + 1
                elif _matches(t, k_stems):
                    score, strong = score + 2, strong + 1
                elif _matches(t, a_stems):
                    score += 1
            if strong or score >= 2:
                hits.append(KnowledgeHit(entry=entry, score=score, sources=self.source_labels(entry)))
        hits.sort(key=lambda h: -h.score)
        if hits:
            answer.best, answer.related = hits[0], hits[1:limit]
        answer.documents = self.search_documents(terms)
        return answer

    def search_documents(self, terms, limit: int = 5) -> list[DocumentHit]:
        hits = []
        for page in self.documents.pages_containing_any(terms):
            folded = fold(page.text)
            score = sum(folded.count(t) for t in terms)
            first = min((folded.find(t) for t in terms if t in folded), default=0)
            start = max(0, first - 160)
            snippet = " ".join(page.text[start:first + 240].split())
            hits.append(DocumentHit(page.filename, page.page, ("… " if start else "") + snippet + " …", score))
        hits.sort(key=lambda h: (-h.score, h.filename, h.page))
        return hits[:limit]

    def browse(self) -> list[tuple[dict, list]]:
        return [(kind, [e for e in self.kb["entries"] if e["kind"] == kind["id"]]) for kind in self.kb["kinds"]]

    def for_need(self, need_id) -> list[dict]:
        return [e for e in self.kb["entries"] if need_id in e.get("needs", [])]
