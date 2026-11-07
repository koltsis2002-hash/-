import json
import urllib.parse
import shutil
import threading
import urllib.error
import urllib.request

import pytest

from app.core.errors import ValidationError
from app.services.advisor.content import DATA_DIR, ContentError, default_content, load_content
from app.services.advisor.products import sha256_file
from app.ui.server import ThreadingHTTPServer, make_handler

NO_PRODUCT = "Προτεινόμενος τομέας διερεύνησης — απαιτείται επιβεβαίωση διαθέσιμης λύσης."


@pytest.fixture
def advisor(services, tmp_path):
    services.advisor.knowledge_dir = tmp_path / "knowledge"
    return services.advisor


def run(advisor, answers, prep=None, shared=(), interests=()):
    p = advisor.create("2026-11-07")
    if prep:
        advisor.save_preparation(p.id, prep, shared=list(shared), interests=list(interests))
    view = advisor.client_view(p.id)
    for qid, value in answers.items():
        status = value if value in ("unknown", "skipped") else "answered"
        view = advisor.record_answer(p.id, qid, status, None if status != "answered" else value)
    return p, view


def levels(view):
    return {n["id"]: n["level"] for n in view["needs"]}


def visible(view):
    return [q["id"] for q in view["flow"]["questions"]]


def test_content_is_valid_and_has_6_to_8_core_questions():
    c = default_content()
    assert 6 <= sum(q["core"] for q in c.questions) <= 8
    assert {q["axis"] for q in c.questions} == {a["id"] for a in c.axes}


def test_content_rejects_condition_on_later_question(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    q = json.loads((data / "questions.json").read_text("utf-8"))
    q["questions"][0]["show_if"] = {"q": "cyber.covered", "eq": "yes"}
    (data / "questions.json").write_text(json.dumps(q, ensure_ascii=False), "utf-8")
    with pytest.raises(ContentError):
        load_content(data)


def test_partner_branching(advisor):
    p, view = run(advisor, {"partners.has": "no"})
    assert "partners.agreement" not in visible(view) and levels(view)["partner_buyout"] == "not_priority"
    view = advisor.record_answer(p.id, "partners.has", "answered", "yes")
    assert "partners.agreement" in visible(view)
    view = advisor.record_answer(p.id, "partners.agreement", "answered", "no")
    assert levels(view)["partner_buyout"] == "confirmed"
    reason = next(n for n in advisor.assess(p.id).needs if n.id == "partner_buyout").reason
    assert "εξαγοράς" in reason
    view = advisor.record_answer(p.id, "partners.has", "answered", "no")
    assert "partners.agreement" not in view["flow"]["answers"]


SCENARIOS = {
    "sole_trader_no_staff": (
        {"ops.closure_costs": ["rent"], "ops.cover_period": "1to3", "key.dependency": "stop", "key.who": ["owner"],
         "key.replace_time": "gt12", "key.existing_cover": "no", "partners.has": "no", "succession.plan": "not_yet",
         "loans.has": "no", "staff.count": 0},
        {"key_person": "confirmed", "succession": "confirmed", "business_interruption": "confirmed",
         "group_health": "not_priority", "staff_retention": "not_priority", "partner_buyout": "not_priority"}),
    "twenty_employees": (
        {"staff.count": 20, "staff.benefits": ["none"], "staff.goals": ["retain", "health"], "staff.hiring": "hard"},
        {"group_health": "confirmed", "staff_retention": "confirmed", "group_pension": "possible"}),
    "existing_group_benefits": (
        {"staff.count": 15, "staff.benefits": ["health", "pension"], "staff.review": "no"},
        {"benefits_review": "confirmed", "group_health": "not_priority", "group_pension": "not_priority"}),
    "business_loans": (
        {"ops.closure_costs": ["loans", "payroll"], "loans.guarantees": "yes", "loans.repayment": "business"},
        {"loan_protection": "confirmed"}),
    "equipment_dependency": (
        {"property.assets": ["equipment"], "property.equipment_dependency": "weeks"},
        {"equipment_protection": "confirmed"}),
    "digital_dependency": (
        {"cyber.dependency": "critical", "cyber.data": ["customers", "payments"], "cyber.covered": "no"},
        {"cyber": "confirmed"}),
    "incomplete_data": ({"key.dependency": "harder"}, {"key_person": "possible", "liability": "info_needed"}),
    "client_skips": (
        {q: "skipped" for q in ("ops.closure_costs", "key.dependency", "partners.has", "loans.has", "staff.count",
                                "property.assets", "liability.exposure", "cyber.dependency")},
        {"key_person": "info_needed", "partner_buyout": "info_needed", "cyber": "info_needed"}),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_qa_scenarios(advisor, name):
    answers, expected = SCENARIOS[name]
    p, view = run(advisor, answers)
    got = levels(view)
    assert {k: got[k] for k in expected} == expected
    assert all(r["status_label"] == NO_PRODUCT for r in view["recommendations"])
    if name == "client_skips":
        assert view["flow"]["handled"] == view["flow"]["total"] and view["recommendations"] == []
    if name == "business_loans":
        assert "loans.has" not in visible(view)
    if name == "sole_trader_no_staff":
        assert "staff.benefits" not in visible(view)


def test_answer_validation(advisor):
    p = advisor.create("2026-11-07")
    for qid, value in [("partners.has", "maybe"), ("staff.count", -1), ("staff.count", "abc"),
                       ("ops.closure_costs", ["none", "rent"]), ("partners.agreement", "yes")]:
        with pytest.raises(ValidationError):
            advisor.record_answer(p.id, qid, "answered", value)


def test_session_persists_and_restores(db_path, tmp_path):
    from app.services.context import Services
    with Services.open(db_path, knowledge_dir=tmp_path) as s:
        p = s.advisor.create("2026-11-07")
        s.advisor.record_answer(p.id, "partners.has", "answered", "yes")
        s.advisor.set_position(p.id, 6, "partners.agreement")
    with Services.open(db_path, knowledge_dir=tmp_path) as s:
        view = s.advisor.client_view(p.id)
        assert view["position"] == {"screen": 6, "question": "partners.agreement"}
        assert view["flow"]["answers"]["partners.has"]["value"] == "yes"


def test_client_view_never_contains_private_data(advisor):
    p = advisor.create("2026-11-07")
    advisor.save_preparation(p.id, {"business_name": "Αλφα ΟΕ", "financial_obligations": "ΔΑΝΕΙΟ-ΚΡΥΦΟ",
                                    "owner_name": "ΟΝΟΜΑ-ΚΡΥΦΟ"}, shared=["business_name"], interests=[])
    advisor.save_internal_notes(p.id, "ΣΗΜΕΙΩΣΗ-ΚΡΥΦΗ")
    advisor.record_answer(p.id, "partners.has", "answered", "yes")
    payload = json.dumps(advisor.client_view(p.id), ensure_ascii=False)
    assert "Αλφα ΟΕ" in payload
    for secret in ("ΔΑΝΕΙΟ-ΚΡΥΦΟ", "ΟΝΟΜΑ-ΚΡΥΦΟ", "ΣΗΜΕΙΩΣΗ-ΚΡΥΦΗ", "reason", "show_if", "Αιτιολόγηση"):
        assert secret not in payload


def test_summary_edit_approval_cycle(advisor):
    p, _ = run(advisor, {"partners.has": "yes", "partners.agreement": "no"},
               prep={"business_name": "Βήτα ΙΚΕ"}, shared=["business_name"])
    s = advisor.summary(p.id)
    assert s.content["business_name"] == "Βήτα ΙΚΕ" and s.content["directions"] and not s.approved_at
    assert advisor.approve_summary(p.id).approved_at
    edited = advisor.save_summary(p.id, {**s.content, "priorities": "Πρώτη\n\nΔεύτερη"})
    assert edited.edited and edited.approved_at is None and edited.content["priorities"] == ["Πρώτη", "Δεύτερη"]


def test_verified_product_is_used_and_changed_document_is_rejected(advisor):
    products = advisor.knowledge_dir / "products"
    products.mkdir(parents=True)
    pdf = products / "oroi.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    catalog = {"products": [{
        "id": "kp", "name": "Πρόγραμμα Δοκιμής", "provider": "Δοκιμή", "categories": ["key_person"],
        "document": {"file": "oroi.pdf", "sha256": sha256_file(pdf)}, "benefits": [{"text": "Παροχή", "page": 2}],
        "verified_by": "Χ.Κ.", "verified_on": "2026-11-07"}]}
    (products / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), "utf-8")
    p, view = run(advisor, {"key.dependency": "stop", "key.existing_cover": "no"})
    rec = next(r for r in view["recommendations"] if r["need_id"] == "key_person")
    assert rec["products"][0]["benefits"][0]["source"] == "oroi.pdf, σ. 2"
    pdf.write_bytes(b"%PDF-1.4 changed")
    rec = next(r for r in advisor.client_view(p.id)["recommendations"] if r["need_id"] == "key_person")
    assert rec["products"] == [] and rec["status_label"] == NO_PRODUCT
    assert "SHA-256" in advisor.catalog().issues[0].problems[0]


def test_knowledge_search_with_sources_and_refusal(advisor):
    r = advisor.search_knowledge("Πώς λειτουργεί η προστασία συνεταίρων;")
    assert r.best.entry["id"] == "faq-partners" and "σ. 2" in r.best.sources[0]
    assert not advisor.search_knowledge("xyz άσχετο").found


def test_document_index_reindexes_only_changed_files(advisor):
    from app.services.advisor.documents import index_documents
    products = advisor.knowledge_dir / "products"
    products.mkdir(parents=True)
    (products / "a.pdf").write_bytes(b"one")
    pages = lambda path: ["Εξαιρέσεις: δεν καλύπτεται η ΠΡΟΫΠΆΡΧΟΥΣΑ πάθηση.", "Δεύτερη σελίδα"]  # noqa: E731
    assert index_documents(products, advisor.documents, pages).indexed == ["a.pdf"]
    assert index_documents(products, advisor.documents, pages).unchanged == ["a.pdf"]
    hits = advisor.search_knowledge("προϋπάρχουσα").documents
    assert (hits[0].filename, hits[0].page) == ("a.pdf", 1)


def test_pdf_text_extraction():
    pypdf = pytest.importorskip("pypdf")
    from app.services.advisor.documents import extract_pages
    import io
    writer = pypdf.PdfWriter()
    writer.add_blank_page(100, 100)
    buf = io.BytesIO()
    writer.write(buf)
    path = DATA_DIR.parent / "_tmp_test.pdf"
    try:
        path.write_bytes(buf.getvalue())
        assert extract_pages(path) == [""]
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture
def base_url(db_path, tmp_path, conn):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db_path, knowledge_dir=tmp_path / "knowledge"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http(url, data=None, headers=None, json_body=None):
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers = {"Content-Type": "application/json", **(headers or {})}
    elif isinstance(data, dict):
        data = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.build_opener(NoRedirect).open(req) as r:
            return r.status, r.headers, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode("utf-8", "replace")


def test_http_end_to_end(base_url):
    status, _, html = http(base_url + "/")
    assert status == 200 and "Business Advisor | Επιχειρήσεις" in html
    status, headers, _ = http(base_url + "/advisor/new", {"meeting_date": "2026-11-07", "contact_id": ""})
    assert status == 303
    pid = headers["Location"].split("/")[3].split("?")[0]
    status, _, _ = http(f"{base_url}/advisor/p/{pid}/prep", {
        "meeting_date": "2026-11-07", "business_name": "Γάμμα <b>ΑΕ</b>", "financial_obligations": "ΚΡΥΦΟ-ΔΑΝΕΙΟ",
        "share": ["business_name"], "interest": ["partners"], "internal_notes": "ΚΡΥΦΗ-ΣΗΜΕΙΩΣΗ"})
    assert status == 303
    status, headers, html = http(f"{base_url}/advisor/p/{pid}")
    assert status == 200 and "ΚΡΥΦΗ-ΣΗΜΕΙΩΣΗ" in html and "Γάμμα &lt;b&gt;" in html
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]

    status, _, page = http(f"{base_url}/present/{pid}")
    status_api, _, api = http(f"{base_url}/api/present/{pid}")
    assert status == status_api == 200
    for secret in ("ΚΡΥΦΗ-ΣΗΜΕΙΩΣΗ", "ΚΡΥΦΟ-ΔΑΝΕΙΟ"):
        assert secret not in page and secret not in api
    status, _, body = http(f"{base_url}/api/present/{pid}/answer",
                           json_body={"question": "partners.has", "status": "answered", "value": "yes"})
    assert status == 200 and "partners.agreement" in body
    assert http(f"{base_url}/api/present/{pid}/answer", data=b"{}")[0] == 415
    assert http(f"{base_url}/api/present/{pid}/answer", json_body={"question": "x", "status": "answered"})[0] == 400
    assert http(f"{base_url}/api/present/{pid}/answer", json_body={},
                headers={"Origin": "http://evil.example"})[0] == 403
    assert http(f"{base_url}/advisor", headers={"Host": "evil.example"})[0] == 403

    status, _, html = http(f"{base_url}/advisor/p/{pid}/summary/print")
    assert "Απαιτείται έγκριση" in html
    assert http(f"{base_url}/advisor/p/{pid}/summary/approve", {})[0] == 303
    status, _, html = http(f"{base_url}/advisor/p/{pid}/summary/print")
    assert "print.js" in html and "Γάμμα &lt;b&gt;ΑΕ&lt;/b&gt;" in html

    assert http(base_url + "/static/advisor/present.js")[0] == 200
    assert http(base_url + "/static/advisor/..%2F..%2Fserver.py")[0] == 404
    assert http(base_url + "/advisor/knowledge?q=" + urllib.parse.quote("συνεταίρων"))[0] == 200
    assert http(base_url + "/advisor/products")[0] == 200

    assert http(f"{base_url}/advisor/p/{pid}/delete", {"confirm": "yes"})[0] == 303
    assert http(f"{base_url}/api/present/{pid}")[0] == 404
