"""pappg: the NSF Proposal & Award Policies & Procedures Guide, as NSF publishes it at nsf.gov/policies/pappg.

Upstream: https://www.nsf.gov/policies/pappg/<version>/ (HTML, no key). NSF publishes the current PAPPG as one page per
chapter (ch-1-pre-submission ... ch-12-disputes-misconduct), a table of contents whose links carry the anchor of every
section (ch2D2b is chapter II, section D.2.b), a summary of changes and a subject index; the landing page says the
version and the date it took effect. Each chapter page is Drupal: the text sits in `text__content` blocks under
headings h2 (a lettered section, with a slug id), h3 (a numbered subsection, id chNXn) and h4 (a lettered paragraph, id
chNXna). The version is pinned here (NSF 24-1, effective 2024-05-20, read live 2026-10-16) and the landing page is
read to say whether NSF has moved on; a new version is a one-line change. Pages are cached a day.
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
VERSION = "24-1"
SITE = "https://www.nsf.gov/policies/pappg"
BASE = f"{SITE}/{VERSION}/"
TOC = BASE + "table-of-contents"
PDF = "https://nsf-gov-resources.nsf.gov/files/nsf24_1.pdf"
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
_LINK = re.compile(rf'href="/policies/pappg/{VERSION}/(ch-(\d+)-[a-z0-9-]+)(?:#([A-Za-z0-9._-]+))?"[^>]*>(.*?)</a>', re.S)
_BLOCK = re.compile(r'<div class="text__content text-formatted">(.*?)</div>\s*</section>', re.S)
_HEAD = re.compile(r'<h([2-4])(?:[^>]*?id="([^"]*)")?[^>]*>(.*?)</h\1>', re.S)
_PARA = re.compile(r"</(?:p|li|tr|h[1-6]|div|blockquote)>|<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_CURRENT = re.compile(r"Current version of the PAPPG NSF (\d\d-\d)\b.*?applies to all proposals submitted or due on or after ([A-Z][a-z]+\.? \d{1,2}, \d{4})")
_SUPPLEMENT = re.compile(r"(Supplement \d+) \(NSF (\d\d-\d{3})\) Applies to all financial assistance awarded on or after ([A-Z][a-z]+\.? \d{1,2}, \d{4})")
_cache = TTLCache()

mcp = MCPServer(
    "pappg",
    instructions=f"The NSF Proposal & Award Policies & Procedures Guide (PAPPG, NSF {VERSION}) from nsf.gov: the chapters (pappg_chapters), a chapter's outline (pappg_outline), one section's text (pappg_section), words across the guide (pappg_search). No key. Read pappg_index first.",
)


def text(fragment: str) -> str:
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", fragment))).strip()


def paragraphs(fragment: str) -> list[str]:
    """A block's HTML as its paragraphs, list items and table rows, in order."""
    return [t for t in (text(p) for p in _PARA.split(fragment)) if t]


def label_of(anchor: str, chapter: int) -> str:
    """'D.2.b' from 'ch2D2b'; a dotted form (ch10.A1) is read the same way."""
    rest = anchor[len(f"ch{chapter}"):].lstrip(".")
    parts = re.findall(r"[A-Z]|\d+|[a-z]", rest)
    return ".".join(parts)


def parse_toc(page: str) -> list[dict]:
    """The chapters in order, each with its slug, number, title and sections (anchor, label, title)."""
    chapters: dict[int, dict] = {}
    for slug, num, anchor, label in _LINK.findall(page):
        n = int(num)
        ch = chapters.setdefault(n, {"chapter": n, "roman": next((r for r, v in ROMAN.items() if v == n), str(n)), "slug": slug, "title": None, "link": BASE + slug, "sections": [], "_letters": 0})
        t = text(label)
        if not anchor:
            if ch["title"] is None and t:
                ch["title"] = t.split(":", 1)[1].strip() if ":" in t else t
            continue
        if not anchor.startswith(f"ch{n}"):
            # A lettered section's link carries the page's slug id; its letter is its place among the chapter's lettered sections.
            ch["_letters"] += 1
            canonical, page_anchor = f"ch{n}{chr(64 + ch['_letters'])}", anchor
        else:
            canonical, page_anchor = anchor, anchor
        if canonical not in {s["anchor"] for s in ch["sections"]}:
            ch["sections"].append({"anchor": canonical, "page_anchor": page_anchor, "label": label_of(canonical, n), "title": t})
    out = []
    for k in sorted(chapters):
        ch = chapters[k]
        ch.pop("_letters")
        out.append(ch)
    return out


def parse_chapter(page: str, chapter: int) -> list[dict]:
    """The chapter's text as blocks under its headings: level (2, 3, 4), anchor, label, heading and paragraphs. A lettered
    section's h2 carries a slug id, so its anchor is made from the letter the heading begins with ('A. Basic ...' is chNA)."""
    body = "\n".join(_BLOCK.findall(page))
    blocks: list[dict] = []
    heads = list(_HEAD.finditer(body))
    for i, m in enumerate(heads):
        level, hid, heading = int(m.group(1)), m.group(2) or "", text(m.group(3))
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        if level == 2:
            letter = re.match(r"([A-Z])\.", heading)
            anchor = f"ch{chapter}{letter.group(1)}" if letter else hid
        else:
            anchor = hid
        blocks.append({"level": level, "anchor": anchor, "page_anchor": hid or anchor, "label": label_of(anchor, chapter) if anchor.startswith(f"ch{chapter}") else None,
                       "heading": heading, "paragraphs": paragraphs(body[m.end():end])})
    return blocks


def parse_effective(page: str) -> dict | None:
    """The landing page's current version and effective date, and the supplements (policy notices) that change it."""
    flat = text(page)
    m = _CURRENT.search(flat)
    if not m:
        return None
    return {"version": m.group(1), "effective": m.group(2),
            "supplements": [{"supplement": a, "number": f"NSF {b}", "applies_to_awards_on_or_after": c, "link": f"{SITE}/{b}"} for a, b, c in _SUPPLEMENT.findall(flat)]}


async def _toc() -> list[dict]:
    chapters = await _cache.remember("toc", DAY, lambda: _parsed(TOC, lambda p: parse_toc(p)))
    if not chapters:
        raise ValueError("the table of contents page lists no chapters (NSF changed the page or the version)")
    return chapters


async def _parsed(url: str, parse):
    return parse(await get_text(url))


async def _chapter(ch: dict) -> list[dict]:
    return await _cache.remember(f"chapter:{ch['chapter']}", DAY, lambda: _parsed(ch["link"], lambda p: parse_chapter(p, ch["chapter"])))


async def _find_chapter(chapter: str) -> dict:
    want = chapter.strip()
    chapters = await _toc()
    for ch in chapters:
        if want.upper() == ch["roman"] or want == str(ch["chapter"]) or want.lower() == ch["slug"] or want.lower().lstrip("chapter ").strip().upper() == ch["roman"]:
            return ch
    raise ValueError(f"no chapter {chapter!r}; chapters are I to XII (1-12): " + ", ".join(f"{c['roman']} {c['title']}" for c in chapters))


def _link(ch: dict, item: dict) -> str:
    """The section's URL: the chapter page and the id the page gives the heading (a lettered section's slug, a subsection's chNXn)."""
    anchor = item.get("page_anchor") or item.get("anchor")
    return ch["link"] + (f"#{anchor}" if anchor else "")


@mcp.tool(name="pappg_index", annotations=_READ_ONLY)
async def pappg_index() -> dict:
    """How to use the PAPPG tools. READ THIS FIRST: which version this is, how sections are cited, what a solicitation can override."""
    try:
        current = await _cache.remember("effective", DAY, lambda: _parsed(SITE, parse_effective))
    except ValueError:
        current = None
    out = {
        "upstream": f"The NSF Proposal & Award Policies & Procedures Guide at {BASE}, one page per chapter, read as NSF publishes it; the PDF of the whole guide is {PDF}; no key",
        "version": {"served": f"NSF {VERSION}", "nsf_says_current": current or "the landing page's version line could not be read; see " + SITE},
        "workflow": ["pappg_chapters for the twelve chapters and how many sections each has",
                     "pappg_outline for a chapter's sections with their labels (D.2.b) and anchors",
                     "pappg_section with a chapter and a section label, anchor or heading words for the text",
                     "pappg_search with words for the sections across the guide that say them"],
        "notes": ["Cite as 'PAPPG Chapter II.D.2.b' (chapter in roman numerals, then the section label) with the section's link; say the version (NSF 24-1).",
                  "A program solicitation may deviate from the PAPPG and governs where it does; the PAPPG is the default. Chapter I says which documents take precedence.",
                  "Chapter II is proposal preparation (formats, sections of the proposal, budgets in II.D.2.f); Chapter VII award administration; Chapter X allowability of costs; Chapter XI other post-award requirements (reporting, research security); Chapter XII disputes and misconduct.",
                  "A lettered section (A, B, C) is a page section; its numbered subsections and lettered paragraphs are what a citation names. A section's text here is its own paragraphs; its subsections are listed and read separately."],
        "caveats": ["NSF's pages, not an API: a change to the site can alter a layout without notice; the version is pinned here and the landing page is read to say whether NSF has moved on.",
                    "Tables and footnotes come through as text rows; an exhibit's layout is lost. Read the PDF when the layout matters."],
        "link": BASE,
    }
    if current and current.get("supplements"):
        out["supplements"] = current["supplements"]
        out["notes"].append("NSF has issued supplements to this version, policy notices that change the PAPPG for awards made on or after their dates (listed under supplements); a supplement governs where it differs from the chapter text here.")
    if current and current.get("version") and current["version"] != VERSION:
        out["note"] = f"NSF's landing page names NSF {current['version']} as current, effective {current['effective']}; this server still reads NSF {VERSION}. Check the newer version at {SITE}."
    return out


@mcp.tool(name="pappg_chapters", annotations=_READ_ONLY)
async def pappg_chapters() -> dict:
    """The PAPPG's chapters: number, title, link and how many sections the table of contents lists under each."""
    try:
        chapters = await _toc()
    except ValueError as e:
        return {"error": str(e), "upstream": TOC}
    return {"version": f"NSF {VERSION}", "total": len(chapters),
            "chapters": [{"chapter": c["roman"], "number": c["chapter"], "title": c["title"], "sections": len(c["sections"]), "link": c["link"]} for c in chapters],
            "also": {"summary_of_changes": BASE + "summary-changes", "subject_index": BASE + "subject-index", "pdf": PDF}, "link": BASE}


@mcp.tool(name="pappg_outline", annotations=_READ_ONLY)
async def pappg_outline(chapter: str) -> dict:
    """One chapter's sections as the table of contents lists them: label (D.2.b), anchor and title, in order.

    Args:
        chapter: The chapter, 'II', '2' or its slug 'ch-2-proposal-preparation'.
    """
    try:
        ch = await _find_chapter(chapter)
    except ValueError as e:
        return {"error": str(e)}
    return {"chapter": ch["roman"], "title": ch["title"], "total": len(ch["sections"]),
            "sections": [{**s, "link": _link(ch, s)} for s in ch["sections"]], "link": ch["link"]}


@mcp.tool(name="pappg_section", annotations=_READ_ONLY)
async def pappg_section(chapter: str, section: str) -> dict:
    """One section of the PAPPG: its heading, text as paragraphs, and the subsections under it.

    Args:
        chapter: The chapter, 'II', '2' or its slug.
        section: The section's label ('D.2.b', 'D'), its anchor ('ch2D2b') or words from its heading ('Project Summary').
    """
    want = section.strip()
    if not want:
        return {"error": "section is required"}
    try:
        ch = await _find_chapter(chapter)
        blocks = await _chapter(ch)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    if not blocks:
        return {"error": f"chapter {ch['roman']} came back without its text blocks (NSF changed the page)", "link": ch["link"]}
    label = want.replace(" ", "").upper() if re.fullmatch(r"[A-Za-z](\.\d+)?(\.[A-Za-z])?", want) else None
    hit = None
    for b in blocks:
        if b["anchor"] and b["anchor"].lower() == want.lower():
            hit = b
            break
        if label and b["label"] and b["label"].upper() == label:
            hit = b
            break
    if hit is None:
        words = want.lower().split()
        matches = [b for b in blocks if all(w in b["heading"].lower() for w in words)]
        if len(matches) == 1:
            hit = matches[0]
        elif matches:
            return {"error": f"{len(matches)} sections of chapter {ch['roman']} have those words in the heading; name one",
                    "sections": [{"label": b["label"], "anchor": b["anchor"], "heading": b["heading"]} for b in matches]}
        else:
            return {"error": f"no section {want!r} in chapter {ch['roman']}; see pappg_outline", "link": ch["link"]}
    i = blocks.index(hit)
    subsections = []
    for b in blocks[i + 1:]:
        if b["level"] <= hit["level"]:
            break
        subsections.append({"label": b["label"], "anchor": b["anchor"], "heading": b["heading"], "link": _link(ch, b)})
    return {"version": f"NSF {VERSION}", "chapter": ch["roman"], "chapter_title": ch["title"], "label": hit["label"], "anchor": hit["anchor"], "heading": hit["heading"],
            "cite": f"PAPPG Chapter {ch['roman']}" + (f".{hit['label']}" if hit["label"] else ""), "paragraphs": hit["paragraphs"], "subsections": subsections, "link": _link(ch, hit)}


@mcp.tool(name="pappg_search", annotations=_READ_ONLY)
async def pappg_search(query: str, chapter: str = "", rows: int = 20) -> dict:
    """The sections of the PAPPG whose heading or text carries every word given, with a snippet, across the guide or in one chapter.

    Args:
        query: Words to find, e.g. 'biographical sketch', 'participant support', 'indirect cost'.
        chapter: Limit to one chapter ('II'); empty for all twelve.
        rows: Sections to return, 1-50. Default 20.
    """
    words = [w for w in query.lower().split() if w]
    if not words:
        return {"error": "query is required"}
    rows = max(1, min(int(rows or 20), 50))
    try:
        chapters = [await _find_chapter(chapter)] if chapter.strip() else await _toc()
        texts = await asyncio.gather(*(_chapter(ch) for ch in chapters))
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    hits = []
    for ch, blocks in zip(chapters, texts):
        for b in blocks:
            body = " ".join(b["paragraphs"])
            hay = (b["heading"] + " " + body).lower()
            if all(w in hay for w in words):
                k = min((body.lower().find(w) for w in words if w in body.lower()), default=-1)
                snippet = body if len(body) <= 300 else (body[max(0, k - 120):k + 180].strip() + " …" if k >= 0 else body[:300] + " …")
                hits.append({"chapter": ch["roman"], "label": b["label"], "anchor": b["anchor"], "heading": b["heading"], "in_heading": all(w in b["heading"].lower() for w in words),
                             "snippet": snippet, "link": _link(ch, b)})
    hits.sort(key=lambda h: (not h["in_heading"], ROMAN.get(h["chapter"], 99)))
    out = {"query": query.strip(), "version": f"NSF {VERSION}", "total": len(hits), "returned": min(rows, len(hits)), "sections": hits[:rows], "link": BASE}
    if len(hits) > rows:
        out["note"] = f"{len(hits)} sections match; the first {rows} are here (heading matches first). Add words or a chapter."
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A chapter the model names waits on the chapter list and a section on the outline (#40); words a person gives pass as given.
given(mcp, {"pappg_outline": {"chapter": "pappg_chapters"}, "pappg_section": {"chapter": "pappg_chapters", "section": "pappg_outline"}})
