"""directory: the University of Idaho campus directory, the employees the university publishes at directory.uidaho.edu.

Who a person is at the university and how to reach them at work: name, university email, phone, title, department,
office and campus zip, by last name, first name, email or department. Employees only: students are behind the
university's login and not here. The upstream is the directory's own advanced search form (directory.py); every tool
is a read and no key is taken. Results are cached ten minutes, the department list a day.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, TTLCache
from ai4ra_mcp.common.skills import register_prompts
from ai4ra_mcp.servers.directory import directory

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
TEN_MINUTES = 10 * 60
ROWS, MAX_ROWS = 10, 30
_cache = TTLCache()

CAVEATS = [
    "This is the directory page's own search form, not a published API: a change to the site can alter a route or a layout without notice, and the only test is the live site. A tool whose route stops answering returns the HTTP status and the route.",
    "Employees only. The directory shows students only after the university's login, which this server never has, so a student, and a student employee, is not here and is not said to be absent from the university.",
    "The fields are the page's own and nothing more: name, university email, phone, title, department, office and campus zip. A phone the person has not listed is null. The directory knows nothing of a person's role on a project, their supervisor, their history or anything behind a login.",
    "Names are matched the way the form matches them: a last name, a first name or both, each as a prefix ('Lay' finds Layman), with sounds_like for a last name spelled from hearing. A one-word name goes in last_name. Several matches come back as a list to choose from, never guessed: narrow by first_name, email or department.",
    "A department is matched against the directory's own list (directory_departments): an exact name, or one name the fragment appears in; several come back as departments_matched, none is said.",
    "Cite a person by name and department with the directory link; a result is at most ten minutes old.",
]

mcp = MCPServer(
    "directory",
    instructions="The University of Idaho campus directory from directory.uidaho.edu, the employees the university publishes: people by last name, first name, email or department (directory_search), one person's details (directory_person), the departments (directory_departments). Employees only, no key. Read directory_index first.",
)


async def _departments() -> list[str]:
    return await _cache.remember("departments", DAY, directory.departments)


async def _resolve_department(fragment: str) -> tuple[str | None, list[str]]:
    """(the department as the directory names it, or None; the names that matched). An exact name wins, else one name
    the fragment appears in; several or none leave the first None and the list says which."""
    want = fragment.strip().lower()
    if not want:
        return "", []
    names = await _departments()
    exact = [n for n in names if n.lower() == want]
    if exact:
        return exact[0], exact
    partial = [n for n in names if want in n.lower()]
    return (partial[0] if len(partial) == 1 else None), partial


@mcp.tool(name="directory_index", annotations=_READ_ONLY)
async def directory_index() -> dict:
    """How to use the campus directory tools. READ THIS FIRST: who is in the directory, how names and departments match, and what a result holds."""
    return {
        "upstream": f"The University of Idaho campus directory at {directory.BASE}, read through its advanced search form at {directory.ADVANCED}; no login, no key; employees only, since students are shown only after the university's login",
        "workflow": ["directory_search by last_name, first_name, email (or its start) or department, any of them, each a prefix as the form matches it: one page of people (name, email, phone, department, status), rows 10, 20 or 30 a page with next_start; a search that matches one person returns that person's details instead",
                     "directory_person with enough of a name, an email or a department to match one person: their name, email, phone, title, department, office and campus zip; several matches come back as a list to narrow from",
                     "directory_departments for every department the directory lists, the names a department argument is matched against"],
        "notes": ["A result's fields are the page's own: name as 'Last, First', the university email, phone (null when the person lists none), department, and in a table the status ('Faculty or Staff'); a person's details add title, office and campus zip.",
                  "sounds_like matches a last name by its sound ('Smyth' finds Smith) and otherwise nothing; use it when a name was heard, not read.",
                  "Cite a person by name and department with the directory link; the directory changes as people come and go, and a result is at most ten minutes old."],
        "caveats": CAVEATS,
        "link": directory.BASE,
    }


@mcp.tool(name="directory_search", annotations=_READ_ONLY)
async def directory_search(last_name: str = "", first_name: str = "", email: str = "", department: str = "", sounds_like: bool = False,
                           rows: int = ROWS, start: int = 0) -> dict:
    """People in the University of Idaho campus directory by last name, first name, email or department: who they are and how to reach them at work.

    At least one of last_name, first_name, email, department. Each name field is a prefix as the form matches it; a department is matched
    against the directory's list. One page of people, or one person's details when exactly one matches. Employees only.

    Args:
        last_name: a last name or its start ('Layman', 'Lay'); a one-word name goes here.
        first_name: a first name or its start ('Nathan').
        email: a university email or its start ('nlayman', 'nlayman@uidaho.edu').
        department: a department as the directory names it ('Office of Sponsored Programs'), or a fragment one name contains ('Sponsored').
        sounds_like: match the last name by its sound ('Smyth' finds Smith).
        rows: people a page: 10, 20 or 30 (default 10; another number rounds up to the next of those).
        start: the offset of the first person (default 0); next_start of a page is the next page's start.
    """
    last_name, first_name, email = last_name.strip(), first_name.strip(), email.strip()
    if not (last_name or first_name or email or department.strip()):
        return {"error": "at least one of last_name, first_name, email, department"}
    depth, start = directory.depth_for(max(1, min(int(rows or ROWS), MAX_ROWS))), max(0, int(start or 0))
    try:
        dept, matched = await _resolve_department(department)
    except directory.DirectoryError as e:
        return e.as_error()
    if dept is None:
        return {"total": 0, "people": [], "departments_matched": matched,
                "error": (f"'{department}' matches {len(matched)} departments; pass one name in full" if matched else f"no department matching '{department}'")}

    async def make():
        found = await directory.search(last_name, first_name, email, dept, sounds_like, depth, start)
        out = {"query": {k: v for k, v in (("last_name", last_name), ("first_name", first_name), ("email", email), ("department", dept), ("sounds_like", sounds_like)) if v},
               "total": found["total"], "start": start, "people": found["people"], "link": directory.ADVANCED}
        if found["total"] == 1:
            out["note"] = "One person matched, so the directory showed their details (title, office, campus zip) in place of a table row."
        elif start + len(found["people"]) < found["total"] and found["people"]:
            out["next_start"] = start + len(found["people"])
        return out

    try:
        return await _cache.remember(f"search:{last_name.lower()}:{first_name.lower()}:{email.lower()}:{dept}:{sounds_like}:{depth}:{start}", TEN_MINUTES, make)
    except directory.DirectoryError as e:
        return e.as_error()


@mcp.tool(name="directory_person", annotations=_READ_ONLY)
async def directory_person(last_name: str = "", first_name: str = "", email: str = "", department: str = "") -> dict:
    """One person in the University of Idaho campus directory: name, university email, phone, title, department, office and campus zip.

    Give enough to match one person: a last name with a first name, an email, or a name with a department. Several matches come
    back as a list to narrow from, never a guess. Employees only.

    Args:
        last_name: a last name or its start ('Layman').
        first_name: a first name or its start ('Nathan').
        email: a university email or its start ('nlayman').
        department: a department as the directory names it, or a fragment one name contains.
    """
    found = await directory_search(last_name, first_name, email, department, False, ROWS, 0)
    if "error" in found:
        return found
    if found["total"] == 1:
        return {"person": found["people"][0], "link": directory.ADVANCED}
    if found["total"] == 0:
        return {"total": 0, "error": "no one in the directory matches; a student, or anyone not an employee, is not in it"}
    return {"total": found["total"], "people": found["people"], "next_start": found.get("next_start"),
            "error": f"{found['total']} people match; narrow by first_name, email or department"}


@mcp.tool(name="directory_departments", annotations=_READ_ONLY)
async def directory_departments() -> dict:
    """Every department the University of Idaho campus directory lists, as it names them: the values a department argument is matched against."""
    try:
        names = await _departments()
    except directory.DirectoryError as e:
        return e.as_error()
    return {"total": len(names), "departments": names, "link": directory.ADVANCED}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A department the model names waits on the directory's own list (#40); a person's name is the conversation's own.
given(mcp, {"directory_search": {"department": "directory_departments"},
            "directory_person": {"department": "directory_departments"}})
