"""nihdates: NIH's standard application due dates, its review and award cycles, and the salary cap by fiscal year.

Upstream: two pages on grants.nih.gov, read as HTML and cached a day. The standard due dates page (the table of
activity codes with their Cycle I, II and III dates, and the table of what happens in each cycle: due dates, merit
review, council, earliest start) and the salary cap summary (the Executive Level II amount for awards issued in each
period of each fiscal year since 1990, with the Guide notice that set it). Neither is an API: the pages are parsed
into their own rows, so a date or an amount here is the page's and every answer carries the page's URL and when it
says it was last updated, for the reader to check when NIH changes it. Nothing is from memory.
"""

from __future__ import annotations

import html as htmlmod
import re
from datetime import date, datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
SITE = "https://grants.nih.gov"
DUE_URL = f"{SITE}/grants-process/submit/submission-policies/standard-due-dates"
CAP_URL = f"{SITE}/policy-and-compliance/policy-topics/nih-fiscal-policies/salary-cap-summary"
_cache = TTLCache()

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_TABLE = re.compile(r"<table[^>]*>(.*?)</table>", re.S)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TD = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
_UPDATED = re.compile(r"last (?:updated|reviewed) on:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})", re.I)
_KINDS = re.compile(r"\b(All|new|renewal|resubmission|revision)s?\b", re.I)
_CODE = re.compile(r"\b([A-Z]{1,2}\d{2}(?:/[A-Z]{1,2}\d{2})?|[A-Z] [Ss]eries)\b")
_FY_H3 = re.compile(r"<h3[^>]*>(?P<h>.*?)</h3>\s*<ul[^>]*>(?P<ul>.*?)</ul>", re.S)
_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
_FY = re.compile(r"FY\s*(\d{4})")
_NOTICE = re.compile(r'href="([^"]*notice-files/(NOT-[A-Z]{2}-\d{2}-\d{3})\.html)"')
_PERIOD = re.compile(r"^(?P<from>[A-Z][a-z]+ \d{1,2}, \d{4}) through (?P<to>[A-Z][a-z]+ \d{1,2}, \d{4})\s*\((?P<level>Executive Level [IVX]+)\):\s*\$(?P<amount>[\d,]+)")

mcp = MCPServer(
    "nihdates",
    instructions="NIH's standard application due dates by activity code (nihdates_due), what happens in each of the three cycles (nihdates_cycles), and the salary cap by fiscal year and award date (nihdates_salary_cap), read from grants.nih.gov's own pages with their links. Read nihdates_index first.",
)


def text(fragment: str | None) -> str:
    return _WS.sub(" ", htmlmod.unescape(_TAG.sub(" ", fragment or ""))).strip()


def updated(page: str) -> str | None:
    m = _UPDATED.search(text(page))
    return m.group(1) if m else None


def tables(page: str) -> list[list[list[str]]]:
    out = []
    for t in _TABLE.findall(page):
        rows = [[text(c) for c in _TD.findall(r)] for r in _TR.findall(t)]
        out.append([r for r in rows if any(r)])
    return out


def parse_due(page: str) -> dict:
    """The due dates table as rows: the activity codes, which applications (new, renewal, resubmission, revision),
    the program, and the three cycle dates; and the cycles table as rows by what happens."""
    tabs = tables(page)
    due_rows, cycle_rows = [], []
    for t in tabs:
        if not t:
            continue
        head = " ".join(t[0]).lower()
        if "activity" in head and "cycle i due" in head:
            for r in t[1:]:
                if len(r) < 5:
                    continue
                if len(r) > 5:  # a row with a form column spliced in (U01 'PHS 398'): the dates are the last three cells
                    r = r[:2] + r[-3:]
                codes_cell = r[0]
                kinds = sorted({k.lower() for k in _KINDS.findall(codes_cell)}, key=["all", "new", "renewal", "resubmission", "revision"].index)
                codes = [c.replace(" series", " series").replace(" Series", " series") for c in _CODE.findall(codes_cell)]
                due_rows.append({"activity_codes": codes, "codes_text": codes_cell, "applications": kinds or ["all"], "program": r[1],
                                 "cycle_1": r[2], "cycle_2": r[3], "cycle_3": r[4]})
        elif "cycle i" in head and "cycle ii" in head:
            for r in t[1:]:
                if len(r) >= 4:
                    cycle_rows.append({"what": r[0], "cycle_1": r[1], "cycle_2": r[2], "cycle_3": r[3]})
    body = text(page)
    aids = None
    m = re.search(r"(We no longer have dedicated AIDS application due dates[^.]*\.[^.]*\.)", body)
    if m:
        aids = m.group(1)
    return {"due": due_rows, "cycles": cycle_rows, "aids_note": aids, "updated": updated(page)}


def _date(s: str) -> str | None:
    try:
        return datetime.strptime(s, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def parse_cap(page: str) -> list[dict]:
    """The salary cap page's fiscal years, newest first: each with its Guide notice and the periods of award issue
    dates with the Executive Level and the amount."""
    out = []
    for m in _FY_H3.finditer(page):
        heading = text(m.group("h"))
        fy = _FY.search(heading)
        if not fy:
            continue
        notice = _NOTICE.search(m.group("h"))
        periods = []
        for li in _LI.findall(m.group("ul")):
            t = text(li)
            pm = _PERIOD.match(t)
            if pm:
                periods.append({"from": _date(pm.group("from")), "to": _date(pm.group("to")), "level": pm.group("level"), "amount_usd": int(pm.group("amount").replace(",", "")), "text": t})
            else:
                periods.append({"text": t})
        out.append({"fiscal_year": int(fy.group(1)), "heading": heading, "notice": notice.group(2) if notice else None,
                    "notice_link": (SITE + notice.group(1) if notice.group(1).startswith("/") else notice.group(1)) if notice else None, "periods": periods})
    return out


def cap_on(caps: list[dict], day: date) -> dict | None:
    for fy in caps:
        for p in fy["periods"]:
            if p.get("from") and p.get("to") and p["from"] <= day.isoformat() <= p["to"]:
                return {**p, "fiscal_year": fy["fiscal_year"], "notice": fy["notice"], "notice_link": fy["notice_link"]}
    return None


async def _due() -> dict:
    return await _cache.remember("due", DAY, lambda: _load(DUE_URL, parse_due))


async def _cap() -> dict:
    return await _cache.remember("cap", DAY, lambda: _load(CAP_URL, lambda p: {"years": parse_cap(p), "updated": updated(p)}))


async def _load(url: str, parse) -> dict:
    page = await get_text(url)
    out = parse(page)
    if not (out.get("due") or out.get("years")):
        raise ValueError(f"the page at {url} has none of the rows this tool reads today; NIH may have reorganised it")
    return out


def _src(url: str, upd: str | None) -> dict:
    return {"url": url, "page_updated": upd, "read": date.today().isoformat(), "note": "The page is the authority; a funding opportunity's own due dates override the standard ones."}


@mcp.tool(name="nihdates_index", annotations=_READ_ONLY)
async def nihdates_index() -> dict:
    """How to use the NIH dates tools. READ THIS FIRST: what a standard due date is and is not, how the cycles work, how the salary cap applies."""
    return {
        "upstream": f"Two pages on grants.nih.gov, read as published and cached a day: the standard due dates at {DUE_URL} and the salary cap summary at {CAP_URL}",
        "workflow": ["nihdates_due with an activity code (R01, R21, K99, F31, 'T series') for its Cycle I, II and III due dates and which applications (new; renewal, resubmission, revision) each date is for",
                     "nihdates_cycles for what follows a due date: the review months, the council round and the earliest project start, by cycle",
                     "nihdates_salary_cap for the Executive Level II cap on salary charged to an award, by the award's issue date; no argument for the cap in force today and every year's, a fiscal year for that year's periods"],
        "notes": ["Standard due dates apply only when a funding opportunity says so; check the opportunity (the nihguide server reads notices and the grants server opportunities). AIDS applications no longer have their own dates (NOT-OD-26-029).",
                  "A due date on a weekend or federal holiday moves to the next business day; a date falls at 5:00 p.m. local time of the applicant organisation. The page's dates are the nominal ones.",
                  "The salary cap is the amount of an individual's salary that may be charged to an NIH grant or cooperative agreement, prorated for effort; the rate in force is by the date the award was issued, not the budget period. Since FY 2025 it applies to indirect salaries too (NOT-OD-25-025).",
                  "Each answer carries the page URL and the date the page says it was updated; cite both with any date or amount."],
        "link": DUE_URL,
    }


@mcp.tool(name="nihdates_due", annotations=_READ_ONLY)
async def nihdates_due(activity_code: str = "") -> dict:
    """NIH's standard application due dates: for an activity code, or the whole table, with the Cycle I, II and III dates and which applications each row is for.

    Args:
        activity_code: An activity code such as 'R01', 'R21', 'K08', 'F31', 'R15', 'U01', or a series ('K series', 'T series'); empty for every row.
    """
    try:
        d = await _due()
    except ValueError as e:
        return {"error": str(e), "source": _src(DUE_URL, None)}
    q = activity_code.strip().upper()
    rows = d["due"]
    if q:
        series = q[0] + " SERIES" if len(q) >= 2 and q[1:].isdigit() else None
        rows = [r for r in rows if any(q == c.upper() or (series and c.upper() == series) for c in r["activity_codes"]) or q in r["codes_text"].upper()]
        if not rows:
            return {"activity_code": q, "total": 0, "due": [], "note": "No standard due date row names this code: the opportunity's own dates apply, or the code is not an application activity code. The whole table is nihdates_due with no argument.", "source": _src(DUE_URL, d["updated"])}
    return {"activity_code": q or None, "total": len(rows), "due": rows, "aids_note": d["aids_note"], "source": _src(DUE_URL, d["updated"])}


@mcp.tool(name="nihdates_cycles", annotations=_READ_ONLY)
async def nihdates_cycles() -> dict:
    """NIH's three review and award cycles: the span of due dates, the scientific merit review months, the advisory council round and the earliest project start date for each."""
    try:
        d = await _due()
    except ValueError as e:
        return {"error": str(e), "source": _src(DUE_URL, None)}
    return {"cycles": d["cycles"], "source": _src(DUE_URL, d["updated"]), "note": "Cycle I is the dates from January 25 to May 7, Cycle II May 25 to September 7, Cycle III September 25 to January 7, as the page states them; an application's cycle is the one its due date falls in."}


@mcp.tool(name="nihdates_salary_cap", annotations=_READ_ONLY)
async def nihdates_salary_cap(fiscal_year: int | None = None) -> dict:
    """The NIH salary cap, the Executive Level II amount above which salary may not be charged to an award, by the award's issue date, with the Guide notice for each fiscal year.

    Args:
        fiscal_year: A federal fiscal year (2026 is October 2025 to September 2026) for that year's periods; empty for the cap in force today and every year since 1990.
    """
    try:
        c = await _cap()
    except ValueError as e:
        return {"error": str(e), "source": _src(CAP_URL, None)}
    years = c["years"]
    today = date.today()
    if fiscal_year:
        years = [y for y in years if y["fiscal_year"] == int(fiscal_year)]
        if not years:
            return {"fiscal_year": fiscal_year, "error": f"the page lists no FY {fiscal_year}; it runs FY {c['years'][-1]['fiscal_year']} to FY {c['years'][0]['fiscal_year']}", "source": _src(CAP_URL, c["updated"])}
    in_force = cap_on(c["years"], today)
    latest = c["years"][0] if c["years"] else None
    out = {"today": today.isoformat(), "in_force": in_force, "years": years, "source": _src(CAP_URL, c["updated"]),
           "note": "Apply the cap in force on the award's issue date (the Notice of Award date), prorated by the person's effort; a budget for a future award uses the current amount and says so. Institutional base salary above the cap is the institution's own cost."}
    if in_force is None and latest:
        out["latest"] = {"fiscal_year": latest["fiscal_year"], "period": latest["periods"][-1] if latest["periods"] else None, "notice": latest["notice"], "notice_link": latest["notice_link"]}
        out["in_force_note"] = f"The page lists no period that covers today; its latest is FY {latest['fiscal_year']}. NIH states what applies between a fiscal year's start and its notice in that notice (the nihguide server reads it); say the figure is the latest posted."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# Arguments are an activity code or a fiscal year, both the person's own words; no identifier from a list (#40).
