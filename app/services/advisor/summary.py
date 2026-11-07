"""MeetingSummary: the personalised, client-facing summary built from the answers. Editable by the advisor."""
MAX_DIRECTIONS = 3
MAX_PRIORITIES = 5

SUMMARY_FIELDS = ("business_name", "meeting_date", "topics", "priorities", "directions",
                  "information_needed", "next_steps")


def build_summary(content, presentation, business_name, flow, needs, recommendations, axis_title=None) -> dict:
    axis_title = axis_title or content.axis_title
    priorities = [n.statement for n in needs if n.level == "confirmed"]
    if not priorities:
        priorities = [n.statement for n in needs if n.level == "possible"][:MAX_DIRECTIONS]

    directions = []
    for r in recommendations[:MAX_DIRECTIONS]:
        directions.append({
            "title": r.direction["title"],
            "need": r.need.title,
            "why": r.direction["why"],
            "solution": (", ".join(p.name for p in r.products) if r.documented
                         else content.solution_labels["no_product_label"]),
        })

    information = []
    for r in recommendations[:MAX_DIRECTIONS]:
        for item in r.direction["information_needed"]:
            if item not in information:
                information.append(item)
    unresolved = [n.title for n in needs if n.level == "info_needed" and n.discussed]
    if unresolved:
        information.append("Περισσότερα στοιχεία για: " + ", ".join(unresolved))
    undiscussed_axes = [axis_title(a) for a in flow.axis_order if a not in flow.discussed_axes()]
    if undiscussed_axes:
        information.append("Θέματα για την επόμενη συζήτηση: " + ", ".join(undiscussed_axes))

    return {
        "business_name": business_name or "",
        "meeting_date": presentation.meeting_date,
        "topics": [axis_title(a) for a in flow.discussed_axes()],
        "priorities": priorities[:MAX_PRIORITIES],
        "directions": directions,
        "information_needed": information,
        "next_steps": list(content.presentation["next"]["steps"]),
    }


def normalize_summary(raw: dict) -> dict:
    """Cleans advisor edits: trims text, drops empty lines and keeps at most three directions."""
    def lines(value):
        items = value.splitlines() if isinstance(value, str) else (value or [])
        return [str(i).strip() for i in items if str(i).strip()]

    directions = []
    for d in raw.get("directions") or []:
        d = {k: str(d.get(k) or "").strip() for k in ("title", "need", "why", "solution")}
        if d["title"]:
            directions.append(d)
    return {
        "business_name": str(raw.get("business_name") or "").strip(),
        "meeting_date": str(raw.get("meeting_date") or "").strip(),
        "topics": lines(raw.get("topics")),
        "priorities": lines(raw.get("priorities")),
        "directions": directions[:MAX_DIRECTIONS],
        "information_needed": lines(raw.get("information_needed")),
        "next_steps": lines(raw.get("next_steps")),
    }
