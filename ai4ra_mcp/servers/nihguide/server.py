"""nihguide: the NIH Guide for Grants and Contracts, NIH's publication of record for notices and funding opportunities.

Upstream: the Guide's own search service and pages at grants.nih.gov (no key). The Guide search page
(grants.nih.gov/funding/searchguide/) is an app that reads a JSON service, found in the app's bundle on 2026-10-16:
GET <service>/data?perpage=&from=&sort=&type=&query=&parentic=&primaryic=&doctype=&daterange=MMDDYYYY-MMDDYYYY&...,
an Elasticsearch result (hits.total, hits.hits[]._source with docnum, title, type, doctype, reldate, expdate, parentIC,
primaryIC, noticeSubject, ac, purpose). type is 'notices' for the Guide's notices (NOT-...; 16,800 on 2026-10-16) and
'active', 'activenosis', 'expired', 'expirednosis' for notices of funding opportunity (RFA, PA, PAR, PAS) and notices
of special interest (NOSI), the four together being every NOFO the Guide has carried. The service is the page's own and
undocumented; a change to it is a change to this server. A notice's text is its HTML page
(grants.nih.gov/grants/guide/notice-files/NOT-OD-25-163.html), read for its labelled fields and its Purpose; the week's
notices are the weekly index page (WeeklyIndexMobile.cfm, WeekEnding=MM-DD-YYYY for an earlier week). NIH posts new
NOFOs to Grants.gov as of FY2026 (the grants server has them with their packages); the Guide still lists them.
Searches are cached an hour, pages a day.
"""

from __future__ import annotations

import html as _html
import re
from datetime import date
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
SERVICE = "https://vtbgfslh0k.execute-api.us-east-1.amazonaws.com/prod"
GUIDE = "https://grants.nih.gov/grants/guide/"
SEARCH_PAGE = "https://grants.nih.gov/funding/searchguide/index.html"
WEEKLY = GUIDE + "WeeklyIndexMobile.cfm"
KINDS = {"notices": "notices", "opportunities": "active,activenosis,expired,expirednosis", "open": "active,activenosis", "all": "notices,active,activenosis,expired,expirednosis"}
ROWS, MAX_ROWS = 20, 100
_NUMBER = re.compile(r"^(NOT|RFA|PA|PAR|PAS)-[A-Z]{2,4}-\d{2}-\d{3,4}[A-Z]?$")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_BLOCK_END = re.compile(r"<(?:br|/p|/div|/li|/h[1-6]|/tr|/td|/span)\b[^>]*>", re.I)
HEADINGS = ("Key Dates", "Related Announcements", "Issued by", "Purpose", "Inquiries")
_cache = TTLCache()

mcp = MCPServer(
    "nihguide",
    instructions="The NIH Guide for Grants and Contracts: notices and funding opportunities by words, institute, kind and dates (nihguide_search), one notice's text by number (nihguide_notice), the week's notices (nihguide_weekly). No key. Read nihguide_index first.",
)


def text(fragment: str) -> str:
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", fragment))).strip()


def doc_link(docnum: str, filename: str | None = None) -> str | None:
    """The Guide page for a document: notice-files for NOT-, rfa-files for RFA-, pa-files for PA-, PAR- and PAS-."""
    if not docnum:
        return None
    folder = {"NOT": "notice-files", "RFA": "rfa-files"}.get(docnum.split("-")[0], "pa-files")
    return f"{GUIDE}{folder}/{filename or docnum + '.html'}"


def _date(v) -> str | None:
    s = str(v or "")
    return s[:10] if re.match(r"\d{4}-\d{2}-\d{2}", s) else None


def slim_hit(h: dict) -> dict:
    s = h.get("_source") or {}
    purpose = text(str(s.get("purpose") or ""))
    purpose = re.sub(r"^p(?=[A-Z])", "", purpose)
    return {"number": s.get("docnum"), "title": s.get("title"), "kind": "notice" if s.get("type") == "notices" else "opportunity", "status": s.get("type") if s.get("type") != "notices" else None,
            "doctype": s.get("doctype"), "notice_subject": s.get("noticeSubject") if s.get("noticeSubject") not in (None, "None") else None,
            "released": _date(s.get("reldate")), "expires": _date(s.get("expdate")), "institute": s.get("primaryIC") if s.get("primaryIC") not in (None, "None") else None, "parent": s.get("parentIC"),
            "activity_codes": s.get("ac") if isinstance(s.get("ac"), list) else None, "clinical_trials": s.get("clinicaltrials") or None,
            "purpose": purpose[:300] + (" …" if len(purpose) > 300 else "") or None, "link": doc_link(s.get("docnum"), s.get("filename"))}


def parse_notice(page: str) -> dict:
    """A notice page read to its number, title, dates, related announcements, issuing organisations, purpose and inquiries."""
    lines = [text(x) for x in _BLOCK_END.split(page)]
    lines = [x for x in lines if x]
    out: dict = {"number": None, "title": None, "release_date": None, "expiration_date": None, "related_announcements": [], "issued_by": [], "purpose": [], "inquiries": []}
    m = re.search(r'<span class="noticenum">(.*?)</span>', page, re.S)
    if m:
        out["number"] = text(m.group(1))
    t = re.search(r'<span class="title">(.*?)</span>', page, re.S) or re.search(r"<title>(.*?)</title>", page, re.S)
    if t:
        out["title"] = text(t.group(1)).split(" | ")[0] or None
    section = None
    for i, line in enumerate(lines):
        if line in HEADINGS:
            section = line
            continue
        low = line.lower()
        if low.startswith("notice number:"):
            out["number"] = out["number"] or line.split(":", 1)[1].strip() or (lines[i + 1] if i + 1 < len(lines) else None)
            continue
        if low.startswith("release date:"):
            v = line.split(":", 1)[1].strip()
            out["release_date"] = v or (lines[i + 1] if i + 1 < len(lines) else None)
            continue
        if low.startswith("expiration date:"):
            v = line.split(":", 1)[1].strip()
            out["expiration_date"] = v or (lines[i + 1] if i + 1 < len(lines) else None)
            continue
        if section == "Key Dates" and (out["release_date"] == line or out["expiration_date"] == line):
            continue
        if section == "Related Announcements":
            if line != "None":
                out["related_announcements"].append(line)
        elif section == "Issued by":
            out["issued_by"].append(line)
        elif section == "Purpose":
            out["purpose"].append(line)
        elif section == "Inquiries":
            if "@" not in line and "[email" not in line:
                out["inquiries"].append(line)
    for k in ("release_date", "expiration_date"):
        if out[k] in HEADINGS:
            out[k] = None
    return out


def parse_weekly(page: str) -> dict:
    """The weekly index page read to its date and its groups of notices (title, number, organisation, link)."""
    m = re.search(r'<div class="weekdate">(.*?)</div>', page, re.S) or re.search(r"Weekly Index for ([^<|]+)", page)
    week = text(m.group(1)) if m else None
    groups = []
    for head, body in re.findall(r'<h3 class="weeklyindex">(.*?)</h3>(.*?)(?=<h3 class="weeklyindex">|</div>\s*</div>\s*</div>|$)', page, re.S):
        items = []
        for li in re.findall(r"<li>(.*?)</li>", body, re.S):
            a = re.search(r'<a href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
            divs = [text(d) for d in re.findall(r"<div[^>]*>(.*?)</div>", li, re.S)]
            number = next((d.strip("()") for d in divs if re.fullmatch(r"\((?:NOT|RFA|PA|PAR|PAS)-[A-Z0-9-]+\)", d)), None)
            org = next((d for d in divs if d and not d.startswith("(")), None)
            if a:
                items.append({"number": number, "title": text(a.group(2)), "organization": org, "link": a.group(1)})
        if items:
            groups.append({"group": text(head), "notices": items})
    return {"week_ending": week, "groups": groups, "total": sum(len(g["notices"]) for g in groups)}


def _mmddyyyy(v: str, label: str) -> str:
    try:
        d = date.fromisoformat(v.strip())
    except ValueError:
        raise ValueError(f"{label} must be a date, YYYY-MM-DD") from None
    return d.strftime("%m%d%Y")


@mcp.tool(name="nihguide_index", annotations=_READ_ONLY)
async def nihguide_index() -> dict:
    """How to use the NIH Guide tools. READ THIS FIRST: what the Guide carries, how notices and opportunities are numbered, where NOFOs now live."""
    return {
        "upstream": f"The NIH Guide for Grants and Contracts at {GUIDE}: its own search service (the one behind {SEARCH_PAGE}, undocumented), its notice pages and its weekly index; no key",
        "workflow": ["nihguide_search with words, a kind (notices, opportunities, open, all), an institute and dates: numbers, titles, dates, subjects and a line of purpose",
                     "nihguide_notice with a notice number (NOT-OD-25-163) for the notice's text: dates, related announcements, who issued it, its purpose",
                     "nihguide_weekly for this week's notices by group, or an earlier week by its Friday"],
        "notes": ["Numbers: NOT-<IC>-<yy>-<nnn> is a notice (policy, information, a request for information, a notice of special interest NOSI, a correction); RFA-, PA-, PAR- and PAS- are notices of funding opportunity. The IC code names the issuing institute (OD the Office of the Director).",
                  "As of fiscal 2026 NIH posts new NOFOs on Grants.gov (the grants server, with the application package); the Guide still lists them and carries every notice. For a NOFO's full text use the Guide link here or grants_gov_opportunity.",
                  "kind: notices for NOT- documents; opportunities for every NOFO and NOSI the Guide has carried, open or expired; open for the active ones; all for everything. An institute filter takes the code (OD, NIAID, NCI) as the Guide's primary IC.",
                  "A notice's Purpose is the policy; the dates are as written on the notice. Release dates are when NIH published; an expiration date on a NOFO is its last due date.",
                  "Cite a notice by number with its link; a notice newer than the Grants Policy Statement's revision governs where they differ (the nihgps server)."],
        "caveats": ["The search service is the Guide page's own and undocumented; a change to it is a change to this server, and the page itself is the fallback.",
                    "Email addresses on notice pages are hidden by the site's protection and are not read; the notice's link shows them."],
        "link": SEARCH_PAGE,
    }


@mcp.tool(name="nihguide_search", annotations=_READ_ONLY)
async def nihguide_search(query: str = "", kind: str = "notices", institute: str = "", from_date: str = "", to_date: str = "", rows: int = ROWS, start: int = 0) -> dict:
    """Notices and funding opportunities in the NIH Guide by words, kind, institute and release dates, newest first (by relevance when words are given).

    Args:
        query: Words in the title or purpose, e.g. 'salary cap', 'data management sharing', 'foreign component'.
        kind: notices (default), opportunities (every NOFO and NOSI), open (active NOFOs and NOSIs), or all.
        institute: The issuing IC's code, e.g. 'OD', 'NIAID', 'NCI'; empty for all.
        from_date: Earliest release date, YYYY-MM-DD.
        to_date: Latest release date, YYYY-MM-DD.
        rows: Results a page, 1-100. Default 20.
        start: Offset of the first result for the next page. Default 0.
    """
    k = kind.strip().lower()
    if k not in KINDS:
        return {"error": f"kind must be one of {', '.join(KINDS)}"}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    start = max(0, int(start or 0))
    try:
        lo = _mmddyyyy(from_date, "from_date") if from_date.strip() else "01011991"
        hi = _mmddyyyy(to_date, "to_date") if to_date.strip() else date.today().strftime("%m%d%Y")
    except ValueError as e:
        return {"error": str(e)}
    params = {"perpage": rows, "from": start, "sort": "_score" if query.strip() else "reldate:desc", "type": KINDS[k], "query": query.strip(),
              "parentic": "all", "primaryic": institute.strip().upper() or "all", "activitycodes": "all", "doctype": "all", "parentfoa": "all",
              "daterange": f"{lo}-{hi}", "clinicaltrials": "all", "fields": "all", "spons": "true", "apptype": "all", "noticeSubject": "all", "category": "all"}
    key = "search:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(key, HOUR, lambda: get_json(f"{SERVICE}/data", params))
    except ValueError as e:
        return {"error": str(e), "upstream": SERVICE, "note": "The Guide page's own search service; try the words on " + SEARCH_PAGE}
    hits = (((body or {}).get("data") or {}).get("hits") or {}) if isinstance(body, dict) else {}
    if not isinstance(hits.get("hits"), list):
        return {"error": "the Guide's search service did not return its hits (the service changed)", "upstream": SERVICE}
    total = hits.get("total")
    total = total.get("value") if isinstance(total, dict) else total
    results = [slim_hit(h) for h in hits["hits"]]
    out = {"query": {k2: v for k2, v in (("query", query.strip()), ("kind", k), ("institute", institute.strip().upper()), ("from_date", from_date.strip()), ("to_date", to_date.strip())) if v},
           "total": total, "start": start, "returned": len(results), "results": results, "link": SEARCH_PAGE}
    if isinstance(total, int) and start + len(results) < total:
        out["next_start"] = start + len(results)
    return out


@mcp.tool(name="nihguide_notice", annotations=_READ_ONLY)
async def nihguide_notice(number: str) -> dict:
    """One NIH Guide notice by number: title, release and expiration dates, related announcements, who issued it, its purpose, whom to ask.

    Args:
        number: The notice number, e.g. 'NOT-OD-25-163'. A NOFO number (RFA-, PA-, PAR-, PAS-) is read for the same fields where its page has them.
    """
    n = number.strip().upper()
    if not _NUMBER.match(n):
        return {"error": "number must be a Guide number like NOT-OD-25-163 or PAR-26-012"}
    url = doc_link(n)
    try:
        page = await _cache.remember(f"notice:{n}", DAY, lambda: get_text(url))
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no Guide page for {n} at {url}; check the number (a NOFO may be on Grants.gov only)", "link": url}
        return {"error": str(e), "link": url}
    found = parse_notice(page)
    if not found["number"] and not found["purpose"]:
        return {"error": f"the page for {n} carried no notice fields (the page layout changed, or it is a NOFO in another layout)", "link": url}
    return {**found, "number": found["number"] or n, "link": url}


@mcp.tool(name="nihguide_weekly", annotations=_READ_ONLY)
async def nihguide_weekly(week_ending: str = "") -> dict:
    """The NIH Guide's weekly index: the notices NIH released in a week, by group, with numbers, titles and issuing organisations.

    Args:
        week_ending: The week's Friday, YYYY-MM-DD; the current week when empty.
    """
    params = None
    if week_ending.strip():
        try:
            d = date.fromisoformat(week_ending.strip())
        except ValueError:
            return {"error": "week_ending must be a date, YYYY-MM-DD"}
        params = {"WeekEnding": d.strftime("%m-%d-%Y")}
    try:
        page = await _cache.remember(f"weekly:{week_ending.strip()}", HOUR, lambda: get_text(WEEKLY, params))
    except ValueError as e:
        return {"error": str(e), "link": WEEKLY}
    found = parse_weekly(page)
    if not found["week_ending"]:
        return {"error": "the weekly index page carried no week (the page layout changed)", "link": WEEKLY}
    return {**found, "link": WEEKLY + (f"?WeekEnding={params['WeekEnding']}" if params else "")}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A notice number the model names waits on a search or the weekly index that returned it (#40); one a person gives passes as given.
given(mcp, {"nihguide_notice": {"number": "nihguide_search"}})
