"""classes: the University of Idaho class schedule and course catalog, from the registrar's public Browse Classes
and Browse Course Catalog.

The schedule: who teaches what, when and where, by term, subject, course number or instructor, and one section in
full. The catalog: courses by subject, number or title, and one course's record. The upstream is the pages' own
interface (banner.py); every tool is a read and no key is taken. Results are cached ten minutes, the term list an hour.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import HOUR, TTLCache
from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.skills import register_prompts
from ai4ra_mcp.servers.classes import banner

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
TEN_MINUTES = 10 * 60
ROWS, MAX_ROWS = 25, 100
_TERM_CODE = re.compile(r"^\d{6}$")
_cache = TTLCache()

CAVEATS = [
    "This is the schedule page's own internal interface, not a published API: a Banner upgrade can change a route without notice, and the only test is the live site. A tool whose route stops answering returns the HTTP status and the route.",
    "Instructors are matched by name, and Banner has no public lookup from a NetID or email. A name that matches several instructors comes back as a list to choose from, never guessed: pass one of the listed names in full. Each section lists its instructors' names and university emails, so a match can be confirmed against an email.",
    "The schedule knows who teaches what, when and where, and the catalog knows what a course is; neither knows degree requirements, who is enrolled, or anything behind a login.",
    "The catalog and the schedule disagree at the edges: a course can be in the catalog with no sections this term, and a section can exist for a course whose catalog entry has ended. Each tool says which it read: classes_search and classes_section the schedule, classes_catalog and classes_course the catalog.",
    "Course materials are not here: Banner's bookstore panel carries no materials, only the Day One Access link classes_section returns.",
    "With no term given, the newest term open to registration is searched: today's term until the next term's registration opens, then the next. Name the term when it matters.",
]

mcp = MCPServer(
    "classes",
    instructions="The University of Idaho class schedule and course catalog from the registrar's public Browse Classes and Browse Course Catalog: sections by term, subject, course number or instructor name (classes_search), one section in full (classes_section), courses by subject, number or keyword (classes_catalog), one course's catalog record (classes_course), the terms (classes_terms). No key. Read classes_index first.",
)


def term_entry(t: dict) -> dict:
    desc = t.get("description") or ""
    return {"code": t.get("code"), "name": re.sub(r"\s*\(View Only\)\s*$", "", desc, flags=re.I).strip(), "view_only": "view only" in desc.lower()}


async def _terms() -> list[dict]:
    """Every term, newest first, cached an hour: one list for the terms tool and for resolving a term a person names, so a
    term older than the newest few resolves and the list the model reads is the schedule's whole reach (#43)."""
    return await _cache.remember("terms", HOUR, banner.get_terms)


async def _resolve_term(term: str) -> tuple[str, str]:
    """(code, name) for a term code ('202610'), a term name ('Fall 2026'), or '' for the newest term open to registration."""
    terms = [term_entry(t) for t in await _terms()]
    want = (term or "").strip()
    if not want:
        found = next((t for t in terms if not t["view_only"]), None) or (terms[0] if terms else None)
        if not found:
            raise ValueError("Banner listed no terms")
        return found["code"], found["name"]
    if _TERM_CODE.match(want):
        found = next((t for t in terms if t["code"] == want), None)
        return want, found["name"] if found else want
    found = next((t for t in terms if t["name"].lower() == want.lower()), None)
    if not found:
        raise ValueError(f"no term named '{want}'; the terms are " + ", ".join(f"{t['name']} ({t['code']})" for t in terms))
    return found["code"], found["name"]


_WORD = re.compile(r"[a-z]+")


def _words(name: str) -> list[str]:
    return _WORD.findall((name or "").lower())


def lookup_word(fragment: str) -> str:
    """The one word Banner's instructor lookup is asked for: a 'Last, First' name's surname, otherwise the last word
    ('Tanya Miura' is looked up as Miura). The lookup takes a fragment of a name, not a whole one."""
    head = fragment.split(",")[0] if "," in fragment else fragment
    words = head.split()
    return (words[0] if "," in fragment else words[-1]) if words else fragment.strip()


def choose_instructor(fragment: str, matches: list[dict]) -> tuple[dict | None, list[str]]:
    """(the one instructor to search for, the names matched). One match is it; among several, the one whose name
    equals the fragment, else the one whose name has every word of it when only one does; otherwise none and the list."""
    names = [m.get("description") or "" for m in matches]
    if len(matches) == 1:
        return matches[0], names
    want = _words(fragment)
    exact = [m for m in matches if _words(m.get("description")) == want]
    if len(exact) == 1:
        return exact[0], names
    having = [m for m in matches if all(w in _words(m.get("description")) for w in want)]
    if len(having) == 1:
        return having[0], names
    return None, names


@mcp.tool(name="classes_index", annotations=_READ_ONLY)
async def classes_index() -> dict:
    """How to use the class schedule tools. READ THIS FIRST: what the schedule knows, the current term, and what to make of an instructor match."""
    out = {
        "upstream": f"The registrar's public Browse Classes at {banner.BROWSE} and Browse Course Catalog at {banner.CATALOG} (Banner Student Registration Self-Service), read through the pages' own interface; no login, no key",
        "workflow": ["classes_search with a subject ('BIOL'), a course number, or an instructor's name (a fragment, 'Miura'; a full name 'Miura, Tanya A.' when the fragment matched several), for the newest open term unless term says otherwise: the schedule's sections",
                     "classes_section with the term and the CRN of one result: its description, meetings with rooms and dates, prerequisites, corequisites, restrictions, cross-listed and linked sections, attributes, fees, the Day One Access link and enrollment",
                     "classes_catalog with a subject, a course number or a keyword (a word of the title or the catalog description), when a person names a topic rather than a section: the catalog's courses",
                     "classes_course with the term, subject and course number: the catalog's record of the course, as opposed to one section of it",
                     "classes_terms for every term the schedule has, newest first, with code, name and which are view-only (closed to registration): the whole list, so how far back the schedule reaches is read from it"],
        "notes": ["A section's instructors carry name, email and whether primary; a result's meets line is days (M T W R F S U), times, building and room, 'TBA' when none is scheduled.",
                  "classes_search needs at least one of subject, course_number, instructor; classes_catalog one of subject, course_number, keyword. rows up to 100 a page; next_start is the start of the next page when there is one.",
                  "Restrictions are the registrar's rules as published, one string each, with the majors, colleges, levels, cohorts or campuses named; attributes are the catalog's designations as published; fees are description and amount.",
                  "Cite a section by term, subject, number, section and CRN, and a course by subject and number; the schedule changes through the term, and a result is at most ten minutes old."],
        "caveats": CAVEATS,
    }
    try:
        code, name = await _resolve_term("")
        out["current_term"] = {"code": code, "name": name}
    except (banner.BannerError, ValueError) as e:
        out["current_term"] = e.as_error() if isinstance(e, banner.BannerError) else {"error": str(e)}
    return out


@mcp.tool(name="classes_terms", annotations=_READ_ONLY)
async def classes_terms() -> dict:
    """Every term the schedule has, newest first, as code, name and whether view-only (closed to registration; still
    searchable). The whole list: the oldest term here is as far back as the schedule reaches."""
    try:
        terms = await _terms()
    except banner.BannerError as e:
        return e.as_error()
    return {"total": len(terms), "terms": [term_entry(t) for t in terms]}


@mcp.tool(name="classes_search", annotations=_READ_ONLY)
async def classes_search(term: str = "", subject: str = "", course_number: str = "", instructor: str = "", rows: int = ROWS, start: int = 0) -> dict:
    """Sections of the class schedule by subject, course number or instructor: who teaches what, when and where.

    At least one of subject, course_number, instructor. An instructor is matched by name: one match is searched;
    several come back as instructors_matched to choose from (pass one in full); none is said.

    Args:
        term: a term code ('202610') or name ('Fall 2026'); empty for the newest term open to registration.
        subject: a subject code ('BIOL', 'CS'); empty for any.
        course_number: a course number ('1010'); empty for any.
        instructor: part of an instructor's name ('Miura'), or a full name as the schedule shows it ('Miura, Tanya A.').
        rows: sections a page, 1 to 100 (default 25).
        start: the offset of the first section (default 0); next_start of a page is the next page's start.
    """
    subject, course_number, instructor = (subject or "").strip().upper(), (course_number or "").strip(), (instructor or "").strip()
    if not (subject or course_number or instructor):
        return {"error": "at least one of subject, course_number, instructor"}
    rows, start = max(1, min(int(rows or ROWS), MAX_ROWS)), max(0, int(start or 0))
    try:
        code, name = await _resolve_term(term)
    except ValueError as e:
        return {"error": str(e)}
    except banner.BannerError as e:
        return e.as_error()

    async def make():
        async with banner.session(code) as client:
            chosen, names = None, []
            if instructor:
                chosen, names = choose_instructor(instructor, await banner.find_instructors(client, code, lookup_word(instructor)))
                if chosen is None:
                    return {"term": code, "term_name": name, "total": 0, "sections": [], "instructors_matched": names,
                            "error": (f"'{instructor}' matches {len(names)} instructors in {name}; pass one name in full" if names
                                      else f"no instructor matching '{instructor}' teaches in {name}")}
            found = await banner.search(client, code, subject, course_number, chosen["code"] if chosen else "", rows, start)
        sections = [banner.slim_section(s) for s in found.get("data") or []]
        total = int(found.get("totalCount") or 0)
        out = {"term": code, "term_name": name, "total": total, "start": start, "sections": sections}
        if start + len(sections) < total and sections:
            out["next_start"] = start + len(sections)
        if instructor:
            out["instructors_matched"] = names
        return out

    try:
        return await _cache.remember(f"search:{code}:{subject}:{course_number}:{instructor.lower()}:{rows}:{start}", TEN_MINUTES, make)
    except banner.BannerError as e:
        return e.as_error()


@mcp.tool(name="classes_section", annotations=_READ_ONLY)
async def classes_section(term: str, crn: str) -> dict:
    """One section by term and CRN: its catalog description, details, meetings with rooms and dates, prerequisites and enrollment.

    Args:
        term: the term code ('202610') or name ('Fall 2026') the CRN belongs to.
        crn: the course reference number from classes_search.
    """
    crn = (crn or "").strip()
    if not crn.isdigit():
        return {"error": "crn is the section's course reference number, digits only, from classes_search"}
    try:
        code, name = await _resolve_term(term)
    except ValueError as e:
        return {"error": str(e)}
    except banner.BannerError as e:
        return e.as_error()

    async def make():
        async with banner.session(code) as client:
            raw = await banner.details(client, code, crn)
        details = banner.parse_details(raw["details"])
        labelled = banner._labelled(raw["details"])
        meetings = banner.parse_meetings(raw["meetings"])
        return {"crn": crn, "term": code, "term_name": name, "read_from": "the schedule",
                "title": labelled.get("Title"), "subject": labelled.get("Subject"), "number": (labelled.get("Course Number", "").split() or [None])[0],
                "description": banner.parse_description(raw["description"]), "details": details, "meetings": meetings,
                "instructors": next((m["instructors"] for m in meetings if m["instructors"]), []),
                "prerequisites": banner.parse_prerequisites(raw["prerequisites"]), "corequisites": banner.parse_text_or_none(raw["corequisites"]),
                "restrictions": banner.parse_restrictions(raw["restrictions"]),
                "cross_listed": banner.parse_crn_table(raw["cross_listed"]), "linked": banner.parse_crn_table(raw["linked"]),
                "attributes": banner.parse_attributes(raw["attributes"]), "fees": banner.parse_fees(raw["fees"]),
                "day_one_access_url": banner.parse_day_one_link(raw["bookstore"]),
                "enrollment": banner.parse_enrollment(raw["enrollment"]), "link": banner.BROWSE}

    try:
        return await _cache.remember(f"section:{code}:{crn}", TEN_MINUTES, make)
    except banner.BannerError as e:
        return e.as_error()


@mcp.tool(name="classes_catalog", annotations=_READ_ONLY)
async def classes_catalog(term: str = "", subject: str = "", course_number: str = "", keyword: str = "", rows: int = ROWS, start: int = 0) -> dict:
    """Courses in the course catalog by subject, course number or a keyword of the title or description: what a course is, for a term.

    The catalog's answer when a person names a topic rather than a section. At least one of subject, course_number,
    keyword. Each course says whether it has sections this term (has_sections); classes_search finds them.

    Args:
        term: a term code ('202610') or name ('Fall 2026'); empty for the newest term open to registration.
        subject: a subject code ('BIOL', 'CS'); empty for any.
        course_number: a course number ('1010'); empty for any.
        keyword: a word of the course title or catalog description ('microbiology'); empty for any.
        rows: courses a page, 1 to 100 (default 25).
        start: the offset of the first course (default 0); next_start of a page is the next page's start.
    """
    subject, course_number, keyword = (subject or "").strip().upper(), (course_number or "").strip(), (keyword or "").strip()
    if not (subject or course_number or keyword):
        return {"error": "at least one of subject, course_number, keyword"}
    rows, start = max(1, min(int(rows or ROWS), MAX_ROWS)), max(0, int(start or 0))
    try:
        code, name = await _resolve_term(term)
    except ValueError as e:
        return {"error": str(e)}
    except banner.BannerError as e:
        return e.as_error()

    async def make():
        async with banner.session(code, "courseSearch") as client:
            found = await banner.search_catalog(client, code, subject, course_number, keyword, rows, start)
        courses = [banner.slim_course(c) for c in found.get("data") or []]
        total = int(found.get("totalCount") or 0)
        out = {"term": code, "term_name": name, "read_from": "the catalog", "total": total, "start": start, "courses": courses}
        if start + len(courses) < total and courses:
            out["next_start"] = start + len(courses)
        return out

    try:
        return await _cache.remember(f"catalog:{code}:{subject}:{course_number}:{keyword.lower()}:{rows}:{start}", TEN_MINUTES, make)
    except banner.BannerError as e:
        return e.as_error()


@mcp.tool(name="classes_course", annotations=_READ_ONLY)
async def classes_course(term: str, subject: str, course_number: str) -> dict:
    """One course's catalog record by term, subject and number: description, prerequisites, corequisites, restrictions, attributes and fees.

    The course as the catalog defines it, as opposed to one section of it (classes_section).

    Args:
        term: a term code ('202610') or name ('Fall 2026'); empty for the newest term open to registration.
        subject: the subject code ('CHEM').
        course_number: the course number ('1120').
    """
    subject, course_number = (subject or "").strip().upper(), (course_number or "").strip()
    if not (subject and course_number):
        return {"error": "subject and course_number are both needed ('CHEM', '1120')"}
    try:
        code, name = await _resolve_term(term)
    except ValueError as e:
        return {"error": str(e)}
    except banner.BannerError as e:
        return e.as_error()

    async def make():
        async with banner.session(code, "courseSearch") as client:
            found = await banner.search_catalog(client, code, subject, course_number, "", 5, 0)
            course = next((c for c in found.get("data") or [] if c.get("courseNumber") == course_number), None)
            if course is None:
                return {"error": f"the catalog has no {subject} {course_number} in {name}", "term": code, "term_name": name, "read_from": "the catalog"}
            raw = await banner.course_details(client, code, subject, course_number)
        return {**banner.slim_course(course), "term": code, "term_name": name, "read_from": "the catalog",
                "description": banner.parse_text_or_none(raw["description"]), "prerequisites": banner.parse_prerequisites(raw["prerequisites"]),
                "corequisites": banner.parse_text_or_none(raw["corequisites"]), "restrictions": banner.parse_restrictions(raw["restrictions"]),
                "attributes": banner.parse_attributes(raw["attributes"]), "fees": banner.parse_fees(raw["fees"]), "link": banner.CATALOG}

    try:
        return await _cache.remember(f"course:{code}:{subject}:{course_number}", TEN_MINUTES, make)
    except banner.BannerError as e:
        return e.as_error()


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# The arguments that name a thing the schedule holds, and the tool that lists the values (#40): a term code the model
# worked out waits on classes_terms, a CRN on classes_search; a term named by the person ("Fall 2026") resolves as typed.
# Subject codes are left out: "biology" to BIOL is inference the person expects.
given(mcp, {"classes_search": {"term": "classes_terms"},
            "classes_section": {"term": "classes_terms", "crn": "classes_search"},
            "classes_catalog": {"term": "classes_terms"},
            "classes_course": {"term": "classes_terms"}})
