"""ncura: the National Council of University Research Administrators' calendar of meetings, conferences and workshops.

Upstream: the public event listing behind the calendar page at https://www.ncura.edu/Education/Calendar.aspx, an
iframe onto NCURA's association-management system (cvweb, Eventsdll.dll): EventList gives the events on the web
from a start date as an HTML table (title, subtitle, dates, a registration flag, the event type and the check
registration form), and EventInfo?sessionaltcd=<code> one event with its dates, deadlines, fees, description
and location. Neither needs a login; the member side (Collaborate, the magazine, the directory) is behind one
and is not read. NCURA shows nine upcoming events today (2026-10-16) and 46 with the past year. The list is cached
an hour, an event a day. Every answer links the event's page on ncura.edu and the calendar.

The Regions VI & VII Regional Meeting's program (Denver, 2026-11-08 to 11) is not on ncura.edu: Region VI's meeting page
(ncuraregionvi.org/rm2026) links it as a PDF, an Excel sheet printed to 17 pages, re-uploaded under a new address with
each update. ncura_program reads the page, follows its 'Conference Program' link and parses the sheet by where each
text run starts (102 rows on 2026-11-09), cached an hour.
"""

from __future__ import annotations

import html as htmlmod
import io
import re
from datetime import date, datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from pypdf import PdfReader
from pypdf._font import Font

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_bytes, get_text
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

# The Regions VI & VII meeting's program is not on ncura.edu: Region VI's meeting page links it as a PDF, an Excel
# sheet printed to paper, whose address changes with every upload. The page is per year (/rm2026).
REGION_VI = "https://www.ncuraregionvi.org"
MEETING = f"{REGION_VI}/rm2026"
MEETING_CODE = "2026REGION67"
_PROGRAM_LINK = re.compile(r'<a[^>]+href="(?P<href>[^"]+\.pdf)"[^>]*aria-label="[^"]*Program[^"]*"', re.I)
_DAY = re.compile(r"^(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday), [A-Z][a-z]+ (?P<n>\d{1,2})\b")
_CELL_DATE = re.compile(r"^(?P<n>\d{1,2})-[A-Z][a-z]{2}$")
# Each column of the printed sheet starts at the same x on every page (points); a run belongs to the column it starts in.
_COLUMNS = [(160, "track"), (260, "type"), (335, "level"), (553, "title"), (885, "description"), (1125, "presenters"),
            (1170, "date"), (1240, "time"), (float("inf"), "location")]
_ONE_LINE = ("track", "type", "level", "title", "date", "time", "location")

mcp = MCPServer(
    "ncura",
    instructions="NCURA's calendar: the National Council of University Research Administrators' upcoming meetings, conferences, traveling and virtual workshops (ncura_events, by words, upcoming or the past year) and one event with its dates, registration deadlines, fees, description and location (ncura_event, by the code ncura_events gives); and the program of the 2026 Regions VI & VII Regional Meeting, session by session, as Markdown (ncura_program). Public pages, no key or membership. Read ncura_index first.",
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
    return {"calendar": CALENDAR, "list": LIST, "read": date.today().isoformat(),
            "note": "NCURA's calendar is the authority; dates, deadlines and fees change and are quoted with the event's link.", **(extra or {})}


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
                     "registration is on the event's own page, linked on every answer",
                     "ncura_program for the 2026 Regions VI & VII Regional Meeting's program (Denver, November 8-11): a schedule table by day, narrowed by words ('subaward', 'Platte') or a day ('Tuesday'); details=True for presenters and descriptions"],
        "notes": ["Event types as NCURA codes them: ANNUAL (the Annual Meeting), FRA and PRA (the Financial and Pre-Award Research Administration conferences), FUND (Fundamentals workshops, Level I), DRA (Departmental Research Administration), REGSPRING and regional meetings (Regions I-VII; Idaho is Region VI), Online. A 'virtual experience' workshop's location reads 'Virtual Experience'.",
                  "registration 'open' is the list's own flag (a Register button shown), 'closed' the list's 'Registration Closed'; a deadline past or an event sold out is said on the event's page, read by ncura_event.",
                  "Fees are as the page prints them, member and non-member, early and regular; the early-bird deadline is on the event. Membership dues, Collaborate, NCURA Magazine, the member directory and the Career Center need a login and are not read here.",
                  "Cite as 'NCURA, <event title>, <dates>' with the event's link.",
                  f"The Regions VI & VII program is read from the PDF that NCURA Region VI's meeting page ({MEETING}) links, not from ncura.edu; the program committee replaces it during the meeting, so it is read again within the hour. A row whose date cell disagrees with its day heading is shown under the heading with the date as printed."],
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


def _column(x: float) -> str:
    return next(name for edge, name in _COLUMNS if x < edge)


def _decode(font: Font, raw) -> str:
    """A shown string through its font: the encoding (WinAnsi, or two-byte for a subset font), then the font's ToUnicode map."""
    raw = raw.get_original_bytes() if hasattr(raw, "get_original_bytes") else raw
    enc = font.encoding
    chars = raw.decode(enc, "replace") if isinstance(enc, str) else "".join(enc.get(b, chr(b)) for b in raw)
    return "".join(font.character_map.get(c, c) for c in chars)


def _runs(page) -> list[tuple[float, float, str]]:
    """Every text-showing operator on a page in drawing order with where it starts: (y, x, text). pypdf's own text joins the runs on
    one line, cells across; here x is right where a run follows a move (each cell's start) and not after a run in the same move."""
    fonts = {k: Font.from_font_resource(v.get_object()) for k, v in page.get("/Resources", {}).get("/Font", {}).items()}
    out: list[tuple[float, float, str]] = []
    font = None

    def before(op, args, cm, tm):
        nonlocal font
        if op == b"Tf":
            font = fonts.get(args[0])
        elif op in (b"Tj", b"TJ"):
            parts = [args[0]] if op == b"Tj" else [a for a in args[0] if not isinstance(a, (int, float))]
            t = "".join(_decode(font, p) for p in parts)
            if t.strip():
                out.append((tm[5] * cm[3] + cm[5], tm[4] * cm[0] + cm[4], t))

    page.extract_text(visitor_operand_before=before)
    return out


def _cell(runs: list[tuple[float, float, str]], one_line: bool) -> str:
    """A cell's lines in order: a line ending in a space or a hyphen wrapped and joins on, any other breaks; a blank line is a paragraph.

    Runs (in drawing order) within a point of each other are one line, kept in drawing order (a capital in another font sits lower)."""
    lines: list[tuple[float, list]] = []
    for i, (y, x, t) in sorted(enumerate(runs), key=lambda r: -r[1][0]):
        if lines and lines[-1][0] - y < 1:
            lines[-1][1].append((i, t))
        else:
            lines.append((y, [(i, t)]))
    out, prev = "", None
    for y, parts in lines:
        t = "".join(p for _, p in sorted(parts))
        if prev is not None:
            out += "\n\n" if prev[0] - y > 20 else " " if prev[1].endswith(" ") else "" if prev[1].endswith("-") else "\n"
        out += t
        prev = (y, t)
    out = "\n".join(re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in out.split("\n")).strip()
    return re.sub(r"\s+", " ", out) if one_line else out


def parse_program(data: bytes) -> dict:
    """The printed program: its heading and every row (day heading, track, type, level, title, description, presenters, date, time, room).

    A row begins at its date cell and holds every run from there down to the next date; a day heading ('Monday, November 9 - Sessions')
    stands in the track column. A row with no title (a dinner) prints its name in the description column, and is given it as title."""
    reader = PdfReader(io.BytesIO(data))
    heading, day, rows = None, None, []
    for page in reader.pages:
        runs = _runs(page)
        tops = [y for y, x, t in runs if t.strip() == "Track"]
        if not tops:
            continue
        top = max(tops)
        heading = heading or next((re.sub(r"\s+", " ", t).strip() for y, x, t in runs if y > top + 1), None)
        body = [(y, x, t) for y, x, t in runs if y < top - 1]
        days = sorted(((y, re.sub(r"\s+", " ", t).strip()) for y, x, t in body if _column(x) == "track" and _DAY.match(re.sub(r"\s+", " ", t).strip())), reverse=True)
        last = rows[-1] if rows else None  # runs above the page's first date run on from the page before
        here: dict[float, dict] = {}
        for a in sorted({y for y, x, t in body if _column(x) == "date" and _CELL_DATE.match(t.strip())}, reverse=True):
            day = next((d for y, d in reversed(days) if y > a), day)
            here[a] = {"day": day, "_runs": {name: [] for _, name in _COLUMNS}}
            rows.append(here[a])
        day = days[-1][1] if days else day
        for y, x, t in body:
            if (y, re.sub(r"\s+", " ", t).strip()) in days:
                continue
            row = here[min(a for a in here if a >= y - 1)] if any(a >= y - 1 for a in here) else last
            if row is not None:
                row["_runs"][_column(x)].append((y, x, t))
    sessions = []
    for row in rows:
        s = {"day": row["day"], **{name: _cell(r, name in _ONE_LINE) or None for name, r in row["_runs"].items()}}
        if not s["title"] and s["description"]:
            s["title"], s["description"] = re.sub(r"\s+", " ", s["description"]), None
        dm, cm = _DAY.match(s["day"] or ""), _CELL_DATE.match(s["date"] or "")
        s["date_differs"] = bool(dm and cm and dm.group("n") != cm.group("n"))
        sessions.append(s)
    return {"heading": heading, "sessions": sessions}


async def _program() -> dict:
    async def load():
        page = await get_text(MEETING, headers=HEADERS)
        link = _PROGRAM_LINK.search(page)
        if not link:
            raise ValueError(f"the meeting page {MEETING} links no program PDF today; Region VI may have moved it")
        pdf = htmlmod.unescape(link.group("href"))
        prog = parse_program(await get_bytes(pdf, headers=HEADERS))
        if not prog["sessions"]:
            raise ValueError(f"the program at {pdf} has no sessions this parser can read; its layout may have changed")
        return {**prog, "pdf": pdf}
    return await _cache.remember("program", HOUR, load)


def _md(s: str | None) -> str:
    return (s or "").replace("|", "\\|")


def program_markdown(heading: str | None, sessions: list[dict], details: bool) -> str:
    """The sessions under their day headings: a table per day, or with details each session's presenters and description."""
    out = [f"# {heading or 'Program'}"]
    for day in dict.fromkeys(s["day"] for s in sessions):
        out.append(f"\n## {day or 'Undated'}\n")
        todays = [s for s in sessions if s["day"] == day]
        if not details:
            out += ["| Time | Session | Track | Type | Level | Room |", "|---|---|---|---|---|---|"]
        for s in todays:
            when = (s["time"] or "") + (f" (dated {s['date']} in the program)" if s["date_differs"] else "")
            if not details:
                out.append(f"| {_md(when)} | {_md(s['title'])} | {_md(s['track'])} | {_md(s['type'])} | {_md(s['level'])} | {_md(s['location'])} |")
                continue
            out.append(f"### {when} · {s['title']}")
            facts = " · ".join(x for x in (s["track"], s["type"], s["level"], s["location"]) if x)
            if facts:
                out.append(facts)
            if s["presenters"]:
                out.append("\n**Presenters:** " + "; ".join(ln for ln in s["presenters"].split("\n") if ln))
            if s["description"]:
                out.append("\n" + s["description"])
            out.append("")
    return "\n".join(out).strip() + "\n"


@mcp.tool(name="ncura_program", annotations=_READ_ONLY)
async def ncura_program(query: str = "", day: str = "", details: bool = False) -> dict:
    """The program of NCURA's Regions VI & VII Regional Meeting (Denver, November 8-11, 2026), as Markdown: every workshop, session, meal and break by day with time, track, type, level and room; with details, each one's presenters and description.

    Read live from the program PDF linked on Region VI's meeting page, which the committee updates during the meeting.

    Args:
        query: Words that must all appear in a session's title, description, presenters, track, type, level or room (case-insensitive), e.g. 'subaward', 'AI', 'Idaho', 'Platte'; empty for all.
        day: Words of the day heading, e.g. 'Monday', 'November 10', 'workshops'; empty for every day.
        details: True for each session's presenters and description; False (default) for a schedule table.
    """
    try:
        prog = await _program()
    except ValueError as e:
        return {"error": str(e), "source": _src({"meeting_page": MEETING})}
    words, days = re.findall(r"[a-z0-9]+", query.lower()), re.findall(r"[a-z0-9]+", day.lower())
    found = [s for s in prog["sessions"]
             if matches(words, " ".join(x for x in (s["title"], s["description"], s["presenters"], s["track"], s["type"], s["level"], s["location"]) if x))
             and matches(days, s["day"] or "")]
    return {"query": query or None, "day": day or None, "program": prog["heading"], "total": len(prog["sessions"]), "returned": len(found),
            "markdown": program_markdown(prog["heading"], found, details) if found else None,
            "source": _src({"meeting_page": MEETING, "program_pdf": prog["pdf"], "event": f"{PAGE}?sessionaltcd={MEETING_CODE}",
                            "note": "The program PDF from NCURA Region VI's meeting page is the authority; rooms and times change during the meeting."})}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
given(mcp, {"ncura_event": {"code": "ncura_events"}})  # an event code is NCURA's handle, read from the list, not guessed (#40)
