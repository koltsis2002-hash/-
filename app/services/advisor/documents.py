"""Page-by-page text index of the official PDFs in knowledge/products/. Re-indexes only changed files."""
from dataclasses import dataclass, field

from app.core.errors import JarvisError
from app.services.advisor.products import product_pdfs, sha256_file


class DocumentIndexUnavailable(JarvisError):
    pass


def extract_pages(path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentIndexUnavailable(
            "Η ευρετηρίαση PDF χρειάζεται το προαιρετικό πακέτο pypdf: pip install pypdf"
        ) from exc
    return [(page.extract_text() or "").strip() for page in PdfReader(str(path)).pages]


@dataclass
class IndexReport:
    indexed: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def index_documents(products_dir, repo, extract=extract_pages) -> IndexReport:
    report = IndexReport()
    existing = {d.filename: d for d in repo.list_all()}
    files = product_pdfs(products_dir)
    for path in files:
        digest = sha256_file(path)
        if path.name in existing and existing[path.name].sha256 == digest:
            report.unchanged.append(path.name)
            continue
        try:
            pages = extract(path)
        except DocumentIndexUnavailable:
            raise
        except Exception as exc:  # a damaged or encrypted PDF must not stop the other files
            report.errors.append((path.name, str(exc) or exc.__class__.__name__))
            continue
        repo.replace(path.name, digest, pages)
        report.indexed.append(path.name)
    for name in set(existing) - {p.name for p in files}:
        repo.delete(name)
        report.removed.append(name)
    return report
