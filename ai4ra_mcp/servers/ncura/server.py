"""ncura: the National Council of University Research Administrators' calendar of meetings, conferences and workshops.

Upstream: the public event listing behind the calendar page at https://www.ncura.edu/Education/Calendar.aspx, an
iframe onto NCURA's association-management system (cvweb, Eventsdll.dll): EventList gives the events on the web
from a start date as an HTML table (title, subtitle, dates, a registration flag, the event type and the check
registration form), and EventInfo?sessionaltcd=<code> one event with its dates, deadlines, fees, description
and location. Neither needs a login; the member side (Collaborate, the magazine, the directory) is behind one
and is not read. NCURA shows nine upcoming events today (2026-10-16) and 46 with the past year. The list is cached
an hour, an event a day. Every answer links the event's page on ncura.edu and the calendar.
"""

from __future__ import annotations

import html as htmlmod
import re
from datetime import date, datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
SITE = "https://www.ncura.edu"
CALENDAR = f"{SITE}/Education/Calendar.aspx"
LIST = f"{SITE}/cvweb/cgi-bin/Eventsdll.dll/EventList"
INFO = f"{SITE}/cvweb/cgi-bin/eventsdll.dll/EventInfo"
PAGE = f"{SITE}/Education/MeetingsConferences/EventInfo.aspx"
# The site's own iframe asks for events from yesterday on, shown on the web, 200 at most; 'year' reaches back 400 days.
WHEN = {"upcoming": "-1", "year": "-400"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai4ra-mcp/0.1; +https://github.com/ui-insight/ai4ra-mcp)"}
ROWS, MAX_ROWS = 50, 200
_cache = TTLCache()

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_ROW = re.compile(r"<tr>\s*<td>(?P<cell>.*?)</td>\s*<td id=\"dates_(?P<code>[^\"]+)\">(?P<dates>[^<]*)</td>\s*<td class='text-center'>(?P<flags>.*?)</td>", re.S)
_LINK = re.compile(r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<text>.*?)</a>', re.S)
_REG = re.compile(r'if\("(?P<flag>\d)" == "0" \|\| "\d" == "1"\)')
_TYPE = re.compile(r'if\("(?P<type>[A-Z0-9]*)" == "Online"\)')
_FEATURED = re.compile(r'if\("(?P<flag>[NY])" == "Y"\)')
_EXTERNAL = re.compile(r'if\( "(?P<url>[^"]*)" != "" \)')
_DATES = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})(?:\s*-\s*(\d{1,2}/\d{1,2}/\d{4}))?")
_FEE = re.compile(r"<tr>\s*<td[^>]*>(?P<what>.*?)</td>\s*<td class=\"text-right\">(?P<amount>.*?)</td>\s*</tr>", re.S)
_CODE = re.compile(r"^[A-Z0-9]{3,40}$")

mcp = MCPServer(
    "ncura",
    instructions="NCURA's calendar: the National Council of University Research Administrators' upcoming meetings, conferences, traveling and virtual workshops (ncura_events, by words, upcoming or the past year) and one event with its dates, registration deadlines, fees, description and location (ncura_event, by the code ncura_events gives). Public pages, no key or membership. Read ncura_index first.",
)


def text(fragment: str | None) -> str:
    return _WS.sub(" ", htmlmod.unescape(_TAG.sub(" ", fragment or ""))).strip()


def _iso(us: str | None) -> str | None:
    try:
        return datetime.strptime(us, "%m/%d/%Y").date().isoformat() if us else None
    except ValueError:
        return None


def _long(s: str | None) -> str | None:
    """'Thursday, October 08, 2026' as 2026-10-08."""
    m = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", s or "")
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat() if m else None
    except ValueError:
        return None


def parse_list(page: str) -> list[dict]:
    """The event table's rows: code, title, subtitle, dates, type, whether registration is open, links."""
    out = []
    for m in _ROW.finditer(page):
        cell, flags = m.group("cell"), m.group("flags")
        links = [(htmlmod.unescape(h), text(t)) for h, t in _LINK.findall(cell)]
        title = next((t for h, t in links if "EventInfo" in h), None) or text(cell.split("<br>")[0])
        after = cell.split("</a>", 1)[1] if "</a>" in cell else ""
        subtitle = text(after.split("<br>", 2)[1]) if after.count("<br>") >= 1 else None
        forms = [{"text": t, "url": h} for h, t in links if "EventInfo" not in h]
        dm = _DATES.search(m.group("dates"))
        reg, typ, feat, ext = _REG.search(flags), _TYPE.search(flags), _FEATURED.search(flags), _EXTERNAL.search(flags)
        code = m.group("code").strip()
        out.append({"code": code, "title": title, "subtitle": subtitle or None, "start": _iso(dm.group(1)) if dm else None, "end": _iso(dm.group(2) or dm.group(1)) if dm else None,
                    "dates": text(m.group("dates")) or None, "type": (typ.group("type") if typ else None) or None,
                    "registration": "open" if reg and reg.group("flag") in ("0", "1") else "closed" if reg else None,
                    "featured": bool(feat and feat.group("flag") == "Y"), "register_link": (ext.group("url") if ext else "") or None,
                    "check_form": forms[0] if forms else None, "link": f"{PAGE}?sessionaltcd={code}"})
    return out


def parse_event(page: str, code: str) -> dict:
    """One event's page: title, subtitle, dates, deadlines, fees, description, location, links."""
    h3 = re.search(r"<h3>(.*?)</h3>", page, re.S)
    dates = re.search(r'id="sessionDates".*?<span[^>]*>(.*?)</span>', page, re.S)
    lead = re.search(r"<p class='lead'>(.*?)</p>", page, re.S)
    early = re.search(r"Early Bird Discount Deadline:</span>(.*?)</p>", page, re.S)
    last = re.search(r"Registration Deadline:</span>(.*?)</p>", page, re.S)
    typ = _TYPE.search(page)
    check = re.search(r"Registering with a Check:</span>\s*<div>(.*?)</div>", page, re.S)
    form = _LINK.search(check.group(1)) if check else None
    details = re.search(r'<div class="tab-pane active" id="details">(.*?)<div class="tab-pane" id=', page, re.S)
    fees_block = re.search(r'<div id="(?P<which>isEARMA|notEARMA)" class="hide">(.*?)</div>', page, re.S)
    fees = []
    kind = "isEARMA" if typ and typ.group("type") == "EARMA" else "notEARMA"
    for blk in re.finditer(r'<div id="(isEARMA|notEARMA)" class="hide">(.*?)</div>', page, re.S):
        if blk.group(1) == kind:
            fees = [{"what": text(f.group("what")), "amount": text(f.group("amount"))} for f in _FEE.finditer(blk.group(2)) if text(f.group("what")) != "Price Description"]
    address = re.search(r"<address>(.*?)</address>", page, re.S)
    hotel = re.search(r'id="hotelInfoLink"[^>]*href="([^"]*)"', page)
    loc_lines = [text(ln) for ln in re.split(r"<br\s*/?>", re.sub(r"<!--.*?-->|<a[^>]*>.*?</a>", "", address.group(1), flags=re.S))] if address else []
    loc_lines = [ln for ln in loc_lines if ln]
    dtext = dates.group(1) if dates else ""
    parts = [p.strip() for p in text(dtext).split(" - ")]
    return {"code": code, "title": text(h3.group(1)).replace("Featured Event", "").strip() if h3 else None, "subtitle": text(lead.group(1)) if lead else None,
            "dates": text(dtext) or None, "start": _long(parts[0]) if parts else None, "end": _long(parts[-1]) if parts else None,
            "type": (typ.group("type") if typ else None) or None,
            "early_bird_deadline": _long(text(early.group(1))) if early else None, "registration_deadline": _long(text(last.group(1))) if last else None,
            "check_form": {"text": text(form.group("text")), "url": htmlmod.unescape(form.group("href"))} if form else None,
            "description": text(details.group(1))[:4000] if details else None, "fees": fees, "fees_note": None if fees_block else "the page lists no fees",
            "location": {"venue": loc_lines[0] if loc_lines else None, "address": loc_lines[1:] or None, "hotel_link": (hotel.group(1) if hotel else "") or None} if loc_lines else None,
            "link": f"{PAGE}?sessionaltcd={code}", "detail_page": f"{INFO}?sessionaltcd={code}"}


def matches(words: list[str], haystack: str) -> bool:
    """Every query word is a whole word of the text, singular or plural ('region vi' finds 'Regions VI & VII' and not 'Irving')."""
    tokens = set(re.findall(r"[a-z0-9]+", haystack.lower()))
    return all(w in tokens or w + "s" in tokens or (w.endswith("s") and w[:-1] in tokens) for w in words)


async def _list(when: str) -> list[dict]:
    async def load():
        params = {"sessionbegdate": f">getdate(){WHEN[when]}", "Range": "1/200", "ONWEBFLG": "Y", "SORT": "SESSIONBEGDATE"}
        page = await get_text(LIST, params, headers=HEADERS)
        rows = parse_list(page)
        if not rows and "Event Listing" not in page:
            raise ValueError(f"the event list at {LIST} has no event table today; NCURA may have changed its calendar")
        return rows
    return await _cache.remember(f"list:{when}", HOUR, load)


def _src(extra: dict | None = None) -> dict:
    return {"calendar": CALENDAR, "list": LIST, "read": date.today().isoformat(), **(extra or {}),
            "note": "NCURA's calendar is the authority; dates, deadlines and fees change and are quoted with the event's link."}


@mcp.tool(name="ncura_index", annotations=_READ_ONLY)
async def ncura_index() -> dict:
    """How to use the NCURA calendar tools. READ THIS FIRST: what the list covers, the event types, what is behind membership and not here."""
    try:
        up = await _list("upcoming")
        counts = {"upcoming": len(up), "types": sorted({e["type"] for e in up if e["type"]})}
    except ValueError as e:
        counts = {"error": str(e)}
    return {
        "upstream": f"NCURA's public event listing behind {CALENDAR} (cvweb EventList and EventInfo), read as HTML with a browser-like User-Agent, no key or login; the list cached an hour, an event a day",
        "coverage": counts,
        "workflow": ["ncura_events for the upcoming events, or with words of a title ('FRA', 'Region VI', 'virtual', 'pre-award'), or when='year' for the past year's too",
                     "ncura_event with the code from ncura_events (2026REGION67) for dates, registration deadlines, fees, description and location",
                     "registration is on the event's own page, linked on every answer"],
        "notes": ["Event types as NCURA codes them: ANNUAL (the Annual Meeting), FRA and PRA (the Financial and Pre-Award Research Administration conferences), FUND (Fundamentals workshops, Level I), DRA (Departmental Research Administration), REGSPRING and regional meetings (Regions I-VII; Idaho is Region VI), Online. A 'virtual experience' workshop's location reads 'Virtual Experience'.",
                  "registration 'open' is the list's own flag (a Register button shown), 'closed' the list's 'Registration Closed'; a deadline past or an event sold out is said on the event's page, read by ncura_event.",
                  "Fees are as the page prints them, member and non-member, early and regular; the early-bird deadline is on the event. Membership dues, Collaborate, NCURA Magazine, the member directory and the Career Center need a login and are not read here.",
                  "Cite as 'NCURA, <event title>, <dates>' with the event's link."],
        "link": CALENDAR,
    }


@mcp.tool(name="ncura_events", annotations=_READ_ONLY)
async def ncura_events(query: str = "", when: str = "upcoming", rows: int = ROWS) -> dict:
    """NCURA's meetings, conferences and workshops, soonest first, each with code, title, dates, type, whether registration is open and its link.

    Args:
        query: Words that must all appear as words of the title, subtitle, code or type (case-insensitive, singular or plural), e.g. 'FRA', 'Region VI', 'virtual pre-award'; empty for all.
        when: 'upcoming' (default) for events from yesterday on, as NCURA's calendar shows; 'year' to include the past 400 days.
        rows: How many to return, 1-200. Default 50.
    """
    when = when.strip().lower()
    if when not in WHEN:
        return {"error": "when must be upcoming or year"}
    try:
        events = await _list(when)
    except ValueError as e:
        return {"error": str(e), "source": _src()}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    words = re.findall(r"[a-z0-9]+", query.lower())
    found = [e for e in events if matches(words, " ".join(x for x in (e["title"], e["subtitle"], e["code"], e["type"]) if x))]
    found.sort(key=lambda e: (e["start"] or "9999", e["title"] or ""))
    return {"query": query or None, "when": when, "total": len(found), "returned": min(rows, len(found)), "events": found[:rows], "source": _src()}


@mcp.tool(name="ncura_event", annotations=_READ_ONLY)
async def ncura_event(code: str) -> dict:
    """One NCURA event by its code: title, dates, early-bird and registration deadlines, fees, description, venue and hotel link.

    Args:
        code: The event code ncura_events gives, e.g. '2026REGION67' or '2026VIRFUNDPREOCT'.
    """
    c = code.strip().upper()
    if not _CODE.match(c):
        return {"error": "code must be an NCURA event code such as 2026REGION67; ncura_events lists them"}
    try:
        page = await _cache.remember(f"event:{c}", DAY, lambda: get_text(INFO, {"sessionaltcd": c}, headers=HEADERS))
    except ValueError as e:
        return {"error": str(e), "code": c, "source": _src()}
    ev = parse_event(page, c)
    if not ev["title"]:
        return {"error": f"NCURA's calendar has no event {c}, or its page has changed shape", "code": c, "source": _src()}
    return {**ev, "source": _src({"page": ev["link"]})}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
given(mcp, {"ncura_event": {"code": "ncura_events"}})  # an event code is NCURA's handle, read from the list, not guessed (#40)
