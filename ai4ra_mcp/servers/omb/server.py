"""omb: the Office of Management and Budget's memoranda to agencies, the M-YY-NN series, as OMB lists them.

Upstream: OMB's memoranda page on whitehouse.gov (the current administration's, 2025 on) and the same page as the
National Archives preserved it for the prior administration (bidenwhitehouse.archives.gov, whose list runs from
the late 1990s to January 2025, 691 memoranda with the current page's when read 2026-10-16), both read as HTML and
cached a day. Each lists, under a heading per year, the memoranda with number, title, date and
a link to the PDF; nothing here reads the PDFs (the fetch tools on the ai4ra server do). A memorandum's status is not
on the list: a later memorandum may rescind or amend it, so each entry carries the later memoranda whose titles name
its number. The index reports the years the two lists cover as read. Every answer links the list page it came from
and the PDF.
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
CURRENT = "https://www.whitehouse.gov/omb/information-resources/guidance/memoranda/"
ARCHIVE = "https://bidenwhitehouse.archives.gov/omb/information-for-agencies/memoranda/"
SOURCES = {"current": CURRENT, "archive": ARCHIVE}
# whitehouse.gov answers a browser's User-Agent; the generic one is refused by its edge.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai4ra-mcp/0.1; +https://github.com/ui-insight/ai4ra-mcp)"}
ROWS, MAX_ROWS = 25, 200
_cache = TTLCache()

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_YEAR_H2 = re.compile(r"<h2[^>]*>\s*(?:<[^>]+>\s*)*Memoranda\s+(\d{4})\s*(?:<[^>]+>\s*)*</h2>(?P<body>.*?)(?=<h2|</main>|$)", re.S)
_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
_ENTRY = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>(?P<rest>.*)', re.S)
_NUMBER = re.compile(r"\b(M-\d{2}-\d{1,3}[A-Za-z]?)\b")
_DATE = re.compile(r"\(([A-Z][a-z]+\.? \d{1,2}, \d{4})\)")
_PAGES = re.compile(r"\((\d+) Pages?, ([\d.]+ ?[KM]B)\)")

mcp = MCPServer(
    "omb",
    instructions="OMB's memoranda to agencies (M-26-01, M-24-11): the list by year with number, title, date and PDF link (omb_memoranda, by year or words), and one memorandum by number with the later memoranda that name it (omb_memorandum). From whitehouse.gov and the archived prior-administration page. Read omb_index first.",
)


def text(fragment: str | None) -> str:
    return _WS.sub(" ", htmlmod.unescape(_TAG.sub(" ", fragment or ""))).strip()


def _date(s: str) -> str | None:
    for fmt in ("%B %d, %Y", "%b. %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_list(page: str, source: str) -> list[dict]:
    """The memoranda under each 'Memoranda YYYY' heading: number, title, date, PDF link, pages when the page says."""
    out = []
    for ym in _YEAR_H2.finditer(page):
        year = int(ym.group(1))
        for li in _LI.findall(ym.group("body")):
            e = _ENTRY.search(li)
            if not e:
                continue
            title = text(e.group("title"))
            num = _NUMBER.search(title) or _NUMBER.search(text(li))
            if not num:
                continue
            rest = text(e.group("rest"))
            dm = _DATE.search(rest) or _DATE.search(title)  # a few entries carry the date inside the link text
            if dm and dm.string is title:
                title = title.replace(dm.group(0), "").strip()
            pm = _PAGES.search(rest)
            out.append({"number": num.group(1).upper(), "title": title.replace(num.group(1), "", 1).strip(" :–-—"), "date": _date(dm.group(1)) if dm else None,
                        "date_text": dm.group(1) if dm else None, "year": year, "pdf": e.group("href"), "pages": int(pm.group(1)) if pm else None,
                        "source": source, "list_page": SOURCES[source]})
    return out


def merge(current: list[dict], archive: list[dict]) -> list[dict]:
    """Both lists as one, newest first, a number listed on both pages kept from whitehouse.gov; and each entry's
    referenced_by, the later memoranda whose titles name its number (a rescission or amendment, usually)."""
    seen: dict[str, dict] = {}
    for m in current + archive:
        seen.setdefault(m["number"], m)
    rows = sorted(seen.values(), key=lambda m: (m["date"] or f"{m['year']}-00-00", m["number"]), reverse=True)
    by_title = [(m["number"], set(_NUMBER.findall(m["title"].upper()))) for m in rows]
    for m in rows:
        refs = [n for n, mentioned in by_title if m["number"] in mentioned and n != m["number"]]
        if refs:
            m["referenced_by"] = refs
    return rows


async def _all() -> dict:
    async def load():
        out: dict = {"errors": {}}
        lists = {}
        for key, url in SOURCES.items():
            try:
                lists[key] = parse_list(await get_text(url, headers=HEADERS), key)
                if not lists[key]:
                    out["errors"][key] = f"the page at {url} lists no memoranda under a 'Memoranda <year>' heading today; OMB may have changed its layout"
                    lists[key] = []
            except ValueError as e:
                out["errors"][key] = str(e)
                lists[key] = []
        if not lists.get("current") and not lists.get("archive"):
            raise ValueError("neither memoranda page answered: " + "; ".join(out["errors"].values()))
        out["rows"] = merge(lists.get("current", []), lists.get("archive", []))
        return out
    return await _cache.remember("all", DAY, load)


def _src(errors: dict) -> dict:
    return {"lists": SOURCES, "read": date.today().isoformat(), "errors": errors or None,
            "note": "The list pages are the authority for what exists; a memorandum's text is its PDF, and whether it is still in force is in later memoranda (referenced_by) or not stated."}


@mcp.tool(name="omb_index", annotations=_READ_ONLY)
async def omb_index() -> dict:
    """How to use the OMB memoranda tools. READ THIS FIRST: what the list covers and does not, how a memorandum is numbered, what 'referenced_by' means."""
    try:
        d = await _all()
        years = sorted({m["year"] for m in d["rows"]})
        span = f"{years[0]} to {years[-1]}, {len(d['rows'])} memoranda" if years else None
    except ValueError as e:
        d, span = {"errors": {"all": str(e)}}, None
    return {
        "upstream": f"OMB's memoranda page at {CURRENT} (the current administration) and the archived prior page at {ARCHIVE} (to January 2025), read as published and cached a day",
        "coverage": span or "the lists could not be read today; see errors",
        "workflow": ["omb_memoranda with a year, or words of a title ('financial assistance', '2 CFR', 'research security', 'rescission'), for the matching memoranda newest first",
                     "omb_memorandum with a number (M-24-11) for that entry and the later memoranda that name it in their titles",
                     "the PDF itself through the ai4ra server's fetch tools, with the pdf link"],
        "notes": ["A number is M-<fiscal year>-<sequence>: M-24-11 is the eleventh of fiscal 2024. OMB's Uniform Guidance revisions (2 CFR 200) and research-security guidance arrive as memoranda; the circulars (A-21, A-110, A-133 as they were) are a separate page not read here.",
                  "The list says nothing about whether a memorandum is in force; a later 'Rescission of M-xx-xx' or 'Amendment to' names it, and referenced_by collects those. Read the later one.",
                  "Coverage is what the two lists hold, stated above; a number from a year before the first is not here, and the archived list is as the National Archives froze it in January 2025.",
                  "Cite as 'OMB Memorandum M-24-11, <title> (<date>)' with the PDF link."],
        "link": CURRENT,
        "errors": d.get("errors") or None,
    }


@mcp.tool(name="omb_memoranda", annotations=_READ_ONLY)
async def omb_memoranda(year: int | None = None, query: str = "", rows: int = ROWS) -> dict:
    """OMB memoranda newest first, by the year they were issued or by words of the title, each with number, date and PDF link.

    Args:
        year: A calendar year (the heading the list files it under), e.g. 2024; empty for all years.
        query: Words that must all appear in the title (case-insensitive), e.g. 'federal financial assistance'; empty for every memorandum.
        rows: How many to return, 1-200. Default 25.
    """
    try:
        d = await _all()
    except ValueError as e:
        return {"error": str(e), "source": _src({})}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    words = [w for w in re.findall(r"[a-z0-9\-\.]+", query.lower()) if w]
    found = [m for m in d["rows"] if (not year or m["year"] == int(year)) and all(w in m["title"].lower() or w in m["number"].lower() for w in words)]
    return {"year": year, "query": query or None, "total": len(found), "returned": min(rows, len(found)), "memoranda": found[:rows], "source": _src(d["errors"])}


@mcp.tool(name="omb_memorandum", annotations=_READ_ONLY)
async def omb_memorandum(number: str) -> dict:
    """One OMB memorandum by number: its title, date, PDF link and the later memoranda whose titles name it (a rescission or amendment).

    Args:
        number: The memorandum number, e.g. 'M-24-11' (also 'M 24 11' or '24-11').
    """
    n = re.sub(r"[^0-9A-Za-z]+", "-", number.strip().upper()).strip("-")
    if not n.startswith("M-"):
        n = "M-" + n
    m2 = re.fullmatch(r"M-(\d{2})-(\d{1,3})([A-Z]?)", n)
    if not m2:
        return {"error": "number must look like M-24-11"}
    n = f"M-{m2.group(1)}-{int(m2.group(2)):02d}{m2.group(3)}"
    try:
        d = await _all()
    except ValueError as e:
        return {"error": str(e), "source": _src({})}
    hit = next((m for m in d["rows"] if m["number"] == n), None)
    if not hit:
        return {"number": n, "error": f"{n} is not on either list; omb_index says the years they cover, and a number can be unissued or withdrawn", "source": _src(d["errors"])}
    refs = [m for m in d["rows"] if m["number"] in hit.get("referenced_by", [])]
    return {**hit, "referenced_by": refs, "source": _src(d["errors"])}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A memorandum's number is the person's own; omb_memoranda lists them but the number is public and cited, not a list's handle (#40).
