"""idstat: the Idaho Statutes, the codified law of the State of Idaho as the Legislature publishes it at legislature.idaho.gov.

What Idaho law says: the titles, a title's chapters, a chapter's sections, one section's text with its history, and
the Legislature's own full-text search of the code. The upstream is the Legislature's statute pages and its search
engine (idstat.py); every tool is a read and no key is taken. Pages are cached a day (the code changes once a year,
on July 1), searches an hour.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache
from ai4ra_mcp.common.skills import register_prompts
from ai4ra_mcp.servers.idstat import idstat

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
ROWS, MAX_ROWS = 10, 50
_cache = TTLCache()

CAVEATS = [
    "This is the current code only, as the Legislative Services Office publishes it: updated to the web each July 1 after the session, with no earlier versions and no session laws. The index reports the office's own statement of how current the text is. A law passed this session may not be in it yet.",
    "The pages are the Legislature's website, not a published API, and the search is its own engine; a change to either can alter a route or a layout without notice. A tool whose page stops answering returns the status and the page.",
    "The text is the statute as codified and its History line (the session laws that made it). Not here: the Idaho Constitution, the Administrative Code (IDAPA, published only as PDFs), bills, case law, or annotations.",
    "The search is the engine's: web-style words, a quoted phrase for exact wording, AND and OR; it ranks by relevance and returns the sections that match with a snippet, not the text. Read a section before quoting it.",
    "Cite a section as Idaho Code § TT-CCSS with its link; say the text is current through the session the index names.",
]

mcp = MCPServer(
    "idstat",
    instructions="The Idaho Statutes from legislature.idaho.gov: the titles (idstat_titles), a title's chapters (idstat_chapters), a chapter's sections (idstat_sections), one section's text and history by citation (idstat_section), and the Legislature's full-text search of the code (idstat_search). No key. Read idstat_index first.",
)


def _error(e: Exception, link: str | None = None) -> dict:
    out = {"error": str(e), "upstream": idstat.BASE, "note": "The Legislature's website, not a published API; a change to the site can alter a route or a layout without notice. Check the page itself."}
    if link:
        out["link"] = link
    return out


@mcp.tool(name="idstat_index", annotations=_READ_ONLY)
async def idstat_index() -> dict:
    """How to use the Idaho Statutes tools. READ THIS FIRST: how current the code is, how sections are cited, what a search matches."""
    try:
        current = await _cache.remember("currency", DAY, idstat.currency)
    except idstat.StatuteError:
        current = None
    return {
        "upstream": f"The Idaho Statutes as the Legislature publishes them at {idstat.BASE}, one page per title, chapter and section, and the Legislature's search of them at {idstat.SEARCH}; no login, no key",
        "current": current or "the Legislature's statement of how current the text is could not be read; see " + idstat.CURRENCY,
        "workflow": ["idstat_search with words or a quoted phrase for the sections that say it, each with a snippet and its citation",
                     "idstat_section with a citation (33-2901, 67-5309A) for the section's text, heading and history",
                     "idstat_titles, idstat_chapters and idstat_sections to walk the code's outline: 74 titles, a title's chapters, a chapter's section headings"],
        "notes": ["A citation is TT-CCSS: title, hyphen, chapter and a two-digit section, so 33-2901 is title 33 (Education), chapter 29, section 01; a letter suffix (67-5309A) is a section added between two others. The chapter is read from the citation, so a citation alone finds its page.",
                  "Titles that research administration reaches for: 33 Education (chapter 29 the University of Idaho's federal educational aid, 37 provisions for the state institutions of learning), 67 State Government and State Affairs (53 the personnel system, 57 purchasing), 74 Transparent and Ethical Government (1 the Public Records Act, 4 Ethics in Government). Confirm with idstat_chapters; the names are the Legislature's.",
                  "A section's text comes as paragraphs in the code's own order with its History line separate; the PDF of the whole chapter is on the chapter's entry.",
                  "The search engine answers the words a person gives, web-style: 'sponsored research' is two words anywhere, '\"board of regents\"' the phrase; results are sections ranked by the engine with the match count and a snippet, at most 50 a call and no further pages. The engine indexes each page whole, header included, so 'Idaho' and 'legislature' match every page and crowd the snippet; leave them out and search for the terms of art ('regents', 'sponsored', 'indirect cost')."],
        "caveats": CAVEATS,
        "link": idstat.BASE,
    }


@mcp.tool(name="idstat_titles", annotations=_READ_ONLY)
async def idstat_titles() -> dict:
    """Every title of the Idaho Code with its name, as the Legislature lists them: the numbers idstat_chapters takes."""
    try:
        found = await _cache.remember("titles", DAY, idstat.titles)
    except idstat.StatuteError as e:
        return _error(e, idstat.BASE)
    return {"total": len(found), "titles": found, "link": idstat.BASE}


@mcp.tool(name="idstat_chapters", annotations=_READ_ONLY)
async def idstat_chapters(title: int) -> dict:
    """The chapters of one title of the Idaho Code, each with its name, link and chapter PDF.

    Args:
        title: The title number, 1-74, from idstat_titles (33 is Education, 67 State Government and State Affairs).
    """
    try:
        t = int(title)
    except (TypeError, ValueError):
        return {"error": "title must be a number, 1-74"}
    if not 1 <= t <= 99:
        return {"error": "title must be a number, 1-74"}
    try:
        found = await _cache.remember(f"chapters:{t}", DAY, lambda: idstat.chapters(t))
    except idstat.StatuteError as e:
        return _error(e, idstat.title_url(t))
    return {"title": t, "heading": found["heading"], "total": len(found["chapters"]), "chapters": found["chapters"], "link": idstat.title_url(t)}


@mcp.tool(name="idstat_sections", annotations=_READ_ONLY)
async def idstat_sections(title: int, chapter: int) -> dict:
    """The sections of one chapter of the Idaho Code, each with its citation and heading: the outline of the chapter before reading a section.

    Args:
        title: The title number, from idstat_titles.
        chapter: The chapter number within the title, from idstat_chapters.
    """
    try:
        t, c = int(title), int(chapter)
    except (TypeError, ValueError):
        return {"error": "title and chapter must be numbers"}
    try:
        found = await _cache.remember(f"sections:{t}:{c}", DAY, lambda: idstat.sections(t, c))
    except idstat.StatuteError as e:
        return _error(e, idstat.chapter_url(t, c))
    return {"title": t, "chapter": c, "title_heading": found["title_heading"], "chapter_heading": found["chapter_heading"],
            "total": len(found["sections"]), "sections": found["sections"], "pdf": found["pdf"], "link": idstat.chapter_url(t, c)}


@mcp.tool(name="idstat_section", annotations=_READ_ONLY)
async def idstat_section(citation: str) -> dict:
    """One section of the Idaho Code by citation: its heading, text as paragraphs, and History line.

    Args:
        citation: The section as cited, 'TT-CCSS' with an optional letter: '33-2901', '67-5309A', '59-704'.
    """
    try:
        url = idstat.section_url(citation)
    except ValueError as e:
        return {"error": str(e)}
    try:
        found = await _cache.remember(f"section:{url}", DAY, lambda: idstat.section(citation))
    except idstat.StatuteError as e:
        return _error(e, url)
    return {"citation": found["section"] or idstat.parse_citation(citation)[2], **found}


@mcp.tool(name="idstat_search", annotations=_READ_ONLY)
async def idstat_search(query: str, rows: int = ROWS) -> dict:
    """The sections of the Idaho Code that say something, from the Legislature's own full-text search: each with its citation, match count, a snippet and link.

    Web-style words ('sponsored research'), a quoted phrase ('"board of regents"'), AND and OR. Ranked by the engine. Read a
    section with idstat_section before quoting it.

    Args:
        query: The words or phrase to find.
        rows: Sections to return, 1-50. Default 10.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "query is required"}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    try:
        found = await _cache.remember(f"search:{q.lower()}:{rows}", HOUR, lambda: idstat.search(q, rows))
    except idstat.StatuteError as e:
        return {"error": str(e), "upstream": idstat.SEARCH, "note": "The Legislature's own search engine, not a published API; try the words on the site itself."}
    out = {"query": q, "sections_matched": found["sections"], "hits": found["hits"], "returned": len(found["results"]), "results": found["results"],
           "link": f"{idstat.SEARCH}?IW_FIELD_WEB_STYLE={q.replace(' ', '+')}&IW_DATABASE=Idaho+Statutes"}
    if found["sections"] > len(found["results"]):
        out["note"] = f"{found['sections']} sections matched; the engine's first {len(found['results'])} by relevance are here (at most {MAX_ROWS} a call). Add words to narrow."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A title or chapter number the model names waits on the list that carries it (#40); a citation a person gives passes as given.
given(mcp, {"idstat_chapters": {"title": "idstat_titles"}, "idstat_sections": {"title": "idstat_titles", "chapter": "idstat_chapters"}})
