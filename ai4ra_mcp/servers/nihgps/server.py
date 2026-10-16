"""nihgps: the NIH Grants Policy Statement, the terms and conditions of NIH awards, as NIH publishes it at grants.nih.gov.

Upstream: https://grants.nih.gov/grants/policy/nihgps/HTML5/ (HTML, no key), the MadCap Flare web edition NIH publishes:
one page per section (section_7/7.9_allowability_of_costs_activities.htm), a table of contents in the edition's data
files (Data/Tocs/TOC_Web.js names the chunks, Data/Tocs/TOC_Web_Chunk<n>.js map each page to its title), and the
revision line on every page ("REVISED MARCH 2026. This document supersedes the April 2024 version"). A section page
holds the section's heading, its text, its tables (Exhibit 5, the selected items of cost, is a table of items and
explanations) and glossary popups, which are inline definitions and are dropped so a sentence reads once. A chapter's
own page ("7 Cost Consideration") is a placeholder that says to pick a section, so a chapter is answered from the table
of contents. About 280 pages. Pages and the contents are cached a day.
"""

from __future__ import annotations

import asyncio
import html as _html
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, TTLCache, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://grants.nih.gov/grants/policy/nihgps/HTML5/"
LANDING = "https://grants.nih.gov/policy-and-compliance/nihgps"
TOC = BASE + "Data/Tocs/TOC_Web.js"
PDF = "https://grants.nih.gov/grants/policy/nihgps/nihgps.pdf"
_CHUNKS = re.compile(r"numchunks:(\d+),prefix:'([^']+)'")
_ENTRY = re.compile(r"'(/[^']+\.htm)':\{i:\[([\d,]+)\],t:\[((?:'(?:[^'\\]|\\.)*',?)+)\](?:,b:\[((?:'[^']*',?)*)\])?")
_QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'")
_POPUP = re.compile(r'<span class="MCTextPopupBody[^"]*">.*?</span>\s*</a>', re.S)
_HEAD = re.compile(r"<h([1-4])[^>]*>(.*?)</h\1>", re.S)
_TABLE = re.compile(r'<table(?! class="masterp")[^>]*>.*?</table>', re.S)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_PARA = re.compile(r"</(?:p|li|h[1-6]|div|blockquote)>|<br\s*/?>", re.I)
_REVISED = re.compile(r'<p class="revised">(.*?)</p>', re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_NUM = re.compile(r"^(\d+(?:\.\d+)*)\s")
_cache = TTLCache()

mcp = MCPServer(
    "nihgps",
    instructions="The NIH Grants Policy Statement from grants.nih.gov: its table of contents (nihgps_toc), one section's text and tables by number or title (nihgps_section), words across a chapter's sections (nihgps_search). No key. Read nihgps_index first.",
)


def text(fragment: str) -> str:
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", _POPUP.sub("</a>", fragment)))).strip()


def parse_toc(index_js: str, chunks: list[str]) -> list[dict]:
    """Every page in the edition in the table's order: number ('7.9.1' when the title begins with one), title, path, url."""
    entries = []
    for chunk in chunks:
        for path, orders, titles, anchors in _ENTRY.findall(chunk):
            # One page can hold several entries (7.9 and 7.9.1 share a page); i, t and b run in step, b the anchor on the page.
            ts = [t.replace("\\u0027", "'").replace("\\'", "'").strip() for t in _QUOTED.findall(titles)]
            bs = _QUOTED.findall(anchors) if anchors else []
            for k, order in enumerate(o for o in orders.split(",") if o):
                t = ts[k] if k < len(ts) else ts[-1]
                anchor = bs[k] if k < len(bs) else ""
                m = _NUM.match(t)
                entries.append({"order": int(order), "number": m.group(1) if m else None, "title": t, "path": path.lstrip("/"), "anchor": anchor or None,
                                "url": BASE + path.lstrip("/") + anchor})
    entries.sort(key=lambda e: e["order"])
    return [e for e in entries if not e["path"].startswith("toc_")]


def chunk_names(index_js: str) -> list[str]:
    m = _CHUNKS.search(index_js)
    if not m:
        raise ValueError("the table of contents index names no chunks (the edition changed)")
    return [f"Data/Tocs/{m.group(2)}{i}.js" for i in range(int(m.group(1)))]


def parse_section(page: str) -> dict:
    """A section page read to its heading, text as paragraphs, tables as rows, and the edition's revision line."""
    i = page.find('data-mc-content-body')
    body = page[page.find(">", i) + 1:] if i >= 0 else page
    end = body.find('<div class="footer')
    if end > 0:
        body = body[:end]
    # The content body opens with the edition's revision line, breadcrumbs and search bar; the text begins at the section's heading.
    start = body.find("<h2")
    if start < 0:
        start = body.find("<h1")
    if start > 0:
        body = body[start:]
    revised = _REVISED.search(page)
    all_heads = [(int(lvl), text(h)) for lvl, h in _HEAD.findall(body)]
    # A section page's h1 is its keyword line and its h2 the heading; a chapter or part page has only an h1, which is its heading.
    heads = [h for h in all_heads if h[0] >= 2] or all_heads[:1]
    tables = []
    for t in _TABLE.findall(body):
        rows = [[text(c) for c in _CELL.findall(r)] for r in _ROW.findall(t)]
        rows = [r for r in rows if any(r)]
        if rows:
            tables.append({"header": rows[0] if len(rows) > 1 else None, "rows": rows[1:] if len(rows) > 1 else rows})
    without_tables = _TABLE.sub(" ", body)
    paras = [p for p in (text(x) for x in _PARA.split(without_tables)) if p and not p.startswith("You are here") and p not in ("Filter: All Files", "Submit Search")]
    if revised:
        paras = [p for p in paras if not p.startswith("REVISED")]
    heading = heads[0][1] if heads else None
    paras = [p for p in paras if not any(p == h for _, h in all_heads)]
    if paras and paras[0].startswith("[Intentionally left blank"):
        paras = []
    return {"heading": heading, "subheadings": [h for _, h in heads[1:]], "paragraphs": paras, "tables": tables, "revised": text(revised.group(1)) if revised else None}


async def _toc() -> list[dict]:
    async def make():
        index_js = await get_text(TOC)
        chunks = await asyncio.gather(*(get_text(BASE + name) for name in chunk_names(index_js)))
        toc = parse_toc(index_js, list(chunks))
        if not toc:
            raise ValueError("the table of contents came back empty (the edition changed)")
        return toc
    return await _cache.remember("toc", DAY, make)


async def _page(entry: dict) -> dict:
    return await _cache.remember(f"page:{entry['path']}", DAY, lambda: _read(entry["url"]))


async def _read(url: str) -> dict:
    return parse_section(await get_text(url))


def _match(toc: list[dict], want: str) -> list[dict]:
    """The entries a person's section names: an exact number, else a path, else every title carrying all the words."""
    w = want.strip().rstrip(".")
    exact = [e for e in toc if e["number"] == w]
    if exact:
        return exact
    by_path = [e for e in toc if e["path"].lower() == w.lower() or e["path"].lower().endswith("/" + w.lower())]
    if by_path:
        return by_path
    words = w.lower().split()
    return [e for e in toc if words and all(x in e["title"].lower() for x in words)]


@mcp.tool(name="nihgps_index", annotations=_READ_ONLY)
async def nihgps_index() -> dict:
    """How to use the NIH Grants Policy Statement tools. READ THIS FIRST: which revision this is, how sections are numbered and cited, what the GPS governs."""
    revised = None
    try:
        toc = await _toc()
        first = next((e for e in toc if e["path"] == "introduction.htm"), toc[0])
        revised = (await _page(first)).get("revised")
    except ValueError:
        toc = []
    return {
        "upstream": f"The NIH Grants Policy Statement, web edition at {BASE}, one page per section, read as NIH publishes it; the PDF is {PDF}; no key",
        "revision": revised or "the revision line could not be read; see " + LANDING,
        "sections": len(toc) or None,
        "workflow": ["nihgps_toc for the table of contents, or the sections whose titles carry words ('allowability', 'prior approval', 'closeout')",
                     "nihgps_section with a section number ('7.9', '8.1.2', '4.1.15') or a title for its text and tables",
                     "nihgps_search with words and a chapter number for the sections of that chapter that say them"],
        "notes": ["The GPS is in three parts: Part I general information (sections 1-3: glossary, NIH, the grant process), Part II the terms and conditions of NIH awards, Part IIA for all awards (4 public policy, 5-6 the award, 7 cost considerations, 8 administrative requirements, 9 multiple PD/PIs, 10 modular, 11 training, 12 fellowships, 13 SBIR/STTR, 14 conferences, 15 consortium agreements) and Part IIB for particular types (16-19), and Part III points of contact.",
                  "Cite as 'NIH GPS 7.9.1' with the section's link and the revision ('revised March 2026'). The GPS is a term and condition of every NIH award; it incorporates 2 CFR 200 (the ecfr server) and the award's notice can add to it.",
                  "A section's tables come as rows; Exhibit 5 in 7.9.1 is the selected items of cost, each row an item and NIH's rule for it. Glossary popups in the text are dropped so a sentence reads once; 1.2 is the glossary itself.",
                  "A chapter's own entry ('7 Cost Consideration') is a placeholder page; nihgps_section on a chapter number returns its sections from the table of contents instead."],
        "caveats": ["NIH's pages, not an API: a change to the edition can alter a layout without notice; the revision line on each page says which text this is.",
                    "The NIH Guide (the nihguide server) carries the notices that change policy between revisions; a notice newer than the revision governs."],
        "link": LANDING,
    }


@mcp.tool(name="nihgps_toc", annotations=_READ_ONLY)
async def nihgps_toc(query: str = "", chapter: str = "") -> dict:
    """The NIH Grants Policy Statement's table of contents, or the sections whose titles carry words, or one chapter's sections.

    Args:
        query: Words in a section title, e.g. 'prior approval', 'indirect', 'closeout'. Empty for the whole table.
        chapter: A chapter number ('7') to list that chapter's sections.
    """
    try:
        toc = await _toc()
    except ValueError as e:
        return {"error": str(e), "upstream": TOC}
    words = query.lower().split()
    ch = chapter.strip().rstrip(".")
    found = [e for e in toc if (not words or all(w in e["title"].lower() for w in words)) and (not ch or (e["number"] or "").split(".")[0] == ch)]
    return {"total": len(found), "sections": [{"number": e["number"], "title": e["title"], "link": e["url"]} for e in found], "link": LANDING}


@mcp.tool(name="nihgps_section", annotations=_READ_ONLY)
async def nihgps_section(section: str) -> dict:
    """One section of the NIH Grants Policy Statement: heading, text as paragraphs, tables as rows, and its subsections.

    Args:
        section: The section number ('7.9', '8.1.2.3', '4.1.15') or words from its title ('Allowability of Costs').
    """
    want = section.strip()
    if not want:
        return {"error": "section is required"}
    try:
        toc = await _toc()
    except ValueError as e:
        return {"error": str(e), "upstream": TOC}
    hits = _match(toc, want)
    if not hits:
        return {"error": f"no section {want!r} in the table of contents; see nihgps_toc", "link": LANDING}
    if len(hits) > 1:
        return {"error": f"{len(hits)} sections carry those words; name one", "sections": [{"number": e["number"], "title": e["title"]} for e in hits[:30]]}
    e = hits[0]
    children, seen = [], set()
    for x in toc:
        # A subsection can be listed twice, at an anchor of this page and as its own page; the first listing stands.
        if e["number"] and x["number"] and x["number"].startswith(e["number"] + ".") and x["number"].count(".") == e["number"].count(".") + 1 and x["number"] not in seen:
            seen.add(x["number"])
            children.append(x)
    try:
        page = await _page(e)
    except ValueError as err:
        return {"error": str(err), "link": e["url"]}
    out = {"number": e["number"], "title": e["title"], "heading": e["title"] if e.get("anchor") else page["heading"], "revised": page["revised"], "cite": f"NIH GPS {e['number']}" if e["number"] else e["title"],
           "paragraphs": page["paragraphs"], "tables": page["tables"], "subheadings": page["subheadings"],
           "subsections": [{"number": x["number"], "title": x["title"], "link": x["url"]} for x in children], "link": e["url"]}
    if e.get("anchor"):
        out["note"] = f"This section shares a page with {page['heading']}; the paragraphs and tables are the whole page's, and the section begins at its subheading."
    if not page["paragraphs"] and not page["tables"]:
        out["note"] = "This entry is a chapter heading with no text of its own; read its subsections."
    return out


@mcp.tool(name="nihgps_search", annotations=_READ_ONLY)
async def nihgps_search(query: str, chapter: str, rows: int = 20) -> dict:
    """The sections of one chapter of the NIH Grants Policy Statement that carry every word given, with a snippet.

    Each section is a page, so the search reads the chapter's pages (cached a day); name the chapter.

    Args:
        query: Words to find, e.g. 'prior approval equipment', 'salary cap'.
        chapter: The chapter number, '7' (cost considerations), '8' (administrative requirements), '4' (public policy).
        rows: Sections to return, 1-50. Default 20.
    """
    words = [w for w in query.lower().split() if w]
    ch = chapter.strip().rstrip(".")
    if not words or not ch:
        return {"error": "query and chapter are required"}
    rows = max(1, min(int(rows or 20), 50))
    try:
        toc = await _toc()
    except ValueError as e:
        return {"error": str(e), "upstream": TOC}
    entries = [e for e in toc if (e["number"] or "").split(".")[0] == ch]
    if not entries:
        return {"error": f"no chapter {ch!r}; chapters are 1 to 19 (see nihgps_toc)"}
    try:
        pages = await asyncio.gather(*(_page(e) for e in entries))
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    hits = []
    for e, page in zip(entries, pages):
        body = " ".join(page["paragraphs"] + [" ".join(c for c in row) for t in page["tables"] for row in t["rows"]])
        hay = (e["title"] + " " + body).lower()
        if all(w in hay for w in words):
            k = min((body.lower().find(w) for w in words if w in body.lower()), default=-1)
            snippet = body if len(body) <= 300 else (body[max(0, k - 120):k + 180].strip() + " …" if k >= 0 else body[:300] + " …")
            hits.append({"number": e["number"], "title": e["title"], "in_title": all(w in e["title"].lower() for w in words), "snippet": snippet, "link": e["url"]})
    hits.sort(key=lambda h: not h["in_title"])
    out = {"query": query.strip(), "chapter": ch, "sections_read": len(entries), "total": len(hits), "returned": min(rows, len(hits)), "sections": hits[:rows], "link": LANDING}
    if len(hits) > rows:
        out["note"] = f"{len(hits)} sections match; the first {rows} are here (title matches first)."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A section number the model names waits on the table of contents (#40); one a person gives passes as given.
given(mcp, {"nihgps_section": {"section": "nihgps_toc"}, "nihgps_search": {"chapter": "nihgps_toc"}})
