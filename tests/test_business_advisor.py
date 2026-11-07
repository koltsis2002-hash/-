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


def run(advisor, answers, prep=None, shared=(), topics=None):
    p = advisor.create("2026-11-07")
    if prep:
        advisor.save_preparation(p.id, prep, shared=list(shared), interests=[])
    if topics:
        advisor.set_topics(p.id, topics)
    view = advisor.client_view(p.id)
    for qid, value in answers.items():
        status = value if value in ("unknown", "skipped") else "answered"
        view = advisor.record_answer(p.id, qid, status, None if status != "answered" else value)
    return p, view


def levels(view):
    return {n["id"]: n["level"] for n in view["needs"]}


def visible(view):
    return [q["id"] for q in view["flow"]["questions"]]


def test_content_is_valid_with_few_targeted_questions():
    c = default_content()
    assert c.default_topics == ["life", "health", "group", "savings"]
    assert sum(q["core"] for q in c.questions if q["axis"] in c.default_topics) <= 8


def test_default_categories_ask_at_most_ten_questions_in_priority_order(advisor):
    p, view = run(advisor, {"life.partners": "yes", "group.staff": 12, "savings.goal": ["owner"]})
    assert view["topics"] == ["life", "health", "group", "savings"]
    assert len(visible(view)) <= 10
    assert [q["axis"] for q in view["flow"]["questions"]] == sorted(
        (q["axis"] for q in view["flow"]["questions"]), key=view["topics"].index)
    assert not any(q.startswith(("loans.", "property.", "risk.")) for q in visible(view))
    assert {n["axis"] for n in view["needs"]} <= set(view["topics"])


def test_choosing_categories(advisor):
    p, view = run(advisor, {"life.cover": "no"})
    view = advisor.set_topics(p.id, ["risk", "life"])
    assert view["topics"] == ["life", "risk"] and visible(view)[0].startswith("life.")
    assert "health.private" not in visible(view) and "risk.exposure" in visible(view)
    assert view["flow"]["answers"]["life.cover"]["status"] == "answered"
    assert advisor.set_topics(p.id, [])["topics"] == ["life", "health", "group", "savings"]
    with pytest.raises(ValidationError):
        advisor.set_topics(p.id, ["nope"])


def test_content_rejects_condition_on_later_question(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    q = json.loads((data / "questions.json").read_text("utf-8"))
    q["questions"][0]["show_if"] = {"q": "risk.covered", "eq": "yes"}
    (data / "questions.json").write_text(json.dumps(q, ensure_ascii=False), "utf-8")
    with pytest.raises(ContentError):
        load_content(data)


def test_partner_branching(advisor):
    p, view = run(advisor, {"life.partners": "no"})
    assert "life.partner_plan" not in visible(view) and "partner_buyout" not in levels(view)
    view = advisor.record_answer(p.id, "life.partners", "answered", "yes")
    assert "life.partner_plan" in visible(view)
    view = advisor.record_answer(p.id, "life.partner_plan", "answered", "no")
    assert levels(view)["partner_buyout"] == "confirmed"
    reason = next(n for n in advisor.assess(p.id).needs if n.id == "partner_buyout").reason
    assert "εξαγοράς" in reason
    view = advisor.record_answer(p.id, "life.partners", "answered", "no")
    assert "life.partner_plan" not in view["flow"]["answers"]


SCENARIOS = {
    "sole_trader_no_staff": (
        {"life.partners": "no", "life.cover": "no", "health.private": "basic", "health.income": "no", "group.staff": 0},
        {"owner_life": "confirmed", "owner_health": "possible", "income_protection": "confirmed",
         "group_health": "not_priority", "group_pension": "not_priority"}, None),
    "two_partners": (
        {"life.partners": "yes", "life.partner_plan": "no", "life.cover": "small"},
        {"partner_buyout": "confirmed", "owner_life": "possible"}, None),
    "twenty_employees": (
        {"group.staff": 20, "group.current": ["none"], "group.goal": "retain"},
        {"group_health": "confirmed", "group_pension": "confirmed"}, None),
    "existing_group_benefits": (
        {"group.staff": 15, "group.current": ["health", "pension"], "group.goal": "retain"},
        {"group_health": "not_priority", "group_pension": "not_priority"}, None),
    "business_loans": (
        {"loans.has": "yes", "loans.covered": "no"}, {"loan_protection": "confirmed"}, ["loans"]),
    "equipment_dependency": (
        {"property.assets": ["equipment"], "property.insured": "no"}, {"property_protection": "confirmed"}, ["property"]),
    "digital_dependency": (
        {"risk.exposure": ["data", "critical_it"], "risk.covered": ["none"]}, {"cyber": "confirmed"}, ["risk"]),
    "savings_for_business_and_owner": (
        {"savings.goal": ["business", "owner"], "savings.horizon": "5to10"},
        {"business_savings": "confirmed", "owner_savings": "confirmed"}, None),
    "incomplete_data": ({"life.cover": "no"}, {"owner_life": "confirmed", "owner_health": "info_needed"}, None),
    "client_skips": (
        {q: "skipped" for q in ("life.partners", "life.cover", "health.private", "health.income", "group.staff",
                                "savings.goal")},
        {"owner_life": "info_needed", "owner_health": "info_needed", "business_savings": "info_needed"}, None),
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_qa_scenarios(advisor, name):
    answers, expected, topics = SCENARIOS[name]
    p, view = run(advisor, answers, topics=topics)
    got = levels(view)
    assert {k: got[k] for k in expected} == expected
    assert all(r["status_label"] == NO_PRODUCT for r in view["recommendations"])
    if name == "client_skips":
        assert view["flow"]["handled"] == view["flow"]["total"] and view["recommendations"] == []
    if name == "sole_trader_no_staff":
        assert "group.current" not in visible(view) and "partner_buyout" not in got
        assert [r["need_id"] for r in view["recommendations"]] == ["owner_life", "income_protection", "owner_health"]


def test_owner_without_partners_sees_texts_only_for_themselves(advisor):
    p, view = run(advisor, {"life.partners": "no", "life.cover": "no", "health.private": "no"})
    payload = json.dumps(view, ensure_ascii=False)
    titles = {a["id"]: a["title"] for a in view["axes"]}
    assert titles["life"] == "Ζωή επιχειρηματία" and titles["health"] == "Υγεία επιχειρηματία"
    assert "συνεταίρ" not in json.dumps([view["needs"], view["recommendations"], view["matches"],
                                         view["summary"]["content"]], ensure_ascii=False)
    assert len(view["content"]["categories"]["life"]) == 1
    texts = {q["id"]: q["text"] for q in view["flow"]["questions"]}
    assert texts["health.private"] == "Έχετε ιδιωτική ασφάλεια υγείας;"
    assert "_solo" not in payload and "partners_only" not in payload and "hide_when_solo" not in payload


def test_partner_wording_follows_preparation_until_answered(advisor):
    p = advisor.create("2026-11-07")
    advisor.save_preparation(p.id, {"partners": "0"}, shared=[], interests=[])
    assert {a["id"]: a["title"] for a in advisor.client_view(p.id)["axes"]}["life"] == "Ζωή επιχειρηματία"
    view = advisor.record_answer(p.id, "life.partners", "answered", "yes")
    assert {a["id"]: a["title"] for a in view["axes"]}["life"] == "Ζωή επιχειρηματία & συνεταίρων"
    assert len(view["content"]["categories"]["life"]) == 2


def test_solution_matches_list_every_priority_need(advisor):
    p, view = run(advisor, {"life.partners": "yes", "life.partner_plan": "no", "life.cover": "no",
                            "health.private": "no", "health.income": "no"})
    matches = view["matches"]
    assert [m["need_id"] for m in matches] == [r.need.id for r in advisor.assess(p.id).recommendations]
    assert len(matches) == 4 and [m["detail"] for m in matches] == [0, 1, 2, None]
    assert all(m["solutions"] and m["solutions"][0]["documented"] is False for m in matches)


def test_answer_validation(advisor):
    p = advisor.create("2026-11-07")
    for qid, value in [("life.partners", "maybe"), ("group.staff", -1), ("group.staff", "abc"),
                       ("savings.goal", ["none", "owner"]), ("life.partner_plan", "yes"), ("risk.exposure", ["data"])]:
        with pytest.raises(ValidationError):
            advisor.record_answer(p.id, qid, "answered", value)


def test_session_persists_and_restores(db_path, tmp_path):
    from app.services.context import Services
    with Services.open(db_path, knowledge_dir=tmp_path) as s:
        p = s.advisor.create("2026-11-07")
        s.advisor.record_answer(p.id, "life.partners", "answered", "yes")
        s.advisor.set_position(p.id, 6, "life.partner_plan")
    with Services.open(db_path, knowledge_dir=tmp_path) as s:
        view = s.advisor.client_view(p.id)
        assert view["position"] == {"screen": 6, "question": "life.partner_plan"}
        assert view["flow"]["answers"]["life.partners"]["value"] == "yes"


def test_position_accepts_slide_markers(advisor):
    p = advisor.create("2026-11-07")
    advisor.set_position(p.id, 3, "slide:2")
    assert advisor.client_view(p.id)["position"] == {"screen": 3, "question": "slide:2"}
    for bad in ("slide:x", "<script>", "slide:123"):
        with pytest.raises(ValidationError):
            advisor.set_position(p.id, 3, bad)


def test_every_category_has_a_slide_and_a_choice():
    c = default_content()
    for axis in c.axes:
        assert c.presentation["categories"][axis["id"]] and axis["id"] in c.presentation["interests"]["items"]


def test_client_view_never_contains_private_data(advisor):
    p = advisor.create("2026-11-07")
    advisor.save_preparation(p.id, {"business_name": "Αλφα ΟΕ", "financial_obligations": "ΔΑΝΕΙΟ-ΚΡΥΦΟ",
                                    "owner_name": "ΟΝΟΜΑ-ΚΡΥΦΟ"}, shared=["business_name"], interests=[])
    advisor.save_internal_notes(p.id, "ΣΗΜΕΙΩΣΗ-ΚΡΥΦΗ")
    advisor.record_answer(p.id, "life.partners", "answered", "yes")
    payload = json.dumps(advisor.client_view(p.id), ensure_ascii=False)
    assert "Αλφα ΟΕ" in payload
    for secret in ("ΔΑΝΕΙΟ-ΚΡΥΦΟ", "ΟΝΟΜΑ-ΚΡΥΦΟ", "ΣΗΜΕΙΩΣΗ-ΚΡΥΦΗ", "reason", "show_if", "Αιτιολόγηση"):
        assert secret not in payload


def test_summary_edit_approval_cycle(advisor):
    p, _ = run(advisor, {"life.partners": "yes", "life.partner_plan": "no"},
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
        "id": "kp", "name": "Πρόγραμμα Δοκιμής", "provider": "Δοκιμή", "categories": ["owner_life"],
        "document": {"file": "oroi.pdf", "sha256": sha256_file(pdf)}, "benefits": [{"text": "Παροχή", "page": 2}],
        "verified_by": "Χ.Κ.", "verified_on": "2026-11-07"}]}
    (products / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), "utf-8")
    p, view = run(advisor, {"life.cover": "no"})
    rec = next(r for r in view["recommendations"] if r["need_id"] == "owner_life")
    assert rec["products"][0]["benefits"][0]["source"] == "oroi.pdf, σ. 2"
    pdf.write_bytes(b"%PDF-1.4 changed")
    rec = next(r for r in advisor.client_view(p.id)["recommendations"] if r["need_id"] == "owner_life")
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
        "share": ["business_name"], "interest": ["life", "health"], "internal_notes": "ΚΡΥΦΗ-ΣΗΜΕΙΩΣΗ"})
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
                           json_body={"question": "life.partners", "status": "answered", "value": "yes"})
    assert status == 200 and "life.partner_plan" in body and "group.staff" not in body
    status, _, body = http(f"{base_url}/api/present/{pid}/topics", json_body={"topics": ["life", "group"]})
    assert status == 200 and "group.staff" in body
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
