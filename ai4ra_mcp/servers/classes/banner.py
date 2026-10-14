"""The registrar's public class schedule: Browse Classes in Banner Student Registration Self-Service, read
through the schedule page's own interface at banner.uidaho.edu/StudentRegistrationSsb. No login, no key.

Banner ties a search to a session cookie and a chosen term. A second search on the same session answers with
the first search's results until the form is reset, and the instructor ids its name lookup returns are numbered
within the session. So every call here opens its own session, selects the term, does its lookups and its search
in that session, resets the form and closes; nothing is shared between calls but the cache of what came back.
Routes confirmed without a login on 2026-10-13 and 2026-10-14.
"""

from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx

from ai4ra_mcp.common import fetch as _fetch
from ai4ra_mcp.common.http import HEADERS

BASE = "https://banner.uidaho.edu/StudentRegistrationSsb/ssb/"
BROWSE = BASE + "classSearch/classSearch"
TIMEOUT = 30
_DAYS = (("monday", "M"), ("tuesday", "T"), ("wednesday", "W"), ("thursday", "R"), ("friday", "F"), ("saturday", "S"), ("sunday", "U"))
_LABEL = re.compile(r"^([A-Z][A-Za-z /]+):", re.M)
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")


class BannerError(Exception):
    """Banner answered a route with something other than what the route returns: a status, a page where JSON
    was expected (a CRN it does not know comes back as a 500 HTML page), or no connection."""

    def __init__(self, route: str, status: int | None, detail: str):
        super().__init__(f"Banner answered {status if status is not None else 'nothing'} on {route}: {detail}")
        self.route, self.status, self.detail = route, status, detail

    def as_error(self) -> dict:
        return {"error": str(self), "upstream": BASE + self.route,
                "note": "This is the schedule page's own internal interface, not a published API; a Banner upgrade can change a route without notice. Check the page itself: " + BROWSE}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT, headers=HEADERS, follow_redirects=True)


async def _call(client: httpx.AsyncClient, method: str, route: str, **kw) -> httpx.Response:
    try:
        resp = await client.request(method, route, **kw)
    except httpx.HTTPError as e:
        raise BannerError(route, None, f"could not connect ({e.__class__.__name__})") from e
    if resp.status_code != 200:
        raise BannerError(route, resp.status_code, "not the 200 the route returns")
    return resp


async def _json(client: httpx.AsyncClient, method: str, route: str, **kw):
    resp = await _call(client, method, route, **kw)
    try:
        return resp.json()
    except ValueError:
        raise BannerError(route, resp.status_code, "a page where JSON was expected") from None


async def get_terms(max: int = 10) -> list[dict]:
    """Banner's terms, newest first: [{code, description}]; a term closed to registration says '(View Only)'."""
    async with _client() as client:
        return await _json(client, "GET", "classSearch/getTerms", params={"searchTerm": "", "offset": 1, "max": max})


@asynccontextmanager
async def session(term: str) -> AsyncIterator[httpx.AsyncClient]:
    """A client whose session has the term selected. Resets the search form before closing, as the page does."""
    async with _client() as client:
        await _call(client, "GET", "term/termSelection", params={"mode": "search"})
        await _json(client, "POST", "term/search", params={"mode": "search"}, data={"term": term})
        try:
            yield client
        finally:
            try:
                await client.post("classSearch/resetDataForm")
            except httpx.HTTPError:
                pass


async def find_instructors(client: httpx.AsyncClient, term: str, fragment: str, max: int = 20) -> list[dict]:
    """[{code, description}]: Banner's session-numbered id and display name for each instructor the fragment matches."""
    return await _json(client, "GET", "classSearch/get_instructor", params={"searchTerm": fragment, "term": term, "offset": 1, "max": max})


async def search(client: httpx.AsyncClient, term: str, subject: str = "", course_number: str = "", instructor_code: str = "",
                 rows: int = 25, start: int = 0) -> dict:
    """{totalCount, data: [section]} for the term selected on the session."""
    params = {"txt_term": term, "txt_subject": subject, "txt_courseNumber": course_number, "pageOffset": start, "pageMaxSize": rows}
    if instructor_code:
        params["txt_instructor"] = instructor_code
    return await _json(client, "GET", "searchResults/searchResults", params=params)


async def details(client: httpx.AsyncClient, term: str, crn: str) -> dict:
    """The five detail panels of one section as Banner returns them: HTML but for the meeting times, which are JSON."""
    form = {"term": term, "courseReferenceNumber": crn}
    out = {}
    for key, route in (("description", "getCourseDescription"), ("details", "getClassDetails"), ("prerequisites", "getSectionPrerequisites"), ("enrollment", "getEnrollmentInfo")):
        out[key] = (await _call(client, "POST", f"searchResults/{route}", data=form)).text
    out["meetings"] = await _json(client, "POST", "searchResults/getFacultyMeetingTimes", data=form)
    return out


# ---- from Banner's shapes to ours ----

def _time(hhmm: str | None) -> str | None:
    return f"{hhmm[:2]}:{hhmm[2:]}" if hhmm and len(hhmm) == 4 else None


def _credits(s: dict) -> str | None:
    if s.get("creditHours") is not None:
        return str(s["creditHours"])
    low, high = s.get("creditHourLow"), s.get("creditHourHigh")
    if low is None and high is None:
        return None
    return f"{low}-{high}" if high is not None and high != low else str(low if low is not None else high)


def meeting(mt: dict) -> dict:
    """One meeting pattern as {days, start, end, building, room, from, to, type}; days '' and times None when unscheduled."""
    return {"days": "".join(letter for key, letter in _DAYS if mt.get(key)), "start": _time(mt.get("beginTime")), "end": _time(mt.get("endTime")),
            "building": mt.get("buildingDescription") or mt.get("building"), "room": mt.get("room"),
            "from": mt.get("startDate"), "to": mt.get("endDate"), "type": mt.get("meetingTypeDescription")}


def meets(s: dict) -> str:
    """The section's meetings in one line: 'MW 14:30-15:20 LIFE SCIENCES SOUTH 277'; 'TBA' when no meeting has a time."""
    parts = []
    for m in s.get("meetingsFaculty") or []:
        mt = meeting(m.get("meetingTime") or {})
        if not mt["start"] and not mt["days"]:
            continue
        where = " ".join(x for x in (mt["building"], mt["room"]) if x)
        when = f"{mt['start']}-{mt['end']}" if mt["start"] else ""
        parts.append(" ".join(x for x in (mt["days"], when, where) if x))
    return "; ".join(parts) or "TBA"


def instructors(faculty: list[dict] | None) -> list[dict]:
    return [{"name": f.get("displayName"), "email": f.get("emailAddress"), "primary": bool(f.get("primaryIndicator"))} for f in faculty or []]


def slim_section(s: dict) -> dict:
    return {"crn": s.get("courseReferenceNumber"), "subject": s.get("subject"), "number": s.get("courseNumber"), "title": s.get("courseTitle"),
            "section": s.get("sequenceNumber"), "credits": _credits(s), "campus": s.get("campusDescription"),
            "schedule_type": s.get("scheduleTypeDescription"), "method": s.get("instructionalMethodDescription"),
            "instructors": instructors(s.get("faculty")), "meets": meets(s),
            "enrollment": s.get("enrollment"), "capacity": s.get("maximumEnrollment"), "seats_available": s.get("seatsAvailable"),
            "waitlist": s.get("waitCount"), "part_of_term": s.get("partOfTerm"), "open": s.get("openSection")}


def _labelled(html: str) -> dict[str, str]:
    """A Banner detail panel's 'Label: value' pairs, read down to text: {'Campus': 'Moscow', ...}."""
    parts = _LABEL.split(_fetch.html_to_text(html)[1])   # [before, label, value, label, value, ...]
    return {label.strip(): " ".join(value.split()) for label, value in zip(parts[1::2], parts[2::2])}


def parse_details(html: str) -> dict:
    d = _labelled(html)
    return {"campus": d.get("Campus"), "schedule_type": d.get("Schedule Type"), "method": d.get("Instructional Method"),
            "section": d.get("Section Number"), "credits": d.get("Credit Hours"), "grade_mode": d.get("Grade Mode")}


def _int(v: str | None) -> int | None:
    return int(v) if v is not None and v.strip().lstrip("-").isdigit() else None


def parse_enrollment(html: str) -> dict:
    d = _labelled(html)
    return {"actual": _int(d.get("Enrollment Actual")), "maximum": _int(d.get("Enrollment Maximum")), "seats_available": _int(d.get("Enrollment Seats Available")),
            "waitlist_actual": _int(d.get("Waitlist Actual")), "waitlist_capacity": _int(d.get("Waitlist Capacity")), "waitlist_seats_available": _int(d.get("Waitlist Seats Available"))}


def parse_description(html: str) -> str:
    return " ".join(_fetch.html_to_text(html)[1].split())


def parse_prerequisites(html: str) -> str:
    """The catalog prerequisites as one line. Banner's table has a row per course or test with its And/Or and its
    parentheses: '( Chemistry 111 (Undergraduate, grade D) Or Chemistry 1111 (Undergraduate, grade D) ) And ( ... )'.
    Without a table, the panel's own sentence ('No prerequisite information available.')."""
    rows = []
    for row in _ROW.findall(html):
        cells = [" ".join(_TAG.sub(" ", c).split()) for c in _CELL.findall(row)]
        if len(cells) < 9:
            continue
        andor, opening, test, score, subject, number, level, grade, closing = cells[:9]
        what = f"{test} {score}".strip() if test else f"{subject} {number}".strip()
        detail = ", ".join(x for x in (level, f"grade {grade}" if grade else "") if x)
        rows.append(" ".join(x for x in (andor, opening, what, f"({detail})" if detail else "", closing) if x))
    if rows:
        return " ".join(rows)
    text = _fetch.html_to_text(html)[1]
    return " ".join(re.sub(r"^#+\s*Catalog Prerequisites\s*", "", text).split())


def parse_meetings(fmt: dict) -> list[dict]:
    out = []
    for m in (fmt or {}).get("fmt") or []:
        out.append({**meeting(m.get("meetingTime") or {}), "instructors": instructors(m.get("faculty"))})
    return out
