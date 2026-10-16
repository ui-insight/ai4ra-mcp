"""costs: what the University of Idaho charges, from the pages that publish it.

Upstream: four pages on www.uidaho.edu, read as HTML and cached a day. Student Accounts' student billing page (the
per-semester tuition and fee schedule by student group, summer and winter per-credit rates, the prior year's schedule,
the late fee schedule and the refund schedule), its account payments page (the payment plan rules), Financial Aid's
cost of attendance page (the estimated annual cost tables by student type and program) and Student Health Services'
SHIP page (the Student Health Insurance Program's premiums, coverage dates and dependent rates). None is an API: the
pages are the university's content management system (headings, accordions, lists and tables), parsed into their own
headings and items, so a figure here is the page's figure and every answer carries the page's URL and its heading so
the reader can check the page when the university changes it. Nothing is from memory: a page that does not answer, or
whose section cannot be found, is reported as such.
"""

from __future__ import annotations

import html as htmlmod
import re
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
SITE = "https://www.uidaho.edu"
PAGES = {
    "billing": {"url": f"{SITE}/student-resources/student-accounts/student-billing", "title": "Student billing (Student Accounts)"},
    "payments": {"url": f"{SITE}/student-resources/student-accounts/account-payments", "title": "Account and payment information (Student Accounts)"},
    "attendance": {"url": f"{SITE}/financial-aid/cost-of-attendance", "title": "Cost of attendance (Financial Aid)"},
    "ship": {"url": f"{SITE}/student-health-insurance/ship", "title": "Student Health Insurance Program (Student Health Services)"},
    "insurance": {"url": f"{SITE}/student-health-insurance", "title": "Student health insurance requirement (Student Health Services)"},
}
SCHEDULES = {"semester": r"per semester tuition and fee schedule", "summer": r"^Summer \d{4} tuition and fee schedule", "winter": r"^Winter intersession \d{4} tuition and fee schedule", "prior": r"^Prior year fee schedule"}
_cache = TTLCache()

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_MAIN = re.compile(r"<main\b.*?</main>", re.S)
_BLOCK = re.compile(
    r"<(h[1-6])(?P<attrs>[^>]*)>(?P<h>.*?)</\1>"
    r'|<summary[^>]*>.*?<div class="text-xl[^"]*">(?P<sum>.*?)</div>.*?</summary>'
    r"|<p(?P<pattrs>[^>]*)>(?P<p>.*?)</p>"
    r"|<ul[^>]*>(?P<ul>.*?)</ul>"
    r"|<table[^>]*>(?P<table>.*?)</table>",
    re.S)
_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TD = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
_ID = re.compile(r'id="([^"]+)"')
_ITEM = re.compile(r"^(?P<name>[^:]{2,120}?):\s*(?P<value>.+)$", re.S)
_YEAR = re.compile(r"(20\d\d-\d\d)")

mcp = MCPServer(
    "costs",
    instructions="What the University of Idaho charges, from its own pages: the tuition and fee schedule by student group (costs_tuition), the estimated annual cost of attendance by student type and program (costs_attendance), payment deadlines, late fees and refunds (costs_deadlines), and the Student Health Insurance Program's premiums and dates (costs_insurance). Every answer names the page and heading it was read from. Read costs_index first.",
)


def text(fragment: str | None) -> str:
    return _WS.sub(" ", htmlmod.unescape(_TAG.sub(" ", fragment or ""))).strip()


def blocks(page: str) -> list[dict]:
    """The page's main content as its headings, accordion labels, paragraphs, lists and tables in order.

    An accordion label (the <summary> of a <details>) is a heading one level below the last real heading, which is
    how the page reads: 'Late fees' then 'Spring 2026 late fee schedule'."""
    m = _MAIN.search(page)
    body = m.group(0) if m else page
    out: list[dict] = []
    level = 1
    for b in _BLOCK.finditer(body):
        if b.group("h") is not None:
            level = int(b.group(1)[1])
            idm = _ID.search(b.group("attrs") or "")
            out.append({"kind": "heading", "level": level, "text": text(b.group("h")), "id": idm.group(1) if idm else None})
        elif b.group("sum") is not None:
            out.append({"kind": "heading", "level": level + 1, "text": text(b.group("sum")), "id": None, "accordion": True})
        elif b.group("p") is not None:
            t = text(b.group("p"))
            if t:
                raw = b.group("p")
                out.append({"kind": "paragraph", "text": t, "strong": raw.lstrip().startswith("<strong>"), "note": raw.lstrip().startswith("<i>") or raw.lstrip().startswith("<em>")})
        elif b.group("ul") is not None:
            items = [text(li) for li in _LI.findall(b.group("ul"))]
            if items:
                out.append({"kind": "list", "items": items})
        elif b.group("table") is not None:
            rows = [[text(c) for c in _TD.findall(r)] for r in _TR.findall(b.group("table"))]
            rows = [r for r in rows if any(r)]
            if rows:
                out.append({"kind": "table", "rows": rows})
    return out


def sections(bl: list[dict]) -> list[dict]:
    """The blocks grouped under their headings: each section is a heading with the blocks that follow it until the
    next heading, and the chain of headings above it."""
    out: list[dict] = []
    chain: list[tuple[int, str]] = []
    cur: dict | None = None
    for b in bl:
        if b["kind"] == "heading":
            chain = [c for c in chain if c[0] < b["level"]] + [(b["level"], b["text"])]
            cur = {"heading": b["text"], "level": b["level"], "path": [c[1] for c in chain], "id": b.get("id"), "blocks": []}
            out.append(cur)
        elif cur is not None:
            cur["blocks"].append(b)
    return out


def split_item(s: str) -> dict:
    """'Full-time (10-20 credits): $4,912' as name and value; a line with no colon is a note."""
    m = _ITEM.match(s)
    if m and not s.startswith("http"):
        return {"name": m.group("name").strip(), "value": m.group("value").strip()}
    return {"note": s}


def parts(section_blocks: list[dict]) -> list[dict]:
    """A section's paragraphs and lists as labelled groups: a bold paragraph opens a group, a plain paragraph labels
    the list that follows it, an italic paragraph is a note, a table is a table."""
    out: list[dict] = []
    group: dict | None = None
    label: str | None = None

    def ensure():
        nonlocal group
        if group is None:
            group = {"group": None, "rates": [], "notes": []}
            out.append(group)
        return group

    for b in section_blocks:
        if b["kind"] == "paragraph":
            if b.get("strong"):
                group = {"group": b["text"].rstrip(":"), "rates": [], "notes": []}
                out.append(group)
                label = None
            elif b.get("note"):
                ensure()["notes"].append(b["text"])
            else:
                label = b["text"].rstrip(":").strip()
        elif b["kind"] == "list":
            g = ensure()
            g["rates"].append({"label": label, "items": [split_item(i) for i in b["items"]]})
            label = None
        elif b["kind"] == "table":
            ensure()["rates"].append({"label": label, "table": table(b["rows"])})
            label = None
    return out


def table(rows: list[list[str]]) -> dict:
    """A table whose first row names the columns and whose first column names the rows, as columns and rows."""
    if not rows:
        return {"columns": [], "rows": []}
    header, body = rows[0], rows[1:]
    columns = [c for c in header[1:]]
    if not columns and body:
        return {"columns": [], "rows": [{"label": r[0], "values": r[1:]} for r in body]}
    return {"columns": columns, "rows": [{"label": r[0], **{columns[i]: v for i, v in enumerate(r[1:]) if i < len(columns)}} for r in body]}


def plain(s: str) -> str:
    """Letters and digits only, lower case, so 'MBA' finds 'M.B.A.' and 'in state' finds 'In-state'."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def matches(words: list[str], *texts: str) -> bool:
    hay = plain(" ".join(texts))
    return all(plain(w) in hay for w in words)


def find(secs: list[dict], pattern: str, level: int | None = None) -> list[dict]:
    rx = re.compile(pattern, re.I)
    return [s for s in secs if rx.search(s["heading"]) and (level is None or s["level"] == level)]


def subtree(secs: list[dict], top: dict) -> list[dict]:
    """A section and the sections under it, in page order, until the next heading at its level or above."""
    out = []
    started = False
    for s in secs:
        if s is top:
            started = True
            out.append(s)
        elif started:
            if s["level"] <= top["level"]:
                break
            out.append(s)
    return out


async def _page(key: str) -> tuple[str, list[dict]]:
    page = PAGES[key]
    raw = await _cache.remember(f"page:{key}", DAY, lambda: get_text(page["url"]))
    return raw, sections(blocks(raw))


def source(key: str, heading: str | None = None, anchor: str | None = None) -> dict:
    page = PAGES[key]
    return {"page": page["title"], "url": page["url"] + (f"#{anchor}" if anchor else ""), "heading": heading, "read": date.today().isoformat(),
            "note": "The page is the authority and changes each year; quote figures with the academic year the heading names and this link."}


def _error(e: Exception, key: str) -> dict:
    return {"error": str(e), "source": source(key), "note": "The university's page, not an API; a change to the page can move a section without notice. Open the link."}


@mcp.tool(name="costs_index", annotations=_READ_ONLY)
async def costs_index() -> dict:
    """How to use the University of Idaho costs tools. READ THIS FIRST: which page each figure comes from, what a tuition schedule holds, and what is not here."""
    return {
        "upstream": "Four pages on www.uidaho.edu, read as published and cached a day: " + "; ".join(f"{p['title']} at {p['url']}" for p in PAGES.values()),
        "workflow": ["costs_tuition for the per-semester tuition and fee schedule by student group (undergraduate, graduate, law, art and architecture, online programs), full-time and per-credit, plus summer and winter per-credit rates and the prior year",
                     "costs_attendance for the estimated annual cost of attendance tables (tuition and fees, housing and meals, books, transportation, personal) by residency and student type, and the program-specific tables",
                     "costs_deadlines for when payment is due, the late fee schedule by term, the refund schedule and the payment plan rules",
                     "costs_insurance for the Student Health Insurance Program: who must have insurance, the premium by period, coverage dates, dependent rates"],
        "notes": ["Figures are the page's own text, parsed from its headings, lists and tables; each answer carries the page URL and heading. Quote the academic year the heading names (a schedule is for one year) and give the link.",
                  "A tuition schedule is per semester; a cost of attendance table is an annual estimate Financial Aid uses for aid eligibility, so housing, books and travel there are estimates, not charges.",
                  "Not here: special course and lab fees (the class schedule lists them by section), housing contract rates, graduate assistant stipends or tuition waivers, and anything behind a login. Fringe benefit and F&A rates for budgets are the uidaho server's uidaho_rates.",
                  "A grant budget's tuition line is the schedule's full-time or per-credit figure for the student's level and residency; cite the schedule and its year."],
        "link": PAGES["billing"]["url"],
    }


@mcp.tool(name="costs_tuition", annotations=_READ_ONLY)
async def costs_tuition(schedule: str = "semester", students: str = "") -> dict:
    """The University of Idaho tuition and fee schedule from the student billing page: by student group, full-time and per-credit, with the extra charges.

    Args:
        schedule: 'semester' (default) for the current year's per-semester schedule by student group; 'summer' or 'winter' for the per-credit session rates; 'prior' for last year's schedule.
        students: Optional words of a student group to keep, e.g. 'graduate', 'law', 'undergraduate', 'architecture', 'online'; empty for all groups.
    """
    kind = schedule.strip().lower()
    if kind not in SCHEDULES:
        return {"error": "schedule must be semester, summer, winter or prior"}
    try:
        _, secs = await _page("billing")
    except ValueError as e:
        return _error(e, "billing")
    tops = find(secs, SCHEDULES[kind])
    if not tops:
        return {"error": f"the student billing page has no heading matching '{SCHEDULES[kind]}' today; the page may have been reorganised", "source": source("billing")}
    top = tops[0]
    # The semester schedule's accordions are the student groups; the summer and winter schedules sit under the same
    # h2 as their own headings and are their own schedules, so they and what is under them are left out here.
    others = [p for k, p in SCHEDULES.items() if k != kind]
    tree, skip_below = [], None
    for s in subtree(secs, top):
        if s is not top and any(re.search(p, s["heading"], re.I) for p in others):
            skip_below = s["level"]
            continue
        if skip_below is not None and s["level"] > skip_below:
            continue
        skip_below = None
        tree.append(s)
    ym = _YEAR.search(top["heading"]) or re.search(r"(20\d\d)", top["heading"])
    groups = []
    words = students.split()
    for s in tree[1:] if len(tree) > 1 else tree:
        if words and not matches(words, s["heading"]):
            continue
        groups.append({"students": s["heading"], "parts": parts(s["blocks"])})
    if len(tree) == 1:
        groups = [{"students": top["heading"], "parts": parts(top["blocks"])}]
    intro = [b["text"] for b in top["blocks"] if b["kind"] == "paragraph"] if len(tree) > 1 else []
    return {"schedule": top["heading"], "year": ym.group(1) if ym else None, "intro": intro, "groups": groups, "total_groups": len(groups),
            "source": source("billing", top["heading"], top.get("id"))}


@mcp.tool(name="costs_attendance", annotations=_READ_ONLY)
async def costs_attendance(students: str = "") -> dict:
    """The estimated annual cost of attendance tables from the Financial Aid page: tuition and fees, housing and meals, books, transportation and personal costs by residency, for each student type and program.

    Args:
        students: Optional words of a student type or program to keep, e.g. 'graduate', 'law', 'undergraduate', 'online', 'MBA', 'international'; empty for every table.
    """
    try:
        _, secs = await _page("attendance")
    except ValueError as e:
        return _error(e, "attendance")
    words = students.split()
    out = []
    for s in secs:
        if not any(b["kind"] == "table" for b in s["blocks"]) and "international" not in s["heading"].lower():
            continue
        if words and not matches(words, s["heading"], *s["path"]):
            continue
        tables = [table(b["rows"]) for b in s["blocks"] if b["kind"] == "table"]
        notes = [b["text"] for b in s["blocks"] if b["kind"] == "paragraph" and (b.get("note") or b.get("strong"))]
        out.append({"students": s["heading"], "under": s["path"][:-1], "tables": tables, "notes": notes, "anchor": s.get("id")})
    year = next((m.group(1) for s in secs for m in [_YEAR.search(s["heading"])] if m), None)
    return {"year": year, "total": len(out), "costs": out, "source": source("attendance", "University of Idaho costs and tuition"),
            "note": "Annual estimates Financial Aid uses for aid eligibility: tuition and fees are charges, housing, books, transportation and personal costs are estimates."}


@mcp.tool(name="costs_deadlines", annotations=_READ_ONLY)
async def costs_deadlines() -> dict:
    """When tuition is due at the University of Idaho: the late fee schedule by term, the refund schedule, and the payment plan rules, from the Student Accounts pages."""
    out: dict = {"sources": []}
    try:
        _, secs = await _page("billing")
        late = find(secs, r"^Late fees$")
        refunds = find(secs, r"^Tuition and fee refunds$")
        if late:
            tree = subtree(secs, late[0])
            out["late_fees"] = {"intro": [b["text"] for b in late[0]["blocks"] if b["kind"] == "paragraph"],
                                "terms": [{"term": s["heading"], "parts": parts(s["blocks"])} for s in tree[1:]]}
            out["sources"].append(source("billing", late[0]["heading"], late[0].get("id") or "late-fees"))
        if refunds:
            tree = subtree(secs, refunds[0])
            out["refunds"] = [{"heading": s["heading"], "parts": parts(s["blocks"])} for s in tree]
            out["sources"].append(source("billing", refunds[0]["heading"], refunds[0].get("id")))
        due = [b["text"] for s in secs for b in s["blocks"] if b["kind"] == "paragraph" and re.search(r"\bdue\b", b["text"], re.I) and "tuition" in b["text"].lower()]
        if due:
            out["due"] = due
    except ValueError as e:
        out["billing_error"] = str(e)
    try:
        _, psecs = await _page("payments")
        plans = find(psecs, r"^Payment plans$")
        if plans:
            tree = subtree(psecs, plans[0])
            out["payment_plans"] = [{"heading": s["heading"], "parts": parts(s["blocks"])} for s in tree]
            out["sources"].append(source("payments", plans[0]["heading"], plans[0].get("id")))
    except ValueError as e:
        out["payments_error"] = str(e)
    if not out["sources"]:
        return {"error": "neither Student Accounts page answered or neither had its late fee, refund or payment plan section", "sources": [source("billing"), source("payments")]}
    out["note"] = "Dates are the page's for the terms it lists; the Registrar's calendar (the events server) holds the academic deadlines, which are separate."
    return out


@mcp.tool(name="costs_insurance", annotations=_READ_ONLY)
async def costs_insurance() -> dict:
    """The Student Health Insurance Program (SHIP): who must carry insurance, the premium by period, coverage dates and dependent rates, from Student Health Services' pages."""
    out: dict = {"sources": []}
    try:
        _, secs = await _page("ship")
        for s in secs:
            if s["level"] <= 1 or s["heading"].lower() in ("footer", "footer navigation", "resources", "campus", "information for", "contact us", "subscribe to u of i", "ready to apply?"):
                continue
            if not s["blocks"]:
                continue
            key = re.sub(r"[^a-z0-9]+", "_", s["heading"].lower()).strip("_")
            out[key] = {"heading": s["heading"], "parts": parts(s["blocks"])}
        out["sources"].append(source("ship", "SHIP costs"))
    except ValueError as e:
        out["ship_error"] = str(e)
    try:
        _, rsecs = await _page("insurance")
        req = find(rsecs, r"^Student health insurance requirement$")
        if req:
            out["requirement"] = {"heading": req[0]["heading"], "parts": parts(req[0]["blocks"])}
            out["sources"].append(source("insurance", req[0]["heading"]))
    except ValueError as e:
        out["requirement_error"] = str(e)
    if not out["sources"]:
        return {"error": "neither Student Health Services page answered", "sources": [source("ship"), source("insurance")]}
    out["note"] = "Premiums are for the plan year the SHIP page's tables name; a graduate assistant's insurance is this program unless the appointment letter says otherwise, so a budget's health insurance line is the student-only premium by semester."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# No tool here takes an identifier from a list; every argument is words (#40).
