"""library: the University of Idaho Library's catalog, what the library holds and where, with the record's page.

Upstream: Primo VE on the Orbis Cascade Alliance's Ex Libris host, https://alliance-uidaho.primo.exlibrisgroup.com, the
discovery service behind the library's search page. Its page is a single-page app over a public REST endpoint, which
answers without a token or key: /primaws/rest/pub/pnxs?q=field,operator,words&vid=01ALLIANCE_UID:UID&tab=…&scope=… the
hits with each record's display fields, identifiers and delivery (Primo's availability code, the physical copy's library,
location, call number and status, the link resolver for an article), and /pnxs/{L|PC}/{recordid} one record with its
table of contents and summary. The Everything scope (DN_and_CI) is the local catalog and the central index together;
CourseReserves and SPECAW (Special Collections and Archives) are local. Verso (the research portal), interlibrary loan and
a person's own account are not here. A search is cached an hour, a record an hour, since availability changes.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://alliance-uidaho.primo.exlibrisgroup.com"
PNXS = f"{BASE}/primaws/rest/pub/pnxs"
VID, INST = "01ALLIANCE_UID:UID", "01ALLIANCE_UID"
SEARCH_PAGE = f"{BASE}/discovery/search?vid={VID}"
LIBRARY_PAGE = "https://www.lib.uidaho.edu/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai4ra-mcp/0.1; +https://github.com/ui-insight/ai4ra-mcp)"}
# The view's scopes, from its configuration: name here -> (tab, scope) as the endpoint wants them.
SCOPES = {"everything": ("Everything", "DN_and_CI"), "reserves": ("CourseReserves", "CourseReserves"), "special": ("SPECAW_Slot", "SPECAW")}
FIELDS = {"any": "any", "title": "title", "creator": "creator", "author": "creator", "subject": "sub", "isbn": "isbn", "issn": "issn"}
SORTS = ("rank", "date", "title", "author")
# Primo's resource-type facet values, the facet's own vocabulary as the discovery page shows it, passed through as given.
# Print books are the value pbooks and e-books the value books, so 'books' here is both, OR-ed through multiFacets (a search
# for Pratchett with the books value alone found two e-books and none of the novels on the shelf, 2026-10-19); 'pbooks' and
# 'ebooks' pick one of them.
TYPES = ("pbooks", "ebooks","books", "articles", "journals", "dissertations", "book_chapters", "conference_proceedings", "reviews", "newspaper_articles",
         "government_documents", "reference_entrys", "videos", "audios", "images", "maps", "scores", "databases", "archival_material_manuscripts", "other")
# What Primo's availability codes meant on the records probed 2026-10-19, in the catalog's own terms.
AVAILABILITY = {
    "available_in_library": "a physical copy is on the shelf here, at the library, location and call number given",
    "unavailable": "the library holds a physical copy and it is out or otherwise not on the shelf",
    "no_inventory": "the record is in the catalog but no copy is held here; record_owner says whose record it is, and the catalog page is where a request is made",
    "fulltext": "online, through the link resolver (openurl), which may ask for a university login",
    "fulltext_multiple": "online through more than one provider, through the link resolver",
    "fulltext_linktorsrc": "online at the source's own site, linked from the catalog page",
    "not_restricted": "online with no login (open access), through the link resolver",
    "ResourceSharingRequest": "the library's copy is out on loan to another Alliance library (Summit Lending) and is not on the shelf; the catalog page is where a request is made",
}
MAX_SUBJECTS = 8
_ADATA = ("isbn", "issn", "doi", "jtitle", "volume", "issue", "spage", "epage", "pmid")
_TAG = re.compile(r"<[^>]+>")
_cache = TTLCache()

mcp = MCPServer(
    "library",
    instructions="The University of Idaho Library's catalog (Primo): what the library holds by words, title, author, subject, ISBN or ISSN, with where a physical copy sits and whether it is on the shelf, articles with their DOI and full-text status, and one record in full with its table of contents; Course Reserves and Special Collections as scopes. No key. Read library_index first.",
)


def _first(v) -> str | None:
    if isinstance(v, list):
        v = v[0] if v else None
    return v.strip() if isinstance(v, str) and v.strip() else None


def _names(v) -> list[str]:
    """Primo's name fields carry a display form and a search form joined by $$Q; the display form is kept."""
    return [s.split("$$Q")[0].strip().rstrip(",") for s in (v or []) if isinstance(s, str) and s.strip()]


def _text(v) -> str | None:
    s = _first(v)
    return _TAG.sub("", s).strip() if s else None


def _location(loc: dict | None) -> dict | None:
    if not loc:
        return None
    return {"library": loc.get("mainLocation"), "location": loc.get("subLocation"), "call_number": loc.get("callNumber"), "status": loc.get("availabilityStatus")}


def record_page(record_id: str, context: str) -> str:
    return f"{BASE}/discovery/fulldisplay?docid={record_id}&context={context}&vid={VID}"


def slim_doc(doc: dict, full: bool = False) -> dict:
    pnx, delivery = doc.get("pnx") or {}, doc.get("delivery") or {}
    display, addata = pnx.get("display") or {}, pnx.get("addata") or {}
    record_id, context = _first((pnx.get("control") or {}).get("recordid")), doc.get("context") or "L"
    availability = _first(delivery.get("availability"))
    out: dict = {
        "id": record_id, "context": context, "title": _first(display.get("title")), "creators": _names(display.get("creator")),
        "contributors": _names(display.get("contributor")), "type": _first(display.get("type")), "publisher": _first(display.get("publisher")),
        "year": _first(display.get("creationdate")), "format": _first(display.get("format")), "language": _first(display.get("language")),
        "edition": _first(display.get("edition")), "part_of": _first(display.get("ispartof")), "subjects": _names(display.get("subject"))[:MAX_SUBJECTS],
        "availability": availability, "availability_means": AVAILABILITY.get(availability or ""),
        "location": _location(delivery.get("bestlocation")), "record_owner": delivery.get("recordOwner"),
        "link": record_page(record_id, context) if record_id else None,
    }
    for k in _ADATA:
        if addata.get(k):
            out[k] = addata[k] if k in ("isbn", "issn") else _first(addata[k])
    if full:
        # The link resolver's URL runs to 900 characters and leads where the catalog page does; it is on the record alone.
        out["openurl"] = delivery.get("almaOpenurl") or None
        out["subjects"] = _names(display.get("subject"))
        out["summary"] = _text(display.get("lds99")) or _text(display.get("description"))
        out["series"] = _text(display.get("description")) if (_first(display.get("description")) or "").startswith("<b>Series") else None
        out["contents"] = _text(display.get("contents"))
        out["holdings"] = [_location(h) for h in delivery.get("holding") or []]
        out["source"] = _first(display.get("source"))
    return out


async def _get(path: str, params: dict) -> dict:
    key = path + "?" + repr(sorted(params.items()))
    return await _cache.remember(key, HOUR, lambda: get_json(f"{PNXS}{path}", params, HEADERS))


@mcp.tool(name="library_index", annotations=_READ_ONLY)
async def library_index() -> dict:
    """How to use the University of Idaho Library catalog tools. READ THIS FIRST: the scopes, the fields, what availability means, how to cite."""
    return {
        "upstream": f"The University of Idaho Library's catalog, Primo VE on the Orbis Cascade Alliance host ({SEARCH_PAGE}); the library's page is {LIBRARY_PAGE}. No key.",
        "workflow": ["library_search once, with the field that fits: a title with field='title' and type='books' for 'does the library have X' (available=true for a copy on the shelf), an author with field='author', a topic with field='subject' or 'any'; read the hits and report, with one more search by another field when the first finds nothing and no more than that",
                     "library_record for one record's table of contents, summary, subjects and every holding, by the id library_search gave (an alma… id is a local record, context L; a cdi_… id is the central index, context PC)",
                     "cite the record with its link (the catalog page), and for an article the DOI and the journal citation (part_of)"],
        "scopes": {"everything": "the local catalog and the central index of articles and e-resources together (the catalog's Everything tab); the default", "reserves": "Course Reserves", "special": "Special Collections and Archives"},
        "fields": sorted(FIELDS), "types": list(TYPES), "sorts": list(SORTS),
        "availability": AVAILABILITY,
        "notes": ["Totals come as total_local (the library's own catalog) and total_central (the central index), and the hits are the first rows of Primo's ranking of both unless sort says otherwise: a title not among the ten returned is not thereby absent when the total is larger; narrow with type or available, or page with offset, before concluding.",
                  "field='title' matches the words as a phrase in the title ('small gods' finds Small Gods and not The God of Small Things); field='any' matches the words anywhere in any order. type='books' is print and e-books together; 'pbooks' print alone.",
                  "location is the best physical copy's library, location (floor or collection), call number and status; holdings in library_record list every copy. A Special Collections copy is for reading-room use only, as its location says.",
                  "Online items reach their full text from the record's catalog page (link), through the library's link resolver, which may ask for a university login; library_record carries the resolver URL (openurl). Whether the university licenses an article is what the availability code says, not whether it exists.",
                  "A hit carries up to eight subjects; library_record carries them all.",
                  "A title the person gives is searched as given, and a title that returns nothing is reported as not found, never replaced by a guessed title: ask the person which work they meant.",
                  "Not here: Verso (the research portal of theses and faculty outputs), interlibrary loan and Summit requests, renewals and the person's account; those are on the catalog page the link opens.",
                  "Nothing is held in memory: a title the catalog does not return is not in the catalog as searched, and a search by another field or spelling is the next step, not a guess."],
    }


@mcp.tool(name="library_search", annotations=_READ_ONLY)
async def library_search(query: str, field: str = "any", type: str = "", available: bool = False, scope: str = "everything", sort: str = "rank", offset: int = 0, rows: int = 10) -> dict:
    """Search the University of Idaho Library's catalog.

    One search answers most questions. For "does the library have X" search the title with field='title' and type='books'
    (available=True for a copy on the shelf), read the hits, and report; one more search by another field is reasonable when the
    first returns nothing, a third is not. Returns hits with id, title, creators, type, publisher, year, format, identifiers
    (ISBN, ISSN, DOI), the journal citation for an article, subjects, Primo's availability code with what it means, the physical
    copy's library, location and call number, and the record's catalog page; and the totals for the local catalog and the central
    index. The default scope mixes in the central index's articles, so a book question is narrower with type='books'.

    Args:
        query: Words, a title, a name, a subject, an ISBN or an ISSN, e.g. 'wheat breeding', 'Idaho a bicentennial history', '9780393056006'.
        field: 'any' (default, the words anywhere), 'title' (matched as a phrase), 'author', 'subject', 'isbn' or 'issn'.
        type: A resource type to keep: 'books' (print and e-books), 'pbooks' (print only), 'ebooks', 'articles' and the rest library_index lists; empty for all.
        available: True keeps physical copies on the shelf here. Default False.
        scope: 'everything' (default), 'reserves' (Course Reserves) or 'special' (Special Collections and Archives).
        sort: 'rank' (default), 'date', 'title' or 'author'.
        offset: First hit, 0-based. Default 0.
        rows: Hits to return, 1-50. Default 10.
    """
    q = " ".join((query or "").split())
    if not q:
        return {"error": "query is required"}
    f = FIELDS.get((field or "any").strip().lower())
    if not f:
        return {"error": f"field must be one of {sorted(FIELDS)}"}
    if scope not in SCOPES:
        return {"error": f"scope must be one of {sorted(SCOPES)}"}
    if sort not in SORTS:
        return {"error": f"sort must be one of {list(SORTS)}"}
    t = (type or "").strip().lower()
    if t and t not in TYPES:
        return {"error": f"type must be one of {list(TYPES)} or empty"}
    tab, scope_id = SCOPES[scope]
    # A title is matched as a phrase (Primo's exact operator), since contains ranks every record with the words somewhere
    # and buried Pratchett's Small Gods below ten sermons (2026-10-19); isbn and issn are exact; the rest contain the words.
    operator = "exact" if f in ("isbn", "issn", "title") else "contains"
    # Primo ignores case, so the query is lowered before it is sent and the cache sees one search for "Emperors" and "emperors".
    q = q.lower()
    params: dict = {"q": f"{f},{operator},{q}", "vid": VID, "tab": tab, "scope": scope_id, "inst": INST, "lang": "en",
                    "offset": max(0, int(offset or 0)), "limit": max(1, min(int(rows or 10), 50)), "pcAvailability": "false", "sort": sort}
    if t == "books":
        params["multiFacets"] = "facet_rtype,include,books|,|facet_rtype,include,pbooks"
    elif t:
        params["qInclude"] = f"facet_rtype,exact,{'books' if t == 'ebooks' else t}"
    if available:
        params["qInclude"] = "|,|".join(x for x in (params.get("qInclude"), "facet_tlevel,exact,available_p") if x)
    try:
        body = await _get("", params)
    except ValueError as e:
        return {"error": str(e), "link": SEARCH_PAGE}
    info = body.get("info") or {}
    hits = [slim_doc(d) for d in body.get("docs") or []]
    out = {"query": query.strip(), "field": field, "type": t or None, "available": bool(available), "scope": scope, "sort": sort, "offset": params["offset"], "returned": len(hits),
           "total_local": info.get("totalResultsLocal"), "total_central": info.get("totalResultsPC"), "total": info.get("total"), "hits": hits,
           "link": f"{SEARCH_PAGE}&tab={tab}&search_scope={scope_id}&query={f},{operator},{q.replace(' ', '%20')}"}
    total = info.get("total") if isinstance(info.get("total"), int) else None
    if total is not None and params["offset"] + len(hits) < total:
        out["next_offset"] = params["offset"] + len(hits)
    if not hits:
        out["note"] = "The catalog returns nothing for this search as phrased. One more search by title with fewer words is reasonable; after that, report that the catalog has no record matching the title as given, with the search link, and ask the person which work they meant if the title was a guess."
    return out


@mcp.tool(name="library_record", annotations=_READ_ONLY)
async def library_record(id: str, context: str = "") -> dict:
    """One catalog record in full: title, creators, publisher, year, format, identifiers, subjects, summary, table of contents,
    availability, every holding with location and call number, the link resolver and the catalog page.

    Args:
        id: The record id from library_search, e.g. 'alma9921606601851' (local) or 'cdi_gutenberg_primary_43572' (central index).
        context: 'L' for a local record or 'PC' for the central index; empty picks by the id's prefix (alma… is L, anything else PC).
    """
    rid = (id or "").strip()
    if not rid:
        return {"error": "id is required; it comes from library_search"}
    ctx = (context or "").strip().upper() or ("L" if rid.startswith("alma") else "PC")
    if ctx not in ("L", "PC"):
        return {"error": "context must be 'L', 'PC' or empty"}
    adaptor = "Local Search Engine" if ctx == "L" else "Primo Central"
    try:
        body = await _get(f"/{ctx}/{rid}", {"vid": VID, "lang": "en", "search_scope": "DN_and_CI", "adaptor": adaptor})
    except ValueError as e:
        return {"error": str(e)}
    if "pnx" in body:
        return {**slim_doc(body, full=True), "read_from": record_page(rid, ctx)}
    return {"error": f"no record {rid} in context {ctx}; record ids come from library_search as given", "link": SEARCH_PAGE}


given(mcp, {"library_record": {"id": "library_search"}})
SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
