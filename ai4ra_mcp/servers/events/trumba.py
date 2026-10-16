"""The University of Idaho campus calendar, published by Trumba as a JSON feed.

The university's calendar (uidaho.edu/events) is a Trumba calendar whose public feed is
https://www.trumba.com/calendars/university-of-idaho.json: every event the university's calendars publish, each
with its title, dates and times (campus local, with the UTC offset), location, calendar, description, links and
registration flags. The feed takes a date window (startdate and enddate as YYYYMMDD, or days or months from
today), a word search over the events' text, an eventid for one event, and events for the most to return (200
when not given). Filtering by calendar is done here, on the categoryCalendar each event carries, since the feed
has no parameter for it. No key, no login. Parameters confirmed on 2026-10-16.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime

from ai4ra_mcp.common.http import get_json

FEED = "https://www.trumba.com/calendars/university-of-idaho.json"
SITE = "https://www.uidaho.edu/events"
MAX_EVENTS = 500
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_HREF = re.compile(r'href="([^"]+)"')
_DATE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})$")


class FeedError(Exception):
    """The feed answered with something other than its list of events."""


def text(fragment: str | None) -> str | None:
    """A Trumba HTML fragment as plain text: tags gone, entities decoded, whitespace folded."""
    if not fragment:
        return None
    t = _WS.sub(" ", html.unescape(_TAG.sub(" ", fragment))).strip()
    return t or None


def href(fragment: str | None) -> str | None:
    """The first link in a fragment, decoded; None when it carries none."""
    if not fragment:
        return None
    m = _HREF.search(fragment)
    return html.unescape(m.group(1)) if m else None


def feed_date(value: str) -> str:
    """A date as the feed wants it, YYYYMMDD, from YYYY-MM-DD or YYYYMMDD; ValueError otherwise."""
    m = _DATE.match(value.strip())
    if not m:
        raise ValueError(f"{value!r} is not a date (YYYY-MM-DD)")
    y, mo, d = (int(g) for g in m.groups())
    date(y, mo, d)
    return f"{y:04d}{mo:02d}{d:02d}"


async def fetch(params: dict) -> list[dict]:
    body = await get_json(FEED, params)
    if not isinstance(body, list):
        raise FeedError("the feed did not return its list of events")
    return body


LIST_DESCRIPTION = 160


def slim(e: dict, full: bool = False) -> dict:
    """One event read to what a person asks: when, where, what, whose calendar, how to join or sign up. A list row is
    kept short (a month on the whole campus is three hundred events); the full form carries the whole description."""
    fields = {f.get("label"): f.get("value") for f in e.get("customFields") or [] if f.get("label")}
    description = text(e.get("description"))
    out = {
        "id": e.get("eventID"), "title": text(e.get("title")),
        "start": e.get("startDateTime"), "end": e.get("endDateTime"), "all_day": e.get("allDay"),
        "canceled": e.get("canceled"),
        "location_type": e.get("locationType") or None, "location": text(fields.get("University Location")) or text(e.get("location")),
        "online_link": href(fields.get("Participate Online")),
        "calendar": e.get("categoryCalendar") or None,
        "description": description if full or not description or len(description) <= LIST_DESCRIPTION else description[:LIST_DESCRIPTION].rsplit(" ", 1)[0] + " …",
        "link": e.get("permaLinkUrl"),
    }
    if full:
        out.update({"when": text(e.get("dateTimeFormatted")), "timezone_offset": e.get("startTimeZoneOffset"), "campus_location": text(fields.get("University Location")),
                    "web_link": href(e.get("webLink"))})
    if e.get("repeats"):
        out["repeats"] = text(e.get("repeats"))
        out["series_id"] = e.get("seriesID")
    if fields.get("Questions?"):
        out["contact"] = text(fields.get("Questions?"))
    if e.get("openSignUp") or e.get("requiresPayment"):
        out["registration"] = {"open": e.get("openSignUp"), "full": e.get("reservationFull"), "past_deadline": e.get("pastDeadline"),
                               "requires_payment": e.get("requiresPayment"), "waiting_list": e.get("waitingListAvailable"), "link": e.get("eventActionUrl")}
    if full and e.get("eventImage"):
        out["image"] = {"url": (e["eventImage"] or {}).get("url"), "alt": (e["eventImage"] or {}).get("alt")}
    return out


def today() -> date:
    return datetime.now().date()
