"""Business Advisor | Επιχειρήσεις.

Two isolated surfaces:
- /advisor/...      advisor workspace (preparation, internal notes, needs reasoning, knowledge base, products)
- /present/<id>     client presentation, a separate page that only reads /api/present/<id>, whose payload is
                    built by BusinessAdvisorService.client_view from an allow-list.
"""
import ipaddress
import json
import re
from dataclasses import dataclass, field
from datetime import date
from html import escape
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, quote

from app.core.errors import NotFoundError, ValidationError
from app.services.advisor.documents import DocumentIndexUnavailable
from app.services.advisor.service import FIELD_LABELS, STATUS_LABELS
from app.services.context import Services

PREFIXES = ("advisor", "present", "api", "static")
STATIC_DIR = Path(__file__).parent / "static" / "advisor"
STATIC_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*\.(css|js|png|woff2|txt)$")
STATIC_TYPES = {
    ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".png": "image/png",
    ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8",
}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
MAX_BODY = 256 * 1024
MONTHS = ("Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου", "Αυγούστου",
          "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου")
LEGAL_FORMS = ("Ατομική επιχείρηση", "ΟΕ", "ΕΕ", "ΙΚΕ", "ΕΠΕ", "ΑΕ", "Μονοπρόσωπη ΙΚΕ")
SENSITIVE_FIELDS = ("existing_coverage", "financial_obligations")
NOTICES = {
    "saved": "Η προετοιμασία αποθηκεύτηκε.",
    "created": "Η νέα παρουσίαση δημιουργήθηκε.",
    "deleted": "Τα δεδομένα της συνάντησης διαγράφηκαν οριστικά.",
    "summary-saved": "Οι αλλαγές στην περίληψη αποθηκεύτηκαν. Χρειάζεται νέα έγκριση πριν από την εξαγωγή.",
    "summary-regenerated": "Η περίληψη δημιουργήθηκε ξανά από τις απαντήσεις.",
    "approved": "Η περίληψη εγκρίθηκε για εξαγωγή.",
    "next": "Δημιουργήθηκε νέα συνάντηση με βάση την προηγούμενη.",
}
LEVEL_CLASS = {"confirmed": "lv-confirmed", "possible": "lv-possible", "info_needed": "lv-info",
               "not_priority": "lv-none"}


@dataclass
class Request:
    method: str
    parts: list
    query: dict
    headers: dict
    body: bytes = b""


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "text/html; charset=utf-8"
    headers: dict = field(default_factory=dict)


def e(value) -> str:
    return "" if value is None else escape(str(value))


def greek_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return e(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def html_response(html: str, status=HTTPStatus.OK) -> Response:
    return Response(int(status), html.encode("utf-8"))


def json_response(data, status=HTTPStatus.OK) -> Response:
    return Response(int(status), json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")


def redirect(location: str) -> Response:
    return Response(int(HTTPStatus.SEE_OTHER), b"", "text/plain; charset=utf-8", {"Location": location})


def trusted_host(host_header: str) -> bool:
    """Blocks DNS-rebinding: only localhost or a literal IP address may address the app."""
    host = (host_header or "").strip()
    if host.startswith("["):
        hostname = host[1:host.find("]")] if "]" in host else ""
    else:
        hostname = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    if hostname == "localhost":
        return True
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def handle(request: Request, db_path, knowledge_dir=None, today=date.today) -> Response:
    response = _handle(request, db_path, knowledge_dir, today)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.parts[0] != "static":
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("X-Frame-Options", "DENY")
    return response


def _handle(request, db_path, knowledge_dir, today) -> Response:
    if not trusted_host(request.headers.get("host", "")):
        return Response(403, b"Forbidden", "text/plain; charset=utf-8")
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin is not None and origin != f"http://{request.headers.get('host', '')}":
            return Response(403, b"Cross-origin request refused", "text/plain; charset=utf-8")
        if len(request.body) > MAX_BODY:
            return Response(413, b"Too large", "text/plain; charset=utf-8")
    if request.parts[0] == "static":
        return _static(request)
    is_api = request.parts[0] == "api"
    with Services.open(db_path, knowledge_dir=knowledge_dir) as services:
        try:
            return _route(request, services.advisor, today)
        except NotFoundError:
            if is_api:
                return json_response({"error": "Δεν βρέθηκε"}, HTTPStatus.NOT_FOUND)
            return html_response(shell("Δεν βρέθηκε", "<h1>Δεν βρέθηκε</h1><p><a href='/advisor'>Επιστροφή</a></p>"),
                                 HTTPStatus.NOT_FOUND)
        except ValidationError as exc:
            if is_api:
                return json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return html_response(shell("Έλεγχος στοιχείων", (
                f"<div class='banner error'><b>Δεν έγινε αποθήκευση.</b> {e(exc)}</div>"
                "<p><a class='btn' href='javascript:history.back()'>Επιστροφή στη φόρμα</a></p>"
            )), HTTPStatus.BAD_REQUEST)


def _static(request) -> Response:
    parts = request.parts
    name = parts[2] if len(parts) == 3 and parts[1] == "advisor" else ""
    path = STATIC_DIR / name
    if request.method != "GET" or not STATIC_NAME.match(name) or not path.is_file():
        return Response(404, b"Not found", "text/plain; charset=utf-8")
    return Response(200, path.read_bytes(), STATIC_TYPES[path.suffix], {"Cache-Control": "no-cache"})


def _form(request) -> dict:
    return parse_qs(request.body.decode("utf-8", errors="replace"), keep_blank_values=True)


def _first(form, name, default="") -> str:
    return form.get(name, [default])[0]


def _route(req, advisor, today) -> Response:
    p, m = req.parts, req.method
    if p[0] == "present" and len(p) == 2 and p[1].isdigit() and m == "GET":
        advisor.get(int(p[1]))
        return html_response(present_page(int(p[1])))
    if p[0] == "api":
        return _api(req, advisor)
    if p[0] != "advisor":
        raise NotFoundError("unknown route")
    notice = NOTICES.get(_first(req.query, "ok"))

    if p == ["advisor"] and m == "GET":
        return html_response(render_index(advisor, today, notice))
    if p == ["advisor", "new"] and m == "POST":
        form = _form(req)
        contact = _first(form, "contact_id")
        presentation = advisor.create(_first(form, "meeting_date") or None,
                                      contact_id=int(contact) if contact.isdigit() else None)
        return redirect(f"/advisor/p/{presentation.id}?ok=created")
    if p == ["advisor", "knowledge"] and m == "GET":
        return html_response(render_knowledge(advisor, _first(req.query, "q").strip()))
    if p == ["advisor", "products"] and m == "GET":
        return html_response(render_products(advisor, req.query))
    if p == ["advisor", "products", "index"] and m == "POST":
        try:
            report = advisor.index_documents()
        except DocumentIndexUnavailable as exc:
            return redirect("/advisor/products?unavailable=1&msg=" + quote(str(exc)[:200]))
        return redirect(f"/advisor/products?indexed={len(report.indexed)}&unchanged={len(report.unchanged)}"
                        f"&removed={len(report.removed)}&errors={len(report.errors)}")

    if len(p) >= 3 and p[:2] == ["advisor", "p"] and p[2].isdigit():
        pid, rest = int(p[2]), p[3:]
        if rest == [] and m == "GET":
            return html_response(render_workspace(advisor, pid, notice))
        if rest == ["prep"] and m == "POST":
            form = _form(req)
            advisor.get(pid)
            if _first(form, "meeting_date"):
                advisor.set_meeting_date(pid, _first(form, "meeting_date"))
            advisor.save_preparation(pid, {f: _first(form, f) for f in FIELD_LABELS},
                                     shared=form.get("share", []), interests=form.get("interest", []))
            advisor.save_internal_notes(pid, _first(form, "internal_notes"))
            return redirect(f"/advisor/p/{pid}?ok=saved")
        if rest == ["delete"] and m == "POST":
            if _first(_form(req), "confirm") != "yes":
                raise ValidationError("Επιβεβαιώστε τη διαγραφή επιλέγοντας το σχετικό πεδίο.")
            advisor.delete(pid)
            return redirect("/advisor?ok=deleted")
        if rest == ["next-meeting"] and m == "POST":
            new = advisor.create(_first(_form(req), "meeting_date") or today().isoformat(), previous_id=pid)
            return redirect(f"/advisor/p/{new.id}?ok=next")
        if rest == ["summary"] and m == "GET":
            return html_response(render_summary_editor(advisor, pid, notice))
        if rest == ["summary"] and m == "POST":
            form = _form(req)
            directions = [{k: _first(form, f"dir{i}_{k}") for k in ("title", "need", "why", "solution")}
                          for i in range(3)]
            advisor.save_summary(pid, {
                "business_name": _first(form, "business_name"), "meeting_date": _first(form, "meeting_date"),
                "topics": _first(form, "topics"), "priorities": _first(form, "priorities"),
                "directions": directions, "information_needed": _first(form, "information_needed"),
                "next_steps": _first(form, "next_steps"),
            })
            return redirect(f"/advisor/p/{pid}/summary?ok=summary-saved")
        if rest == ["summary", "regenerate"] and m == "POST":
            advisor.regenerate_summary(pid)
            return redirect(f"/advisor/p/{pid}/summary?ok=summary-regenerated")
        if rest == ["summary", "approve"] and m == "POST":
            advisor.approve_summary(pid)
            return redirect(f"/advisor/p/{pid}/summary?ok=approved")
        if rest == ["summary", "print"] and m == "GET":
            return html_response(render_print(advisor, pid))
    raise NotFoundError("unknown route")


def _api(req, advisor) -> Response:
    p = req.parts
    if len(p) < 3 or p[1] != "present" or not p[2].isdigit():
        raise NotFoundError("unknown api route")
    pid, action = int(p[2]), p[3:]
    if req.method == "GET" and action == []:
        return json_response(advisor.client_view(pid))
    if req.method != "POST" or len(action) != 1:
        raise NotFoundError("unknown api route")
    if not req.headers.get("content-type", "").startswith("application/json"):
        return json_response({"error": "Απαιτείται JSON"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
    try:
        data = json.loads(req.body or b"{}")
    except ValueError as exc:
        raise ValidationError("Μη έγκυρο JSON") from exc
    if not isinstance(data, dict):
        raise ValidationError("Μη έγκυρο αίτημα")
    if action == ["answer"]:
        return json_response(advisor.record_answer(pid, data.get("question"), data.get("status"),
                                                   data.get("value"), data.get("note")))
    if action == ["topics"]:
        return json_response(advisor.set_topics(pid, data.get("topics")))
    if action == ["clear"]:
        return json_response(advisor.clear_answer(pid, data.get("question")))
    if action == ["position"]:
        advisor.set_position(pid, data.get("screen"), data.get("question"))
        return json_response({"ok": True})
    if action == ["approve"]:
        summary = advisor.approve_summary(pid)
        return json_response({"approved": summary.approved_at is not None})
    raise NotFoundError("unknown api route")


# ----- HTML ---------------------------------------------------------------------------------------

def shell(title: str, body: str, extra_head: str = "") -> str:
    return (
        "<!doctype html><html lang='el'><head><meta charset='utf-8'>"
        f"<title>{e(title)} · JARVIS</title><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='icon' href='/static/advisor/logo-mark.png'>"
        "<link rel='stylesheet' href='/static/advisor/fonts.css'><link rel='stylesheet' href='/static/advisor/advisor.css'>"
        f"{extra_head}</head><body class='adv'>"
        "<nav class='topnav'><a href='/'>Dashboard</a><a href='/contacts'>Contacts</a>"
        "<a href='/advisor' class='active'>Business Advisor | Επιχειρήσεις</a></nav>"
        f"<main class='adv-main'>{body}</main></body></html>"
    )


def present_page(pid: int) -> str:
    return (
        "<!doctype html><html lang='el'><head><meta charset='utf-8'><title>Παρουσίαση</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
        "<meta name='robots' content='noindex'><link rel='icon' href='/static/advisor/logo-mark.png'>"
        "<link rel='stylesheet' href='/static/advisor/fonts.css'><link rel='stylesheet' href='/static/advisor/present.css'>"
        f"</head><body data-presentation='{int(pid)}'><div id='app' class='app'>"
        "<div class='loading'><img src='/static/advisor/logo-mark.png' alt=''></div></div>"
        "<script src='/static/advisor/present.js'></script></body></html>"
    )


def _banner(notice) -> str:
    return f"<div class='banner ok'>{e(notice)}</div>" if notice else ""


def _title_for(prep, pid) -> str:
    return prep.business_name or prep.owner_name or f"Παρουσίαση #{pid}"


def render_index(advisor, today, notice=None) -> str:
    rows = []
    for o in advisor.overview():
        p, prep = o.presentation, o.preparation
        approved = ("<span class='status st-approved'>Εγκεκριμένη περίληψη</span>"
                    if o.summary is not None and o.summary.approved_at else "")
        rows.append(
            "<tr>"
            f"<td><a href='/advisor/p/{p.id}'><b>{e(_title_for(prep, p.id))}</b></a>"
            f"<div class='muted'>{e(prep.industry or '')}</div></td>"
            f"<td>{e(prep.owner_name or '—')}</td><td>{greek_date(p.meeting_date)}</td>"
            f"<td><span class='status st-{e(p.status)}'>{e(o.status_label)}</span>"
            f"{approved}</td>"
            f"<td class='actions'><a href='/advisor/p/{p.id}'>Προετοιμασία</a>"
            f"<a href='/present/{p.id}' target='_blank' rel='noopener'>Παρουσίαση ↗</a>"
            f"<a href='/advisor/p/{p.id}/summary'>Περίληψη</a></td></tr>"
        )
    table = ("<table class='list'><thead><tr><th>Επιχείρηση</th><th>Επιχειρηματίας</th><th>Συνάντηση</th>"
             "<th>Κατάσταση</th><th></th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
             ) if rows else "<p class='empty'>Δεν υπάρχουν ακόμη παρουσιάσεις. Δημιουργήστε την πρώτη.</p>"
    contacts = "".join(
        f"<option value='{c.id}'>{e(c.full_name)}{' — ' + e(c.company) if c.company else ''}</option>"
        for c in advisor.contacts()
    )
    return shell("Business Advisor", (
        _banner(notice)
        + "<header class='hero'><img src='/static/advisor/logo-mark.png' alt='' class='hero-mark'>"
        "<div><p class='eyebrow'>Business Advisor | Επιχειρήσεις</p>"
        "<h1>Συναντήσεις με επιχειρηματίες</h1>"
        "<p class='lead'>Προετοιμάστε τη συνάντηση, παρουσιάστε με αυτοπεποίθηση και ολοκληρώστε με μια "
        "προσωποποιημένη περίληψη.</p></div>"
        "<div class='hero-links'><a class='btn ghost' href='/advisor/knowledge'>Γνωσιακή βάση</a>"
        "<a class='btn ghost' href='/advisor/products'>Προϊόντα & έγγραφα</a></div></header>"
        "<section class='panel'><h2>Νέα παρουσίαση</h2>"
        "<form method='post' action='/advisor/new' class='inline-form'>"
        f"<label>Ημερομηνία συνάντησης<input type='date' name='meeting_date' value='{today().isoformat()}' required></label>"
        "<label>Σύνδεση με επαφή του Jarvis <span class='muted'>(προαιρετικό — συμπληρώνει όνομα και επωνυμία)</span>"
        f"<select name='contact_id'><option value=''>— Χωρίς σύνδεση —</option>{contacts}</select></label>"
        "<button class='btn primary'>Δημιουργία</button></form></section>"
        f"<section class='panel'><h2>Παρουσιάσεις</h2>{table}</section>"
    ))


def _field_input(name, value) -> str:
    v = "" if value is None else value
    if name in ("employees", "partners"):
        return f"<input type='number' min='0' step='1' name='{name}' value='{e(v)}'>"
    if name in ("facilities", "existing_coverage", "financial_obligations"):
        return f"<textarea name='{name}' rows='2'>{e(v)}</textarea>"
    if name == "legal_form":
        options = "".join(f"<option value='{e(f)}'>" for f in LEGAL_FORMS)
        return f"<input name='legal_form' list='legal-forms' value='{e(v)}'><datalist id='legal-forms'>{options}</datalist>"
    return f"<input name='{name}' value='{e(v)}'>"


def render_workspace(advisor, pid, notice=None) -> str:
    ws = advisor.workspace(pid)
    p, prep, a = ws.presentation, ws.preparation, ws.assessment
    content = advisor.content
    title = _title_for(prep, pid)

    fields = []
    for name, label in FIELD_LABELS.items():
        checked = "checked" if name in prep.shared_fields else ""
        sensitive = "<span class='tag warn'>ευαίσθητο</span>" if name in SENSITIVE_FIELDS else ""
        control = _field_input(name, getattr(prep, name))
        fields.append(
            f"<div class='field'><label>{e(label)} {sensitive}{control}</label>"
            f"<label class='share'><input type='checkbox' name='share' value='{name}' {checked}> Εμφάνιση στον πελάτη</label></div>"
        )
    selected = content.topics(prep.interests)
    interests = "".join(
        f"<label class='check'><input type='checkbox' name='interest' value='{ax['id']}' "
        f"{'checked' if ax['id'] in selected else ''}> {e(ax['title'])}"
        + (" <span class='tag info'>προτεραιότητα</span>" if ax.get("priority") else "") + "</label>"
        for ax in content.axes
    )
    shared_preview = "".join(
        f"<li><span>{e(FIELD_LABELS[f])}</span><b>{e(getattr(prep, f))}</b></li>"
        for f in prep.shared_fields if getattr(prep, f) not in (None, "")
    ) or "<li class='muted'>Κανένα στοιχείο προετοιμασίας δεν θα εμφανιστεί.</li>"

    flow = a.flow
    axis_rows = []
    for ax_id in flow.axis_order:
        qs = [q for q in flow.visible if q["axis"] == ax_id]
        done = sum(1 for q in qs if q["id"] in flow.active)
        axis_rows.append(f"<li><span>{e(content.axis_title(ax_id))}</span><b>{done}/{len(qs)}</b></li>")

    answer_rows = []
    for q in flow.visible:
        ans = flow.active.get(q["id"])
        label = flow.answer_label(q["id"]) if ans else "—"
        answer_rows.append(
            f"<tr><td class='muted'>{e(content.axis_title(q['axis']))}</td><td>{e(q['text'])}</td>"
            f"<td><b>{e(label)}</b></td><td>{e(ans.note if ans else '')}</td></tr>"
        )

    need_rows = []
    for n in a.needs:
        evidence = "; ".join(f"{x['label']}: {x['answer']}" for x in n.evidence) or "—"
        need_rows.append(
            f"<tr><td><span class='level {LEVEL_CLASS[n.level]}'>{e(n.level_label)}</span></td>"
            f"<td><b>{e(n.title)}</b></td><td>{e(n.reason)}</td><td class='muted'>{e(evidence)}</td></tr>"
        )

    rec_cards = []
    for r in a.recommendations:
        if r.documented:
            products = "".join(
                f"<li><b>{e(pr.name)}</b> ({e(pr.provider)}) — έγγραφο {e(pr.filename)}, επαλήθευση "
                f"{e(pr.verified_by)}, {e(pr.verified_on)}</li>" for pr in r.products)
            status = f"<ul class='plain'>{products}</ul>"
        else:
            status = (f"<p class='tag info'>{e(content.solution_labels['no_product_label'])}</p>"
                      f"<p class='muted small'>Κανένα επαληθευμένο προϊόν στον κατάλογο για την κατηγορία "
                      f"«{e(r.direction['category'])}».</p>")
        kb = "".join(
            f"<li><a href='/advisor/knowledge?q={quote(entry['question'])}'>{e(entry['question'])}</a></li>"
            for entry in advisor.knowledge.for_need(r.need.id)
        )
        rec_cards.append(
            f"<article class='rec'><p class='eyebrow'>{e(r.need.title)} · {e(r.need.level_label)}</p>"
            f"<h3>{e(r.direction['title'])}</h3>{status}"
            + (f"<details><summary>Υποστήριξη συμβούλου</summary><ul class='plain'>{kb}</ul></details>" if kb else "")
            + "</article>"
        )

    previous = ""
    if ws.previous_summary:
        prev = ws.previous_summary.content
        previous = (
            "<section class='panel'><h2>Από την προηγούμενη συνάντηση</h2>"
            f"<p class='muted'>Συνάντηση {greek_date(prev.get('meeting_date'))}</p>"
            "<ul>" + "".join(f"<li>{e(x)}</li>" for x in prev.get("priorities", [])) + "</ul>"
            f"<p><a href='/advisor/p/{p.previous_id}/summary'>Προβολή περίληψης</a></p></section>"
        )

    contact = f"<span class='muted'>Επαφή Jarvis: {e(ws.contact_name)}</span>" if ws.contact_name else ""
    return shell(title, (
        _banner(notice)
        + f"<p class='crumbs'><a href='/advisor'>Business Advisor</a> › {e(title)}</p>"
        f"<header class='ws-head'><div><p class='eyebrow'>Προετοιμασία συνάντησης</p><h1>{e(title)}</h1>"
        f"<p><span class='status st-{e(p.status)}'>{e(STATUS_LABELS[p.status])}</span> "
        f"Συνάντηση {greek_date(p.meeting_date)} {contact}</p></div>"
        "<div class='ws-actions'>"
        f"<a class='btn primary big' href='/present/{pid}#start' target='_blank' rel='noopener'>Έναρξη παρουσίασης</a>"
        f"<a class='btn' href='/present/{pid}' target='_blank' rel='noopener'>Συνέχιση παρουσίασης</a>"
        f"<a class='btn ghost' href='/advisor/p/{pid}/summary'>Περίληψη & PDF</a></div></header>"
        "<p class='hint'>Η παρουσίαση ανοίγει σε δικό της παράθυρο και δεν περιέχει ιδιωτικές σημειώσεις. "
        "Σε κοινή χρήση οθόνης, μοιραστείτε μόνο εκείνο το παράθυρο.</p>"
        "<div class='ws-grid'>"
        f"<form method='post' action='/advisor/p/{pid}/prep' class='panel prep'>"
        "<h2>Στοιχεία που γνωρίζω</h2><p class='muted'>Όλα τα πεδία είναι προαιρετικά. Επιλέξτε ποια επιτρέπεται "
        "να εμφανιστούν στον πελάτη — κανένα ευαίσθητο στοιχείο δεν εμφανίζεται αυτόματα.</p>"
        f"<div class='field'><label for='f-date'>Ημερομηνία συνάντησης</label>"
        f"<input id='f-date' type='date' name='meeting_date' value='{e(p.meeting_date)}' required></div>"
        + "".join(fields)
        + f"<fieldset><legend>Κατηγορίες ερωτήσεων</legend><div class='checks'>{interests}</div>"
        "<p class='muted small'>Ρωτάμε μόνο τις επιλεγμένες κατηγορίες, πάντα με τη σειρά: ζωή, υγεία, ομαδικά, "
        "αποταμίευση. Η επιλογή αλλάζει και μέσα στην παρουσίαση.</p></fieldset>"
        "<div class='private'><label for='f-notes'>Ιδιωτικές σημειώσεις</label>"
        f"<textarea id='f-notes' name='internal_notes' rows='5'>{e(ws.internal_notes)}</textarea>"
        "<p class='small'>Αποθηκεύονται χωριστά και δεν εμφανίζονται ποτέ στην παρουσίαση ή στην περίληψη.</p></div>"
        "<button class='btn primary'>Αποθήκευση προσχεδίου</button></form>"
        "<aside class='side'>"
        f"<section class='panel'><h2>Τι θα δει ο πελάτης</h2><ul class='kv'>{shared_preview}</ul></section>"
        f"<section class='panel'><h2>Πορεία συζήτησης</h2><p class='big-number'>{flow.handled}<span>/{flow.total}</span></p>"
        f"<ul class='kv'>{''.join(axis_rows)}</ul></section>"
        "</aside></div>"
        "<section class='panel'><h2>Απαντήσεις</h2>"
        "<p class='muted'>Οι απαντήσεις επεξεργάζονται μέσα στην παρουσίαση (ενότητα «Ας γνωρίσουμε την επιχείρηση»).</p>"
        "<table class='list'><thead><tr><th>Θέμα</th><th>Ερώτηση</th><th>Απάντηση</th><th>Σχόλιο</th></tr></thead>"
        f"<tbody>{''.join(answer_rows)}</tbody></table></section>"
        "<section class='panel'><h2>Ανάλυση αναγκών <span class='tag'>μόνο για τον σύμβουλο</span></h2>"
        "<details><summary>Κανόνες προτεραιοποίησης</summary><ol class='plain'>"
        + "".join(f"<li>{e(x)}</li>" for x in content.priority_rules)
        + "</ol></details><table class='list'><thead><tr><th>Επίπεδο</th><th>Ανάγκη</th><th>Αιτιολόγηση κανόνα</th>"
        f"<th>Με βάση τις απαντήσεις</th></tr></thead><tbody>{''.join(need_rows)}</tbody></table></section>"
        "<section class='panel'><h2>Κατευθύνσεις & τεκμηριωμένα προϊόντα</h2>"
        + ("<div class='recs'>" + "".join(rec_cards) + "</div>" if rec_cards
           else "<p class='empty'>Δεν έχει αναδειχθεί ακόμη ανάγκη προτεραιότητας.</p>")
        + "<p class='muted small'>Προϊόντα εμφανίζονται μόνο αν είναι καταχωρισμένα και επαληθευμένα στα "
        "<a href='/advisor/products'>Προϊόντα & έγγραφα</a>.</p></section>"
        + previous
        + "<section class='panel danger-zone'><h2>Επόμενη συνάντηση & διαγραφή</h2><div class='two'>"
        f"<form method='post' action='/advisor/p/{pid}/next-meeting'><p>Νέα συνάντηση με την ίδια προετοιμασία και "
        "τις ίδιες απαντήσεις ως αφετηρία. Η τρέχουσα περίληψη παραμένει διαθέσιμη.</p>"
        "<label>Ημερομηνία<input type='date' name='meeting_date'></label>"
        "<button class='btn'>Δημιουργία επόμενης συνάντησης</button></form>"
        f"<form method='post' action='/advisor/p/{pid}/delete'><p>Οριστική διαγραφή προετοιμασίας, απαντήσεων, "
        "ιδιωτικών σημειώσεων και περίληψης αυτής της συνάντησης.</p>"
        "<label class='check'><input type='checkbox' name='confirm' value='yes' required> Επιβεβαιώνω τη διαγραφή</label>"
        "<button class='btn danger'>Διαγραφή δεδομένων συνάντησης</button></form></div></section>"
    ))


def summary_document(summary: dict, advisor_profile: dict, labels: dict, footer: str) -> str:
    def items(values, tag="ul"):
        return f"<{tag}>" + "".join(f"<li>{e(v)}</li>" for v in values) + f"</{tag}>" if values else \
            "<p class='muted'>—</p>"

    directions = "".join(
        f"<li><h3>{e(d['title'])}</h3>"
        + (f"<p class='doc-need'>{e(d['need'])}</p>" if d.get("need") else "")
        + f"<p>{e(d.get('why'))}</p>"
        + (f"<p class='doc-solution'>{e(d['solution'])}</p>" if d.get("solution") else "")
        + "</li>"
        for d in summary.get("directions", [])
    )
    a = advisor_profile
    return (
        "<article class='doc'>"
        "<header class='doc-head'><img src='/static/advisor/logo-full.png' alt='Κόλτσης Χρήστος — Insurance & Financial Advisor' class='doc-logo'>"
        f"<div><p class='doc-eyebrow'>Περίληψη συνάντησης</p><h1>{e(summary.get('business_name') or 'Η επιχείρησή σας')}</h1>"
        f"<p class='doc-date'>{greek_date(summary.get('meeting_date'))}</p></div></header>"
        f"<section><h2>Τι συζητήσαμε</h2>{items(summary.get('topics'))}</section>"
        f"<section><h2>Οι προτεραιότητες που αναδείχθηκαν</h2>{items(summary.get('priorities'))}</section>"
        "<section><h2>Προτεινόμενες κατευθύνσεις</h2>"
        + (f"<ol class='doc-dirs'>{directions}</ol>" if directions else "<p class='muted'>—</p>")
        + "</section>"
        f"<section><h2>Τι χρειάζεται να συγκεντρώσουμε</h2>{items(summary.get('information_needed'))}</section>"
        f"<section><h2>Τα επόμενα βήματα</h2>{items(summary.get('next_steps'), 'ol')}</section>"
        f"<footer class='doc-foot'><div><b>{e(a['name'])}</b><br>{e(a['title'])}<br>{e(a['phone'])} · {e(a['email'])}</div>"
        f"<p>{e(labels['disclaimer'])} {e(footer)}</p></footer>"
        "</article>"
    )


def render_summary_editor(advisor, pid, notice=None) -> str:
    p = advisor.get(pid)
    prep = advisor.preparation(pid)
    stored = advisor.summary(pid)
    s = stored.content
    content = advisor.content
    dirs = s.get("directions", []) + [{}] * 3
    dir_fields = "".join(
        f"<fieldset class='dir'><legend>Κατεύθυνση {i + 1}</legend>"
        f"<label>Τίτλος<input name='dir{i}_title' value='{e(d.get('title'))}'></label>"
        f"<label>Ανάγκη<input name='dir{i}_need' value='{e(d.get('need'))}'></label>"
        f"<label>Γιατί προτείνεται<textarea name='dir{i}_why' rows='2'>{e(d.get('why'))}</textarea></label>"
        f"<label>Λύση<input name='dir{i}_solution' value='{e(d.get('solution'))}'></label></fieldset>"
        for i, d in enumerate(dirs[:3])
    )

    def lines(key):
        return e("\n".join(s.get(key, [])))

    if stored.approved_at:
        approval = (f"<div class='banner ok'><b>Εγκεκριμένη για εξαγωγή</b> ({e(stored.approved_at.replace('T', ' '))})."
                    f" <a class='btn primary' href='/advisor/p/{pid}/summary/print' target='_blank' rel='noopener'>"
                    "Εξαγωγή PDF</a></div>")
    else:
        approval = (f"<div class='banner warn'><b>Δεν έχει εγκριθεί.</b> Ελέγξτε το περιεχόμενο και εγκρίνετέ το "
                    f"πριν από την εξαγωγή PDF.<form method='post' action='/advisor/p/{pid}/summary/approve' class='inline'>"
                    "<button class='btn primary'>Εγκρίνω το περιεχόμενο</button></form></div>")
    edited = ("<p class='muted small'>Η περίληψη έχει επεξεργαστεί χειροκίνητα και δεν αλλάζει αυτόματα με τις "
              "απαντήσεις.</p>") if stored.edited else ("<p class='muted small'>Η περίληψη ενημερώνεται αυτόματα "
                                                         "από τις απαντήσεις μέχρι να την επεξεργαστείτε.</p>")
    title = _title_for(prep, pid)
    return shell(f"Περίληψη · {title}", (
        _banner(notice)
        + f"<p class='crumbs'><a href='/advisor'>Business Advisor</a> › <a href='/advisor/p/{pid}'>{e(title)}</a> › Περίληψη</p>"
        f"<h1>Περίληψη συνάντησης</h1>{approval}{edited}"
        "<div class='sum-grid'>"
        f"<form method='post' action='/advisor/p/{pid}/summary' class='panel sum-form'>"
        "<h2>Επεξεργασία</h2>"
        f"<label>Επωνυμία<input name='business_name' value='{e(s.get('business_name'))}'></label>"
        f"<label>Ημερομηνία συνάντησης<input type='date' name='meeting_date' value='{e(s.get('meeting_date') or p.meeting_date)}'></label>"
        f"<label>Τι συζητήσαμε <span class='muted'>(μία γραμμή ανά θέμα)</span><textarea name='topics' rows='4'>{lines('topics')}</textarea></label>"
        f"<label>Προτεραιότητες <span class='muted'>(μία ανά γραμμή)</span><textarea name='priorities' rows='5'>{lines('priorities')}</textarea></label>"
        f"{dir_fields}"
        f"<label>Πληροφορίες που χρειάζονται<textarea name='information_needed' rows='5'>{lines('information_needed')}</textarea></label>"
        f"<label>Επόμενα βήματα<textarea name='next_steps' rows='4'>{lines('next_steps')}</textarea></label>"
        "<button class='btn primary'>Αποθήκευση αλλαγών</button></form>"
        "<div><div class='sum-tools'>"
        f"<form method='post' action='/advisor/p/{pid}/summary/regenerate'><button class='btn ghost'>"
        "Αναδημιουργία από τις απαντήσεις</button></form></div>"
        + "<div class='doc-frame'>"
        + summary_document(s, content.presentation["advisor"], content.solution_labels, content.presentation["footer"])
        + "</div></div></div>"
    ))


def render_print(advisor, pid) -> str:
    stored = advisor.summary(pid)
    content = advisor.content
    s = stored.content
    if not stored.approved_at:
        return shell("Απαιτείται έγκριση", (
            "<div class='banner warn'><b>Απαιτείται έγκριση από τον σύμβουλο πριν από την εξαγωγή.</b></div>"
            f"<p><a class='btn primary' href='/advisor/p/{pid}/summary'>Έλεγχος και έγκριση περίληψης</a></p>"
        ))
    name = f"Περίληψη συνάντησης – {s.get('business_name') or 'Επιχείρηση'} – {s.get('meeting_date', '')}"
    return (
        "<!doctype html><html lang='el'><head><meta charset='utf-8'>"
        f"<title>{e(name)}</title><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<link rel='stylesheet' href='/static/advisor/fonts.css'><link rel='stylesheet' href='/static/advisor/advisor.css'>"
        "</head><body class='print-page'>"
        "<div class='print-bar'><span>Επιλέξτε «Αποθήκευση ως PDF» στο παράθυρο εκτύπωσης.</span>"
        "<button class='btn primary' id='print-now'>Εκτύπωση / Αποθήκευση PDF</button></div>"
        + summary_document(s, content.presentation["advisor"], content.solution_labels, content.presentation["footer"])
        + "<script src='/static/advisor/print.js'></script></body></html>"
    )


EXAMPLE_QUERIES = ("Πώς λειτουργεί η προστασία συνεταίρων;", "Τι καλύπτει η αστική ευθύνη;",
                   "Εκπίπτει το ομαδικό ως δαπάνη;", "Είμαστε ήδη ασφαλισμένοι", "Εξαιρέσεις και περιορισμοί")


def _entry_card(entry, sources, kinds, big=False) -> str:
    return (
        f"<article class='kb {'kb-best' if big else ''}'><p class='eyebrow'>{e(kinds[entry['kind']])}</p>"
        f"<h3>{e(entry['question'])}</h3><p>{e(entry['answer'])}</p>"
        "<p class='sources'>Πηγές: " + " · ".join(e(s) for s in sources) + "</p></article>"
    )


def render_knowledge(advisor, query: str) -> str:
    kb = advisor.knowledge
    kinds = {k["id"]: k["label"] for k in kb.kb["kinds"]}
    examples = "".join(f"<a class='chip' href='/advisor/knowledge?q={quote(q)}'>{e(q)}</a>" for q in EXAMPLE_QUERIES)
    head = (
        "<p class='crumbs'><a href='/advisor'>Business Advisor</a> › Γνωσιακή βάση</p>"
        "<header class='ws-head'><div><p class='eyebrow'>Ιδιωτικό περιβάλλον συμβούλου</p><h1>Γνωσιακή βάση</h1>"
        "<p class='muted'>Απαντήσεις μόνο από τις καταχωρίσεις της βάσης και τα ευρετηριασμένα έγγραφα όρων, "
        "πάντα με την πηγή τους.</p></div></header>"
        "<form method='get' class='search'>"
        f"<input name='q' value='{e(query)}' placeholder='π.χ. Πώς λειτουργεί η προστασία συνεταίρων;' autofocus>"
        f"<button class='btn primary'>Αναζήτηση</button></form><div class='chips'>{examples}</div>"
    )
    if not query:
        sections = "".join(
            f"<section class='panel'><h2>{e(kind['label'])}</h2><div class='kb-grid'>"
            + "".join(_entry_card(entry, kb.source_labels(entry), kinds) for entry in entries)
            + "</div></section>"
            for kind, entries in kb.browse() if entries
        )
        return shell("Γνωσιακή βάση", head + sections)
    result = advisor.search_knowledge(query)
    if not result.found:
        body = ("<div class='banner warn'>Δεν βρέθηκε απάντηση στη γνωσιακή βάση ή στα ευρετηριασμένα έγγραφα. "
                "Ο Jarvis δεν συμπληρώνει απαντήσεις από μνήμης.</div>")
        return shell("Γνωσιακή βάση", head + body)
    body = ""
    if result.best:
        body += "<h2>Σύντομη απάντηση</h2>" + _entry_card(result.best.entry, result.best.sources, kinds, big=True)
    if result.documents:
        body += "<h2>Από τα έγγραφα όρων</h2>" + "".join(
            f"<article class='kb doc-hit'><p class='eyebrow'>{e(h.filename)} · σελίδα {h.page}</p>"
            f"<p>{e(h.snippet)}</p></article>" for h in result.documents)
    elif not advisor.indexed_documents():
        body += ("<p class='muted small'>Δεν υπάρχουν ακόμη ευρετηριασμένα έγγραφα όρων — βλ. "
                 "<a href='/advisor/products'>Προϊόντα & έγγραφα</a>.</p>")
    if result.related:
        body += "<h2>Σχετικά</h2><div class='kb-grid'>" + "".join(
            _entry_card(h.entry, h.sources, kinds) for h in result.related) + "</div>"
    return shell("Γνωσιακή βάση", head + body)


CATALOG_EXAMPLE = """{
  "products": [
    {
      "id": "unique-id",
      "name": "Όνομα προϊόντος όπως στους όρους",
      "provider": "Ασφαλιστική εταιρεία",
      "categories": ["key_person"],
      "summary": "Σύντομη περιγραφή από τους όρους",
      "document": {"file": "oroi-proiontos.pdf", "sha256": "…", "version": "2026-01"},
      "benefits": [{"text": "Παροχή όπως διατυπώνεται στους όρους", "page": 3}],
      "limitations": [{"text": "Εξαίρεση ή περιορισμός", "page": 7}],
      "verified_by": "Χ. Κόλτσης",
      "verified_on": "2026-11-07"
    }
  ]
}"""


def render_products(advisor, query) -> str:
    catalog = advisor.catalog()
    indexed = {d.filename: d for d in advisor.indexed_documents()}
    message = ""
    if _first(query, "unavailable"):
        message = f"<div class='banner warn'>{e(_first(query, 'msg'))}</div>"
    elif _first(query, "indexed"):
        message = (f"<div class='banner ok'>Ευρετηρίαση: {e(_first(query, 'indexed'))} νέα/αλλαγμένα, "
                   f"{e(_first(query, 'unchanged'))} χωρίς αλλαγή, {e(_first(query, 'removed'))} αφαιρέθηκαν, "
                   f"{e(_first(query, 'errors'))} σφάλματα.</div>")
    products = "".join(
        f"<tr><td><b>{e(pr.name)}</b><div class='muted'>{e(pr.provider)}</div></td><td>{e(', '.join(pr.categories))}</td>"
        f"<td>{e(pr.filename)} {e(pr.version)}</td><td>{len(pr.benefits)} / {len(pr.limitations)}</td>"
        f"<td>{e(pr.verified_by)}, {e(pr.verified_on)}</td></tr>" for pr in catalog.products
    )
    products_html = ("<table class='list'><thead><tr><th>Προϊόν</th><th>Κατηγορίες</th><th>Έγγραφο</th>"
                     "<th>Παροχές / περιορισμοί</th><th>Επαλήθευση</th></tr></thead>"
                     f"<tbody>{products}</tbody></table>") if products else (
        "<p class='empty'>Δεν υπάρχει κανένα τεκμηριωμένο προϊόν. Στην παρουσίαση, κάθε κατεύθυνση εμφανίζεται ως "
        f"«{e(advisor.content.solution_labels['no_product_label'])}»</p>")
    issues = "".join(
        f"<li><b>{e(i.product)}</b><ul>" + "".join(f"<li>{e(x)}</li>" for x in i.problems) + "</ul></li>"
        for i in catalog.issues
    )
    not_indexed = "<span class='tag warn'>όχι</span>"
    files = "".join(
        f"<tr><td>{e(f.filename)}</td><td><code>{e(f.sha256)}</code></td><td>"
        + (f"{indexed[f.filename].page_count} σελ." if f.filename in indexed
           and indexed[f.filename].sha256 == f.sha256 else not_indexed)
        + "</td></tr>"
        for f in catalog.files
    )
    categories = "".join(
        f"<li><code>{e(d['category'])}</code> — {e(d['title'])}</li>" for d in advisor.content.directions.values()
    )
    return shell("Προϊόντα & έγγραφα", (
        "<p class='crumbs'><a href='/advisor'>Business Advisor</a> › Προϊόντα & έγγραφα</p>"
        + message
        + "<header class='ws-head'><div><p class='eyebrow'>Ιδιωτικό περιβάλλον συμβούλου</p><h1>Προϊόντα & έγγραφα</h1>"
        "<p class='muted'>Ένα προϊόν εμφανίζεται σε πρόταση μόνο όταν: είναι καταχωρισμένο στο "
        "<code>knowledge/products/catalog.json</code>, κάθε παροχή του παραπέμπει σε σελίδα επίσημου εγγράφου όρων "
        "και το SHA-256 του εγγράφου ταιριάζει με αυτό που καταγράψατε κατά την επαλήθευση.</p></div></header>"
        f"<section class='panel'><h2>Τεκμηριωμένα προϊόντα</h2>{products_html}</section>"
        + (f"<section class='panel'><h2>Καταχωρίσεις που δεν πέρασαν τον έλεγχο</h2><ul>{issues}</ul></section>" if issues else "")
        + ("" if catalog.found else "<p class='muted'>Δεν υπάρχει ακόμη αρχείο <code>catalog.json</code>.</p>")
        + "<section class='panel'><h2>Έγγραφα στον φάκελο knowledge/products/</h2>"
        + (("<table class='list'><thead><tr><th>Αρχείο</th><th>SHA-256</th><th>Ευρετήριο</th></tr></thead>"
            f"<tbody>{files}</tbody></table>") if files else "<p class='empty'>Δεν υπάρχουν PDF στον φάκελο.</p>")
        + "<form method='post' action='/advisor/products/index'><button class='btn'>Ευρετηρίαση εγγράφων</button></form>"
        "<p class='muted small'>Η ευρετηρίαση εξάγει το κείμενο κάθε σελίδας τοπικά (προαιρετικό πακέτο pypdf) "
        "και ενημερώνει μόνο αρχεία που άλλαξαν.</p></section>"
        f"<section class='panel'><h2>Κατηγορίες λύσεων</h2><ul class='plain'>{categories}</ul>"
        f"<details><summary>Μορφή καταχώρισης</summary><pre>{e(CATALOG_EXAMPLE)}</pre></details></section>"
    ))
