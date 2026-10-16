"""events, offline from nine events captured from the campus calendar's Trumba feed on 2026-10-16 (contacts anonymised,
descriptions cut): an event read to its fields with the HTML gone; the window parameters the feed is sent for each
way of asking; the calendar filter applied here; one event by id; the calendar list counted; and bad input said."""

import json
from datetime import date
from pathlib import Path

import pytest

from ai4ra_mcp.servers.events import server as ev
from ai4ra_mcp.servers.events import trumba

FEED = json.loads((Path(__file__).parent / "fixtures" / "events" / "feed.json").read_text(encoding="utf-8"))
BY_ID = {e["eventID"]: e for e in FEED}


def _feed(monkeypatch, calls: list | None = None, answer=None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        if answer is not None:
            return answer
        if "eventid" in (params or {}):
            return [BY_ID[params["eventid"]]] if params["eventid"] in BY_ID else []
        if (params or {}).get("search") == "nothing":
            return []
        return FEED

    monkeypatch.setattr(trumba, "get_json", get_json)
    monkeypatch.setattr(trumba, "today", lambda: date(2026, 10, 16))
    ev._cache._d.clear()
    return calls


def test_an_event_is_read_to_its_fields_with_the_html_gone():
    e = trumba.slim(BY_ID[183225128])
    assert e["title"] == "Vandal Voyagers — Village Life Cotswolds" and e["all_day"] is True and e["start"] == "2026-10-11T00:00:00" and e["end"] == "2026-10-20T00:00:00"
    assert e["location"] == "England" and e["calendar"] == "Alumni Relations" and e["web_link"].startswith("https://idaho.gohagantravel.com/") and "when" not in e and e["link"].startswith("https://www.uidaho.edu/events?")
    assert "<" not in json.dumps(e) and e["description"].endswith(" …") and len(e["description"]) <= 165
    online = trumba.slim(BY_ID[206122718])
    assert online["location_type"] == "Online" and online["online_link"].startswith("https://uidaho.zoom.us/")
    series = trumba.slim(BY_ID[206378665])
    assert series["repeats"] == "Monthly on the last Wednesday of the month through October 28, 2026" and series["series_id"]
    contact = trumba.slim(BY_ID[209597493])
    assert contact["contact"] == "Contact Example Person, events@example.edu"
    full = trumba.slim(BY_ID[206122718], full=True)
    assert len(full["description"]) >= len(online["description"]) and not full["description"].endswith(" …") and full["timezone_offset"] in ("-0700", "-0800") and full["when"]
    room = trumba.slim(BY_ID[211332463])
    assert room["location"].startswith("ALB 311") or room["location"]  # the campus room stands in for the location line in a list row


def test_text_and_href_and_dates():
    assert trumba.text('<a href="x">A &amp; B</a>  <i>c</i>') == "A & B c" and trumba.text("") is None and trumba.text(None) is None
    assert trumba.href('<a href="https://x.y/z?a=1&amp;b=2" target="_blank">x</a>') == "https://x.y/z?a=1&b=2" and trumba.href("plain") is None
    assert trumba.feed_date("2026-11-01") == "20261101" and trumba.feed_date("20261101") == "20261101"
    for bad in ("2026-13-01", "11/01/2026", "tomorrow"):
        with pytest.raises(ValueError):
            trumba.feed_date(bad)


async def test_search_sends_the_window_the_way_it_was_asked(monkeypatch):
    calls = _feed(monkeypatch)
    out = await ev.events_search()
    assert calls[-1][0] == trumba.FEED and calls[-1][1] == {"events": 500, "days": 30} and out["window"] == {"days": 30} and out["total"] == 9
    assert [e["start"] for e in out["events"]] == sorted(e["start"] for e in out["events"])
    await ev.events_search(start="2026-11-01", end="2026-11-30", search="research seminar")
    assert calls[-1][1] == {"events": 500, "startdate": "20261101", "enddate": "20261130", "search": "research seminar"}
    await ev.events_search(start="2026-11-01", days=7)
    assert calls[-1][1] == {"events": 500, "startdate": "20261101", "enddate": "20261107"}
    await ev.events_search(end="2026-12-31")
    assert calls[-1][1] == {"events": 500, "startdate": "20261016", "enddate": "20261231"}
    assert len(calls) == 4
    await ev.events_search()
    assert len(calls) == 4  # the same window within ten minutes is the cache
    assert "error" in await ev.events_search(start="2026-99-01")


async def test_calendar_filter_rows_and_the_cap_note(monkeypatch):
    _feed(monkeypatch)
    out = await ev.events_search(calendar="student affairs")
    assert out["total"] == 2 and all("Student Affairs" in e["calendar"] for e in out["events"]) and out["window"]["calendar"] == "student affairs"
    out = await ev.events_search(rows=2)
    assert out["total"] == 9 and len(out["events"]) == 2 and "first 2" in out["note"]
    assert (await ev.events_search(search="nothing"))["events"] == []
    ev._cache._d.clear()
    _feed(monkeypatch, answer=[BY_ID[198514850]] * 500)
    assert "at most 500" in (await ev.events_search(days=90))["note"]


async def test_one_event_by_id_in_full_and_none(monkeypatch):
    calls = _feed(monkeypatch)
    out = await ev.events_event(206122718)
    assert calls[-1][1] == {"eventid": 206122718} and out["event"]["id"] == 206122718 and out["event"]["online_link"]
    assert "error" in await ev.events_event(1) and "error" in await ev.events_event("abc")


async def test_calendars_are_counted(monkeypatch):
    calls = _feed(monkeypatch)
    out = await ev.events_calendars()
    assert calls[-1][1] == {"months": 3, "events": 500} and out["total"] == 7 and out["events_counted"] == 9
    assert out["calendars"][0] == {"calendar": "University Closures", "events": 3}  # most events first, then by name
    assert sum(c["events"] for c in out["calendars"]) == 9


async def test_closures_are_found_by_what_the_events_say(monkeypatch):
    calls = _feed(monkeypatch)
    out = await ev.events_closures()
    assert [c[1]["search"] for c in calls] == ["closed", "closure", "holiday"] and all(c[1]["days"] == 120 for c in calls) and out["window"] == {"days": 120}
    assert out["total"] == 3 and [c["start"][:10] for c in out["closures"]] == ["2026-11-26", "2026-11-27", "2026-12-24"] and all(c["all_day"] and c["calendar"] == "University Closures" for c in out["closures"])
    assert set(out["closures"][0]) == {"id", "title", "start", "end", "all_day", "calendar", "description", "link"} and "concert" in out["note"]
    assert ev.is_closure({"title": "Holiday Jazz Choirs Concert", "categoryCalendar": "Lionel Hampton School of Music"}) is False
    assert ev.is_closure({"title": "Vandal Voyagers: Holiday Markets Cruise", "categoryCalendar": "Alumni Relations"}) is False
    assert ev.is_closure({"title": "University Closed to the Public", "categoryCalendar": "University of Idaho Main"}) is True
    assert ev.is_closure({"title": "Thanksgiving", "categoryCalendar": "Holidays and Closures"}) is True
    assert ev.is_closure({"title": "Snow closure", "categoryCalendar": "Registrar"}) is True
    none = await ev.events_closures(start="2026-11-01", end="2026-11-02")
    assert none["window"] == {"startdate": "20261101", "enddate": "20261102"}  # the fixture answers every window alike; the live feed narrows
    assert "error" in await ev.events_closures(start="soon")


async def test_a_feed_that_is_not_a_list_is_reported(monkeypatch):
    _feed(monkeypatch, answer={"error": "down"})
    out = await ev.events_search()
    assert "did not return its list" in out["error"] and out["upstream"] == trumba.FEED


async def test_the_index_names_the_upstream_and_the_caveats():
    out = await ev.events_index()
    assert out["upstream"].startswith("The University of Idaho campus calendar at https://www.uidaho.edu/events") and out["caveats"] == ev.CAVEATS
