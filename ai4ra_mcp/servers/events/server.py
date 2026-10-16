"""events: the University of Idaho campus calendar, the events the university's calendars publish at uidaho.edu/events.

What is happening on campus and when: events by date window, words or calendar; one event in full; the calendars
that feed the university's. The upstream is the calendar's public Trumba feed (trumba.py); every tool is a read
and no key is taken. A window's events are cached ten minutes, the calendar list an hour.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import HOUR, TTLCache
from ai4ra_mcp.common.skills import register_prompts
from ai4ra_mcp.servers.events import trumba

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
TEN_MINUTES = 10 * 60
ROWS, MAX_ROWS = 50, 200
DAYS, MAX_DAYS = 30, 366
_cache = TTLCache()

CAVEATS = [
    "This is the calendar's public feed, which the university's calendar owners fill; an event is as current as its owner left it, and a calendar that posts nothing is not here. A change to the feed's shape is a change to this server; the only test is the live feed.",
    "Times are campus local (Moscow, Idaho; Mountain time) and carry the UTC offset; an all-day event has no time of day. A multi-day event appears from its start date through its end.",
    "Events from every university calendar come through one feed; calendar names the owner ('Registrar', 'College of Graduate Studies', 'Alumni Relations'), and a window with no filter is the whole campus.",
    "Registration, payment and waiting-list flags are the feed's own and say nothing about whether a particular person may attend; the event's link is where that is settled.",
    "The feed returns at most 500 events a call; a wide window on a busy month can reach it, so narrow the window or add words.",
    "Cite an event by title and date with its link.",
]

mcp = MCPServer(
    "events",
    instructions="The University of Idaho campus calendar from uidaho.edu/events: events by date window, words or calendar (events_search), one event in full (events_event), the calendars that feed it (events_calendars). No key. Read events_index first.",
)


async def _window(start: str, end: str, days: int, search: str) -> tuple[dict, list[dict]]:
    """The feed parameters for a window and the events it holds, cached ten minutes."""
    params: dict = {"events": trumba.MAX_EVENTS}
    if start.strip():
        params["startdate"] = trumba.feed_date(start)
        if end.strip():
            params["enddate"] = trumba.feed_date(end)
        else:
            first = trumba.date(int(params["startdate"][:4]), int(params["startdate"][4:6]), int(params["startdate"][6:]))
            params["enddate"] = (first + timedelta(days=days - 1)).strftime("%Y%m%d")
    elif end.strip():
        params["startdate"] = trumba.today().strftime("%Y%m%d")
        params["enddate"] = trumba.feed_date(end)
    else:
        params["days"] = days
    if search.strip():
        params["search"] = search.strip()
    key = "feed:" + repr(sorted(params.items()))
    return params, await _cache.remember(key, TEN_MINUTES, lambda: trumba.fetch(params))


@mcp.tool(name="events_index", annotations=_READ_ONLY)
async def events_index() -> dict:
    """How to use the campus calendar tools. READ THIS FIRST: the date window, what a search matches, what an event carries."""
    return {
        "upstream": f"The University of Idaho campus calendar at {trumba.SITE}, read from its public Trumba feed {trumba.FEED}; no login, no key",
        "workflow": ["events_search for a date window (start and end, or start and days, or the next days from today), optionally narrowed by words or by calendar: title, when, where (campus room or online link), calendar, a description cut at 400 characters, links",
                     "events_event for one event by id in full: the whole description, image, contact, registration",
                     "events_calendars for the calendars that feed the university's, with how many events each has in the coming months, the names a calendar argument is matched against"],
        "notes": ["Dates are YYYY-MM-DD; with no window the next 30 days are read. The feed searches words anywhere in an event's text; a phrase in quotes matches nothing, so give words.",
                  "An event lists the campus room as the calendar owner wrote it ('ALB 311 - J. A. Albertson - Main Campus'), the online link when there is one, and location_type In-Person, Online or Hybrid.",
                  "Repeating events appear once per occurrence in the window, sharing a series_id, with repeats saying the rule ('Every Friday through December 4, 2026').",
                  "Cite an event by title and date with its link; a window is at most ten minutes old."],
        "caveats": CAVEATS,
        "link": trumba.SITE,
    }


@mcp.tool(name="events_search", annotations=_READ_ONLY)
async def events_search(search: str = "", start: str = "", end: str = "", days: int = DAYS, calendar: str = "", rows: int = ROWS) -> dict:
    """Events on the University of Idaho campus calendar in a date window, optionally matching words or on one calendar, soonest first.

    With nothing given, the next 30 days. Use it for what is on this week, the research seminars this month, the Registrar's
    deadlines this term, or whether anything is scheduled on a date.

    Args:
        search: Words to match anywhere in an event's text, e.g. 'research seminar'. Words, not a quoted phrase.
        start: First date of the window, YYYY-MM-DD. Default today.
        end: Last date of the window, YYYY-MM-DD. Default start plus days.
        days: Length of the window in days when end is not given, 1-366. Default 30.
        calendar: A calendar's name or part of it ('Registrar', 'Graduate Studies'), as events_calendars lists them.
        rows: Events to return, 1-200. Default 50.
    """
    days = max(1, min(int(days or DAYS), MAX_DAYS))
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    try:
        params, found = await _window(start, end, days, search)
    except (ValueError, trumba.FeedError) as e:
        return {"error": str(e), "upstream": trumba.FEED}
    want = calendar.strip().lower()
    if want:
        found = [e for e in found if want in (e.get("categoryCalendar") or "").lower()]
    found = sorted(found, key=lambda e: (e.get("startDateTime") or "", e.get("eventID") or 0))
    out = {"window": {k: v for k, v in params.items() if k != "events"}, "total": len(found), "events": [trumba.slim(e) for e in found[:rows]], "link": trumba.SITE}
    if calendar.strip():
        out["window"]["calendar"] = calendar.strip()
    if len(found) > rows:
        out["note"] = f"{len(found)} events in the window; the first {rows} are here. Narrow the window, add words or a calendar, or raise rows (to {MAX_ROWS})."
    if len(found) >= trumba.MAX_EVENTS and not want:
        out["note"] = f"The feed returns at most {trumba.MAX_EVENTS} events a call and this window reached it; narrow the window."
    return out


@mcp.tool(name="events_event", annotations=_READ_ONLY)
async def events_event(id: int) -> dict:
    """One event on the University of Idaho campus calendar in full: the whole description, location, online link, contact, registration, image.

    Args:
        id: The event's id, from events_search.
    """
    try:
        eid = int(id)
    except (TypeError, ValueError):
        return {"error": "id must be the event's numeric id"}
    try:
        found = await _cache.remember(f"event:{eid}", TEN_MINUTES, lambda: trumba.fetch({"eventid": eid}))
    except (ValueError, trumba.FeedError) as e:
        return {"error": str(e), "upstream": trumba.FEED}
    if not found:
        return {"error": f"no event {eid} on the calendar; it may have been removed, or the id is not one the feed gave", "link": trumba.SITE}
    return {"event": trumba.slim(found[0], full=True)}


@mcp.tool(name="events_calendars", annotations=_READ_ONLY)
async def events_calendars(months: int = 3) -> dict:
    """The calendars that feed the University of Idaho's, with how many events each has in the coming months: the names a calendar argument is matched against.

    Args:
        months: How many months ahead to count, 1-12. Default 3.
    """
    months = max(1, min(int(months or 3), 12))
    try:
        found = await _cache.remember(f"calendars:{months}", HOUR, lambda: trumba.fetch({"months": months, "events": trumba.MAX_EVENTS}))
    except (ValueError, trumba.FeedError) as e:
        return {"error": str(e), "upstream": trumba.FEED}
    counts: dict[str, int] = {}
    for e in found:
        name = e.get("categoryCalendar") or "(no calendar)"
        counts[name] = counts.get(name, 0) + 1
    calendars = [{"calendar": k, "events": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    out = {"months": months, "total": len(calendars), "events_counted": len(found), "calendars": calendars, "link": trumba.SITE}
    if len(found) >= trumba.MAX_EVENTS:
        out["note"] = f"The feed returns at most {trumba.MAX_EVENTS} events a call, so the counts cover the first {trumba.MAX_EVENTS} events of the period, not all of it."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# An event id the model names waits on a search that returned it (#40); a calendar name on the list.
given(mcp, {"events_event": {"id": "events_search"}, "events_search": {"calendar": "events_calendars"}})
