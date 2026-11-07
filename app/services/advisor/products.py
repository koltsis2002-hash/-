"""Product catalog. A product is offered only when every claim points to a page of an official document
in knowledge/products/ whose SHA-256 matches the one recorded when the advisor verified it."""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

CATALOG_FILE = "catalog.json"


@dataclass
class DocumentedClaim:
    text: str
    page: int
    filename: str

    @property
    def source(self) -> str:
        return f"{self.filename}, σ. {self.page}"


@dataclass
class VerifiedProduct:
    id: str
    name: str
    provider: str
    categories: list
    summary: str
    filename: str
    version: str
    benefits: list
    limitations: list
    verified_by: str
    verified_on: str


@dataclass
class CatalogIssue:
    product: str
    problems: list


@dataclass
class ProductFile:
    filename: str
    sha256: str


@dataclass
class Catalog:
    found: bool
    products: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    files: list = field(default_factory=list)

    def for_category(self, category) -> list[VerifiedProduct]:
        return [p for p in self.products if category in p.categories]


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def product_pdfs(products_dir: Path) -> list[Path]:
    if not products_dir.is_dir():
        return []
    return sorted(p for p in products_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def _claims(raw, filename, label, problems, page_count, required):
    claims = []
    if not isinstance(raw, list) or (required and not raw):
        problems.append(f"Χρειάζεται λίστα «{label}» με κείμενο και σελίδα πηγής")
        return claims
    for item in raw:
        text, page = (item or {}).get("text"), (item or {}).get("page")
        if not text or not isinstance(page, int) or page < 1:
            problems.append(f"«{label}»: κάθε στοιχείο χρειάζεται κείμενο και αριθμό σελίδας")
            continue
        if page_count is not None and page > page_count:
            problems.append(f"«{label}»: η σελίδα {page} δεν υπάρχει (το έγγραφο έχει {page_count})")
            continue
        claims.append(DocumentedClaim(text=text, page=page, filename=filename))
    return claims


def load_catalog(knowledge_dir, known_categories, page_counts=None) -> Catalog:
    products_dir = Path(knowledge_dir) / "products"
    files = {p.name: sha256_file(p) for p in product_pdfs(products_dir)}
    catalog = Catalog(found=(products_dir / CATALOG_FILE).is_file(),
                      files=[ProductFile(n, h) for n, h in files.items()])
    if not catalog.found:
        return catalog
    try:
        data = json.loads((products_dir / CATALOG_FILE).read_text("utf-8"))
        entries = data["products"]
        if not isinstance(entries, list):
            raise TypeError("products is not a list")
    except (ValueError, KeyError, TypeError) as exc:
        catalog.issues.append(CatalogIssue(CATALOG_FILE, [f"Μη έγκυρο αρχείο καταλόγου: {exc}"]))
        return catalog

    page_counts = page_counts or {}
    for raw in entries:
        raw = raw if isinstance(raw, dict) else {}
        name = raw.get("name") or raw.get("id") or "(χωρίς όνομα)"
        problems = []
        if not raw.get("id") or not raw.get("name"):
            problems.append("Λείπει id ή όνομα")
        categories = raw.get("categories") or []
        if not categories or not set(categories) <= set(known_categories):
            problems.append(f"Οι κατηγορίες πρέπει να είναι μία ή περισσότερες από: {', '.join(sorted(known_categories))}")
        document = raw.get("document") or {}
        filename = document.get("file") or ""
        if not filename or Path(filename).name != filename:
            problems.append("Το document.file πρέπει να είναι όνομα αρχείου μέσα στο knowledge/products/")
        elif filename not in files:
            problems.append(f"Το έγγραφο {filename} δεν βρέθηκε στο knowledge/products/")
        elif document.get("sha256") != files[filename]:
            problems.append(f"Το SHA-256 του {filename} δεν ταιριάζει: το έγγραφο άλλαξε ή δεν έχει επαληθευτεί")
        if not raw.get("verified_by") or not raw.get("verified_on"):
            problems.append("Λείπει ποιος και πότε επαλήθευσε το προϊόν (verified_by, verified_on)")
        page_count = page_counts.get(filename)
        benefits = _claims(raw.get("benefits"), filename, "benefits", problems, page_count, required=True)
        limitations = _claims(raw.get("limitations", []), filename, "limitations", problems, page_count, required=False)
        if problems:
            catalog.issues.append(CatalogIssue(name, problems))
            continue
        catalog.products.append(VerifiedProduct(
            id=raw["id"], name=raw["name"], provider=raw.get("provider", ""), categories=list(categories),
            summary=raw.get("summary", ""), filename=filename, version=document.get("version", ""),
            benefits=benefits, limitations=limitations, verified_by=raw["verified_by"],
            verified_on=raw["verified_on"],
        ))
    return catalog
