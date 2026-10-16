"""The University of Idaho campus directory at directory.uidaho.edu, read through its advanced search form.

The directory publishes its employees with no login: name, university email, phone, title, department, office and
campus zip. Students sit behind the university's single sign-on and are not here. The advanced form takes a last
name, a first name, an email (or its start), a department from its own list, and a sounds-like switch; it answers
with a table of ten, twenty or thirty people a page (name, email, phone, department, status) and, when exactly one
person matches, with that person's details instead. Only what the page shows is read.

The page also carries an internal identifier for each person, Banner's PIDM, in its popup attributes, its detail
links and its autocomplete JSON. Nothing here reads, keeps or follows it: the detail route and the autocomplete are
not used, the table is read for its visible cells, and the identifier is reported to the university as a defect
(2026-10-15), so its presence is not assumed either way. Routes confirmed without a login on 2026-10-15.
"""

from __future__ import annotations

import html as _html
import re

import httpx

from ai4ra_mcp.common.http import HEADERS

BASE = "https://directory.uidaho.edu/"
ADVANCED = BASE + "advanced"
SEARCH = BASE + "search"
DEPTHS = (10, 20, 30)
TIMEOUT = 30
_TOTAL = re.compile(r"<h2>\s*(\d+) matches? (?:was|were) found\s*</h2>")
_NAME = re.compile(r"<h2>\s*([^<]+?)\s*</h2>")
_TABLE = re.compile(r'<table class="Cdir_Table.*?</table>', re.S)
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_HEAD = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_LINK_TEXT = re.compile(r"<a [^>]*>(.*?)</a>", re.S)
_MAILTO = re.compile(r'href="mailto:([^"]+)"')
_DETAIL = re.compile(r'<li>\s*<span role="heading">([^<]+?):</span>(.*?)</li>', re.S)
_SELECT = re.compile(r'<select name="dept".*?</select>', re.S)
_OPTION = re.compile(r'<option[^>]*value="([^"]*)"')
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_DETAIL_KEYS = {"Phone": "phone", "Email": "email", "Title": "title", "Department": "department", "Office": "office", "Campus Zip": "campus_zip"}


class DirectoryError(Exception):
    """The directory answered a route with something other than what the route returns: a status, a page with
    neither a results table nor a person's details, or no connection."""

    def __init__(self, route: str, status: int | None, detail: str):
        super().__init__(f"the directory answered {status if status is not None else 'nothing'} on {route}: {detail}")
        self.route, self.status, self.detail = route, status, detail

    def as_error(self) -> dict:
        return {"error": str(self), "upstream": BASE + self.route,
                "note": "This is the directory page's own form, not a published API; a change to the site can alter a route or a layout without notice. Check the page itself: " + ADVANCED}


async def _get(route: str, params: dict | None = None) -> str:
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(route, params=params)
    except httpx.HTTPError as e:
        raise DirectoryError(route, None, str(e)) from e
    if resp.status_code != 200:
        raise DirectoryError(route, resp.status_code, "not the 200 the route returns")
    if "Cdir_" not in resp.text:
        raise DirectoryError(route, resp.status_code, "a page that is not the directory's (a login page, or a changed site)")
    return resp.text


def text(fragment: str) -> str:
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", fragment))).strip()


def depth_for(rows: int) -> int:
    """The page size the form offers that holds `rows`: 10, 20 or 30."""
    return next((d for d in DEPTHS if d >= rows), DEPTHS[-1])


async def search(last_name: str = "", first_name: str = "", email: str = "", department: str = "", sounds_like: bool = False,
                 depth: int = 10, offset: int = 0) -> dict:
    """One page of the advanced search: {"total", "people"}, people being table rows or, on a single match, one details record."""
    params = {"tab": "advanced", "pt": "emp", "FirstName": first_name, "LastName": last_name, "email": email,
              "dept": department or "All", "major": "All", "depth": depth, "offset": offset}
    if sounds_like:
        params["SoundsLike"] = "on"
    return parse_results(await _get("search", params))


def parse_results(page: str) -> dict:
    """The results page read down to what it shows: the count and the table's visible cells, or one person's details.
    The table's popup attributes and detail links, which carry an internal identifier, are not read."""
    m = _TOTAL.search(page)
    if m:
        return {"total": int(m.group(1)), "people": parse_table(page)}
    if "Cdir_DetailsList" in page:
        return {"total": 1, "people": [parse_details(page)]}
    raise DirectoryError("search", 200, "neither a results table nor a person's details on the page")


def parse_table(page: str) -> list[dict]:
    m = _TABLE.search(page)
    if not m:
        return []
    people = []
    for row in _ROW.findall(m.group(0)):
        if 'scope="col"' in row:
            continue
        head = _HEAD.search(row)
        cells = _CELL.findall(row)
        if not head or len(cells) < 3:
            continue
        links = _LINK_TEXT.findall(head.group(1))
        mail = _MAILTO.search(head.group(1))
        people.append({"name": text(links[0]) if links else text(head.group(1)), "email": mail.group(1) if mail else None,
                       "phone": text(cells[0]) or None, "department": text(cells[1]) or None, "status": text(cells[2]) or None})
    return people


def parse_details(page: str) -> dict:
    """One person's details view: name from the heading, then each labelled line; 'Not listed' is None."""
    name = _NAME.search(page)
    out: dict = {"name": text(name.group(1)) if name else None}
    for label, value in _DETAIL.findall(page):
        key = _DETAIL_KEYS.get(text(label))
        if key:
            v = text(value)
            out[key] = None if not v or v.lower() == "not listed" else v
    # The directory shows the first 30 characters of a title ("Director, Office of Sponsored", "Research Administration Data S");
    # a title exactly that long is almost surely cut, and a reader must not finish it by guessing.
    if out.get("title") and len(out["title"]) >= 30:
        out["title_truncated"] = True
    return out


async def departments() -> list[str]:
    """Every department the advanced form lists, in the form's order, without its 'All'."""
    page = await _get("advanced")
    m = _SELECT.search(page)
    if not m:
        raise DirectoryError("advanced", 200, "no department list on the page")
    return [_html.unescape(v) for v in _OPTION.findall(m.group(0)) if v and v != "All"]
