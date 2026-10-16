"""The Idaho Statutes as the Legislature publishes them at legislature.idaho.gov, and the Legislature's own search of them.

The Legislative Services Office publishes the codified statutes as one HTML page per title, chapter and section under
https://legislature.idaho.gov/statutesrules/idstat/ (a WordPress site; the statute text inside each page is the
Arbortext export the office makes, in a `pgbrk` block with the section's text and its History line), with a PDF of
each chapter beside it. The text is the current law only, updated to the web each July 1 after the session; the
office's own statement of how current it is sits at /statutesrules/howcurrentisthislaw/. There is no API and no
bulk download (checked 2026-10-16); the pages are read as published.

Full-text search is the Legislature's ISYS engine at https://legislature.search.idaho.gov/search, a GET with
IW_FIELD_WEB_STYLE (web-style words, a quoted phrase, AND/OR) and IW_DATABASE=Idaho Statutes, IW_BATCHSIZE for the
results a page (tested to 50). Its results page lists each matching section with the hit count and a snippet with
the matches marked, and the section's page URL. The engine answers nothing (200, empty) to a User-Agent that does
not begin "Mozilla/5.0", or that nests parentheses, so the search is sent as
"Mozilla/5.0 (compatible; ai4ra-mcp/0.1; +contact)", the convention for an identified robot, which still names
the project and its contact. Later pages of a result set live under a query id the engine mints per
search, so this server asks for the rows it wants in one batch and pages no further.

A section is cited TT-CCSS: title, hyphen, chapter and a two-digit section (33-2901 is title 33, chapter 29,
section 01; 67-5309A has a letter suffix; 33-107C is chapter 1), which is how a citation alone finds its page.
"""

from __future__ import annotations

import html as _html
import re

from ai4ra_mcp.common.http import CONTACT, HEADERS, get_text

BASE = "https://legislature.idaho.gov/statutesrules/idstat/"
CURRENCY = "https://legislature.idaho.gov/statutesrules/howcurrentisthislaw/"
SEARCH = "https://legislature.search.idaho.gov/search"
# The engine answers an empty body to any agent string not beginning Mozilla/5.0, and to one with nested parentheses.
SEARCH_HEADERS = {"User-Agent": f"Mozilla/5.0 (compatible; ai4ra-mcp/0.1; +{CONTACT})"}
DATABASE = "Idaho Statutes"
_CITATION = re.compile(r"^(\d{1,2})-(\d{3,5})([A-Za-z]?)$")
_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_HEAD = re.compile(r'<h([12]) class="lso-toc">(.*?)</h\1>', re.S)
_BLOCK = re.compile(r'<div class="pgbrk".*?(?=<p></body>|</body>)', re.S)
_DIV = re.compile(r"<div[^>]*>(.*?)</div>", re.S)
_SECTION_LINE = re.compile(r"^(\d{1,2}-\d{3,5}[A-Za-z]?)\.\s*(.*?\.)\s*(.*)$", re.S)
_RESULT = re.compile(r'<tr>\s*<td class="resultColumnB".*?</tr>', re.S)
_RESULT_TITLE = re.compile(r"Section\s+(\d{1,2}-\d{3,5}[A-Za-z]?)")
_RESULT_HITS = re.compile(r'resultHits">\s*(\d+) hits?')
_RESULT_URL = re.compile(r'<a href="(https?://legislature\.idaho\.gov/statutesrules/idstat/[^"]+)"')
_RESULT_SNIPPET = re.compile(r'<div style="word-wrap: break-word; font-size:10pt;">(.*?)</div>', re.S)
_SHOWING = re.compile(r"Showing (\d+) to (\d+) of (\d+)\s*\(\s*(\d+) hits?\s*\)")
_NONE = re.compile(r"found 0 hits in 0 documents")
_CURRENT = re.compile(r"current through the (.+?) Legislative Session")
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


class StatuteError(Exception):
    """The site answered a page with something other than what the page carries."""

    def __init__(self, what: str, detail: str):
        super().__init__(f"{what}: {detail}")
        self.what, self.detail = what, detail


def text(fragment: str | None) -> str:
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", fragment or ""))).strip()


def parse_citation(citation: str) -> tuple[int, int, str]:
    """(title, chapter, section as written) from 'TT-CCSS[A]'; ValueError when it is not one."""
    m = _CITATION.match(citation.strip().upper().replace("–", "-").replace("—", "-"))
    if not m:
        raise ValueError(f"{citation!r} is not an Idaho Code citation like 33-2901 or 67-5309A")
    title, number, suffix = int(m.group(1)), m.group(2), m.group(3)
    if len(number) < 3:
        raise ValueError(f"{citation!r} is not an Idaho Code citation like 33-2901 or 67-5309A")
    return title, int(number[:-2]), f"{title}-{number}{suffix}"


def title_url(title: int) -> str:
    return f"{BASE}Title{title}/"


def chapter_url(title: int, chapter: int) -> str:
    return f"{BASE}Title{title}/T{title}CH{chapter}/"


def section_url(citation: str) -> str:
    title, chapter, sect = parse_citation(citation)
    return f"{BASE}Title{title}/T{title}CH{chapter}/SECT{sect}/"


async def _page(url: str, what: str) -> str:
    try:
        return await get_text(url, headers=HEADERS)
    except ValueError as e:
        raise StatuteError(what, str(e)) from e


def _rows(page: str, href_part: str) -> list[tuple[str, str, str]]:
    """(href, link text, the row's name cell as text) for each table row whose first link carries href_part. The name
    is the first cell after the link's that says something and is not the chapter's PDF link."""
    out = []
    for row in _ROW.findall(page):
        m = _LINK.search(row)
        if not m or href_part not in m.group(1):
            continue
        cells = [text(c) for c in _CELL.findall(row)]
        names = [c for c in cells[1:] if c and not c.startswith("Download Entire Chapter")]
        out.append((m.group(1), text(m.group(2)), names[0] if names else ""))
    return out


def parse_titles(page: str) -> list[dict]:
    titles = []
    for href, label, name in _rows(page, "/idstat/Title"):
        m = re.search(r"Title(\d+)", href, re.I)
        if m:
            titles.append({"title": int(m.group(1)), "name": name, "link": _absolute(href)})
    return titles


def parse_chapters(page: str) -> dict:
    heads = [text(h) for _, h in _HEAD.findall(page)]
    chapters = []
    for href, label, name in _rows(page, "CH"):
        m = re.search(r"T(\d+)CH(\d+)(?:/|$)", href, re.I)
        if m and not href.lower().endswith(".pdf"):
            chapters.append({"chapter": int(m.group(2)), "name": name, "link": _absolute(href),
                             "pdf": _absolute(re.sub(r"/statutesrules/idstat/", "/wp-content/uploads/statutesrules/idstat/", href.rstrip("/")) + ".pdf")})
    return {"heading": heads[0] if heads else None, "chapters": chapters}


def parse_sections(page: str) -> dict:
    heads = [text(h) for _, h in _HEAD.findall(page)]
    sections = []
    for href, label, heading in _rows(page, "SECT"):
        m = re.search(r"SECT(\d{1,2}-\d{3,5}[A-Za-z]?)", href, re.I)
        if m:
            sections.append({"section": m.group(1).upper(), "heading": heading.rstrip(".").strip() or None, "link": _absolute(href)})
    pdf = re.search(r'href="([^"]+\.pdf)"[^>]*>\s*Download Entire Chapter', page)
    return {"title_heading": heads[0] if heads else None, "chapter_heading": heads[1] if len(heads) > 1 else None, "sections": sections, "pdf": _absolute(pdf.group(1)) if pdf else None}


def parse_section(page: str) -> dict:
    """The statute text of a section page: the title and chapter lines, the section's number, heading and text as
    paragraphs, and its History line. Raises when the page has no statute block (a removed or mistyped section)."""
    m = _BLOCK.search(page)
    if not m:
        raise StatuteError("section", "the page carries no statute text (no such section, or the site changed)")
    paras = [text(d) for d in _DIV.findall(m.group(0))]
    paras = [p for p in paras if p]
    out: dict = {"title_heading": None, "chapter_heading": None, "section": None, "heading": None, "text": [], "history": None}
    i = 0
    if len(paras) >= 4 and paras[0].upper().startswith("TITLE"):
        out["title_heading"] = f"{paras[0]} {paras[1]}".replace("  ", " ")
        out["chapter_heading"] = f"{paras[2]} {paras[3]}".replace("  ", " ")
        i = 4
    body = paras[i:]
    if body:
        sm = _SECTION_LINE.match(body[0])
        if sm:
            out["section"], out["heading"] = sm.group(1).upper(), sm.group(2).rstrip(".").strip()
            first = sm.group(3).strip()
            body = ([first] if first else []) + body[1:]
    if "History:" in body:
        k = body.index("History:")
        out["history"] = " ".join(body[k + 1:]) or None
        body = body[:k]
    out["text"] = body
    return out


def parse_search(page: str) -> dict:
    """The engine's results page: how many sections matched, the hit count, and each result's section, hit count,
    snippet (matches kept as **word**) and link."""
    flat = text(page)
    if _NONE.search(flat):
        return {"from": 0, "to": 0, "sections": 0, "hits": 0, "results": []}
    sm = _SHOWING.search(flat)
    results = []
    for block in _RESULT.findall(page):
        head = text(block[: block.find("resultSummary")] if "resultSummary" in block else block).replace("pecnv.out", "").split(" – ")[0].strip()
        url = _RESULT_URL.search(block)
        link = url.group(1) if url else None
        hits = _RESULT_HITS.search(block)
        snip = _RESULT_SNIPPET.search(block)
        snippet = text(re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", snip.group(1))) if snip else None
        t = _RESULT_TITLE.search(head)
        # The engine indexes the section pages and the title and chapter outlines alike; the link says which this is.
        if t:
            kind = "section"
        elif link and re.search(r"/T\d+CH\d+/?$", link, re.I):
            kind = "chapter"
        elif link and re.search(r"/Title\d+/?$", link, re.I):
            kind = "title"
        else:
            kind = "page"
        results.append({"kind": kind, "section": t.group(1).upper() if t else None, "page": head or None, "hits": int(hits.group(1)) if hits else None,
                        "snippet": snippet, "link": link})
    if not sm and not results:
        raise StatuteError("search", "the engine's page carried neither results nor its no-results line (the engine may have changed, or refused the request)")
    return {"from": int(sm.group(1)) if sm else 1, "to": int(sm.group(2)) if sm else len(results), "sections": int(sm.group(3)) if sm else len(results),
            "hits": int(sm.group(4)) if sm else None, "results": results}


def parse_currency(page: str) -> str | None:
    m = _CURRENT.search(text(page))
    return f"current through the {m.group(1)} Legislative Session" if m else None


def _absolute(href: str) -> str:
    return href if href.startswith("http") else "https://legislature.idaho.gov" + href


async def titles() -> list[dict]:
    found = parse_titles(await _page(BASE, "titles"))
    if not found:
        raise StatuteError("titles", "no titles on the page (the site changed)")
    return found


async def chapters(title: int) -> dict:
    found = parse_chapters(await _page(title_url(title), f"title {title}"))
    if not found["chapters"]:
        raise StatuteError(f"title {title}", "no chapters on the page: no such title, or the site changed")
    return found


async def sections(title: int, chapter: int) -> dict:
    found = parse_sections(await _page(chapter_url(title, chapter), f"chapter {title}-{chapter}"))
    if not found["sections"]:
        raise StatuteError(f"chapter {chapter} of title {title}", "no sections on the page: no such chapter, or the site changed")
    return found


async def section(citation: str) -> dict:
    url = section_url(citation)
    return {**parse_section(await _page(url, f"section {citation}")), "link": url}


async def search(query: str, rows: int) -> dict:
    try:
        page = await get_text(SEARCH, {"IW_FIELD_WEB_STYLE": query, "IW_DATABASE": DATABASE, "IW_BATCHSIZE": rows}, headers=SEARCH_HEADERS)
    except ValueError as e:
        raise StatuteError("search", str(e)) from e
    return parse_search(page)


async def currency() -> str | None:
    return parse_currency(await _page(CURRENCY, "how current is this law"))
