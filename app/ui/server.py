from datetime import date
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.core.errors import NotFoundError
from app.services.context import Services

STYLE = """
body{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1d2330}
nav{background:#1d2330;padding:12px 20px}nav a{color:#fff;margin-right:18px;text-decoration:none;font-weight:600}
main{max-width:1000px;margin:0 auto;padding:20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.card{background:#fff;border-radius:8px;padding:14px;box-shadow:0 1px 2px #0002}
.card b{font-size:28px;display:block}
table{width:100%;border-collapse:collapse;background:#fff;margin:8px 0 20px}
th,td{text-align:left;padding:8px;border-bottom:1px solid #e3e6ea}
.muted{color:#6b7280}input{padding:6px;width:260px}
"""


def e(value) -> str:
    return "" if value is None else escape(str(value))


def page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html lang='el'><head><meta charset='utf-8'><title>{e(title)} · JARVIS</title>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'><style>{STYLE}</style></head>"
        f"<body><nav><a href='/'>Dashboard</a><a href='/contacts'>Contacts</a></nav><main>{body}</main></body></html>"
    )


def table(headers, rows, empty="Nothing here.") -> str:
    if not rows:
        return f"<p class='muted'>{e(empty)}</p>"
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def contact_link(contact_id, names) -> str:
    if contact_id is None:
        return "<span class='muted'>—</span>"
    return f"<a href='/contacts/{int(contact_id)}'>{e(names.get(contact_id, f'#{contact_id}'))}</a>"


def render_dashboard(services, today: date) -> str:
    o = services.planner.today(today)
    names = services.crm.names(
        [a.contact_id for a in o.appointments] + [f.contact_id for f in o.overdue_follow_ups + o.due_today_follow_ups]
    )
    names.update({c.id: c.full_name for c in o.untouched_leads})
    cards = "".join(
        f"<div class='card'><b>{n}</b>{e(label)}</div>" for n, label in [
            (len(o.appointments), "appointments today"),
            (len(o.due_today_follow_ups), "follow-ups due today"),
            (len(o.overdue_follow_ups), "overdue follow-ups"),
            (len(o.untouched_leads), "untouched leads"),
            (o.contact_count, "contacts"),
        ]
    )

    def follow_up_rows(items):
        return [[e(f.due_at), contact_link(f.contact_id, names), e(f.priority), e(f.reason)] for f in items]

    return page("Dashboard", (
        f"<h1>Today · {e(o.date)}</h1><div class='cards'>{cards}</div>"
        "<h2>Appointments</h2>"
        + table(["Start", "Contact", "Purpose", "Location"],
                [[e(a.start_at), contact_link(a.contact_id, names), e(a.purpose), e(a.location)]
                 for a in o.appointments], "No appointments today.")
        + "<h2>Overdue follow-ups</h2>"
        + table(["Due", "Contact", "Priority", "Reason"], follow_up_rows(o.overdue_follow_ups), "None overdue.")
        + "<h2>Follow-ups due today</h2>"
        + table(["Due", "Contact", "Priority", "Reason"], follow_up_rows(o.due_today_follow_ups), "None due today.")
        + "<h2>Untouched leads</h2>"
        + table(["Name", "Phone", "Source"],
                [[contact_link(c.id, names), e(c.phone), e(c.source)] for c in o.untouched_leads],
                "Every lead has been contacted.")
    ))


def render_contacts(services, query: str) -> str:
    contacts = services.crm.search(query)
    names = {c.id: c.full_name for c in contacts}
    rows = [[contact_link(c.id, names), e(c.phone), e(c.company), e(c.status), e(c.product_interest)]
            for c in contacts]
    return page("Contacts", (
        f"<h1>Contacts</h1><form method='get'><input name='q' value='{e(query)}' placeholder='Search name, phone, email…'>"
        f" <button>Search</button></form><p class='muted'>{len(contacts)} result(s)</p>"
        + table(["Name", "Phone", "Company", "Status", "Interest"], rows, "No matching contacts.")
    ))


def render_contact(services, contact_id: int) -> str | None:
    try:
        t = services.crm.timeline(contact_id)
    except NotFoundError:
        return None
    c = t.contact
    fields = [("Phone", c.phone), ("Email", c.email), ("Profession / company", c.company), ("Source", c.source),
              ("Status", c.status), ("Product interest", c.product_interest), ("Client", "yes" if c.client_flag else "no")]
    details = "".join(f"<tr><th>{label}</th><td>{e(value)}</td></tr>" for label, value in fields)
    return page(c.full_name, (
        f"<h1>{e(c.full_name)}</h1><table>{details}</table>"
        "<h2>Follow-ups</h2>"
        + table(["Due", "Priority", "Status", "Reason"],
                [[e(f.due_at), e(f.priority), e(f.status), e(f.reason)] for f in t.follow_ups], "No follow-ups.")
        + "<h2>Appointments</h2>"
        + table(["Start", "Purpose", "Status"],
                [[e(a.start_at), e(a.purpose), e(a.status)] for a in t.appointments], "No appointments.")
        + "<h2>Production</h2>"
        + table(["Date", "Product", "Value", "Status"],
                [[e(p.date), e(p.product), e(p.value), e(p.status)] for p in t.production], "No production.")
        + "<h2>Timeline</h2>"
        + table(["When", "Type", "Outcome", "Product", "Notes"],
                [[e(a.timestamp), e(a.activity_type), e(a.outcome), e(a.product), e(a.notes)]
                 for a in t.activities], "No activity yet.")
    ))


def make_handler(db_path, today_fn=date.today):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            parts = [p for p in url.path.split("/") if p]
            with Services.open(db_path) as services:
                if not parts:
                    html = render_dashboard(services, today_fn())
                elif parts == ["contacts"]:
                    html = render_contacts(services, parse_qs(url.query).get("q", [""])[0])
                elif len(parts) == 2 and parts[0] == "contacts" and parts[1].isdigit():
                    html = render_contact(services, int(parts[1]))
                else:
                    html = None
            if html is None:
                self._send(HTTPStatus.NOT_FOUND, page("Not found", "<h1>Not found</h1>"))
            else:
                self._send(HTTPStatus.OK, html)

        def _send(self, status, html):
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return Handler


def make_server(db_path, host="127.0.0.1", port=8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(db_path))
