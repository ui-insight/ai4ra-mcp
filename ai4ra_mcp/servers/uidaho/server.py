"""uidaho: University of Idaho guidance for sponsored projects.

The policy site is plain HTML with a stable address scheme: the APM at
/policies/apm/<chapter>/<policy> and the FSH at /policies/fsh/<chapter>/<policy>.
Each landing page lists chapters, each chapter page lists its policies under a
"Chapter Index" heading, and each policy page carries its owner and a
"Last updated" date above the text. The tools here crawl that scheme and cache
what they read for a day, since revisions are rare and the page dates itself.
"""

from __future__ import annotations

import asyncio
import html
import re
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common import fetch as _fetch
from ai4ra_mcp.common import text as _text
from ai4ra_mcp.common.http import DAY, USER_AGENT, TTLCache
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}

BASE = "https://www.uidaho.edu/policies"
SOURCES = {
    "APM": {"label": "Administrative Procedures Manual", "landing": f"{BASE}/apm",
            "about": "Finance and administration policy, chapters 01-95. Chapter 45 is the Research Office: proposals, allowable costs, cost sharing, effort, F&A, subawards, closeout."},
    "FSH": {"label": "Faculty Staff Handbook", "landing": f"{BASE}/fsh",
            "about": "Governance, employment, academic and research policy, chapters 1-6. Chapter 5 is Research Policies: general research policy, human subjects, intellectual property, financial disclosure, research data."},
}
RATES = {
    "fa": {"label": "Facilities and administrative (indirect) rate agreement",
           "url": "https://content-hub.uidaho.edu/api/public/content/015597383dac40219f3c7f32223b7445?v=6bc964f2",
           "linked_from": "https://www.uidaho.edu/research/faculty/resources/f-and-a-rates",
           "note": "A PDF, read at the address the F&A page links today (this one is the last known). Section I has the rates by type and location and the base definition. Read in pages."},
    "fringe": {"label": "Consolidated fringe benefit rates by fiscal year",
               "url": "https://www.uidaho.edu/leadership/finance-administration/budget-planning",
               "note": "The section 'Consolidated fringe rates by fiscal year' lists faculty, staff, temporary help and student rates."},
}
_ANCHOR = re.compile(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.I | re.S)


def pick_agreement_link(page_html: str) -> str | None:
    """The address of the rate agreement PDF as the F&A page links it: the content-hub link whose text says
    'rate agreement'. None when the page has no such link."""
    for href, inner in _ANCHOR.findall(page_html):
        label = re.sub(r"<[^>]+>", " ", inner)
        if "content-hub.uidaho.edu" in href and re.search(r"rate\s+agreement", label, re.I):
            return html.unescape(href)
    return None


async def _fa_agreement_url() -> tuple[str, str]:
    """(url, how): the current rate agreement's address read from the F&A page today, so a new agreement is
    picked up the day the page links it; the last known address when the page cannot be read."""
    async def make():
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            r = await client.get(RATES["fa"]["linked_from"])
            r.raise_for_status()
        return pick_agreement_link(r.text)
    try:
        found = await _cache.remember("fa-agreement-url", DAY, make)
    except Exception:
        found = None
    if found:
        return found, "the F&A page's rate-agreement link, read today"
    return RATES["fa"]["url"], "the last known address; the F&A page could not be read or has no rate-agreement link"


# The fringe section of the budget office page: from its heading to the next heading.
_FRINGE_SECTION = re.compile(r"^## Consolidated fringe rates by fiscal year[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
COVERS_CHARS = 500   # the most of a policy's opening paragraph a chapter's index carries
INDEX_FETCHES = 6    # policy pages read at once when a chapter's index is built
USAGE_NOTES = [
    "To find the policy that governs something, start with uidaho_guidance_index and a chapter ('APM 45' is sponsored projects, 'FSH 5' is research policy): it lists each policy of the chapter with what it covers, in the policy's own opening words. Choose by what a policy covers, then read it with uidaho_guidance_get. No call without a chapter is needed first.",
    "uidaho_guidance_index with no chapter lists every chapter with its URL and where the rate documents are: for a matter whose chapter is not known.",
    "uidaho_guidance_get returns a short policy whole and a long one as an outline of its sections (A., E-1.) with their offsets: read the section you need by its offset, not the whole policy.",
    "uidaho_guidance_search matches policy numbers and titles, not full text: use it when you have a title word or a number.",
    "uidaho_guidance_get takes a policy number ('APM 45.06', 'FSH 5100'); every result carries the page URL and its 'Last updated' date. Cite both.",
    "uidaho_rates reads the F&A rate agreement PDF or the fringe-rate page; quote figures with their effective period.",
    "Questions about allowability or interpretation go to the Office of Sponsored Programs, 208-885-6651, osp@uidaho.edu. Give no other contact.",
]

_cache = TTLCache()
_CHAPTER_LINE = re.compile(r"^Chapter (\d+): (.+)$", re.M)
_APM_POLICY_LINE = re.compile(r"^(\d{2})\.(\d{2}) - (.+)$", re.M)
_FSH_POLICY_LINE = re.compile(r"^(\d{4}) - (.+)$", re.M)
_POLICY_REF = re.compile(r"^\s*(APM|FSH)?\s*(\d{2}\.\d{2}|\d{4})\s*$", re.I)
# Where a page's own text ends and the site's navigation begins: a heading that is only "APM", "FSH" or "Footer".
# A heading inside a policy that merely opens with one of those words ("### APM 70.04 is under revision.") is text.
_NAV_HEADING = re.compile(r"^#{2,4} (APM|FSH|Footer)[ \t]*$", re.M)
# A policy's own sections: a lettered one (A. Purpose.) and a numbered one under it (E-1. Salaries), at the start of a line.
_SECTION = re.compile(r"^(?:#+[ \t]*)?([A-Z])(-\d+)?\.[ \t]+(\S.*)$", re.M)
_CHAPTER_REF = re.compile(r"^\s*(APM|FSH)\s*(\d{1,2})\s*$", re.I)

mcp = MCPServer(
    "uidaho",
    instructions="University of Idaho policy for sponsored projects: the APM and FSH, found by what each policy covers (start with uidaho_guidance_index and a chapter: 'APM 45' is sponsored projects) or by number and title, read whole or one section at a time, and the F&A and fringe rates.",
)


async def _whole_text(url: str) -> tuple[str, str]:
    """A page's full text, following the reader's paging. Returns (title, text)."""
    parts, offset, title = [], 0, ""
    while True:
        page = await _fetch.fetch_document(url, offset=offset, max_chars=40_000)
        if "error" in page:
            raise ValueError(f"{page['error']} ({url})")
        title = title or page.get("title", "")
        parts.append(page.get("text", ""))
        if not page.get("truncated"):
            break
        offset = page["next_offset"]
    return title, "".join(parts)


def parse_chapters(source: str, text: str) -> list[dict]:
    seen, out = set(), []
    for number, title in _CHAPTER_LINE.findall(text):
        if number in seen:
            continue
        seen.add(number)
        out.append({"chapter": number, "title": title.strip(), "url": f"{SOURCES[source]['landing']}/{number}"})
    return out


def parse_policies(source: str, chapter: str, text: str) -> list[dict]:
    """The policies listed under a chapter page's 'Chapter Index'."""
    start = text.find("## Chapter Index")
    body = text[start:] if start >= 0 else text
    end = _NAV_HEADING.search(body[3:])
    body = body[: end.start() + 3] if end else body
    seen, out = set(), []
    if source == "APM":
        for ch, num, title in _APM_POLICY_LINE.findall(body):
            policy = f"{ch}.{num}"
            if policy in seen:
                continue
            seen.add(policy)
            out.append({"policy": f"APM {policy}", "title": title.strip(), "chapter": ch, "url": f"{SOURCES['APM']['landing']}/{ch}/{num}"})
    else:
        for num, title in _FSH_POLICY_LINE.findall(body):
            if num in seen:
                continue
            seen.add(num)
            out.append({"policy": f"FSH {num}", "title": title.strip(), "chapter": chapter, "url": f"{SOURCES['FSH']['landing']}/{chapter}/{num}"})
    return out


def parse_policy_page(text: str) -> dict:
    """Title, owner, last-updated date and body from a policy page's text."""
    title_m = re.search(r"^# (.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else ""
    owner = {}
    m = re.search(r"^Position: (.+)$", text, re.M)
    if m:
        owner["position"] = m.group(1).strip()
    m = re.search(r"^Email: (.+)$", text, re.M)
    if m:
        owner["email"] = m.group(1).strip()
    m = re.search(r"^Last updated: (.+)$", text, re.M)
    last_updated = m.group(1).strip() if m else ""
    body_start = m.end() if m else (title_m.end() if title_m else 0)
    body = text[body_start:]
    end = _NAV_HEADING.search(body)
    if end:
        body = body[: end.start()]
    return {"title": title, "owner": owner, "last_updated": last_updated, "text": body.strip()}


def opening_paragraph(body: str) -> str:
    """What a policy covers, in its own words: the first paragraph of its text that is prose, whatever the page
    calls it (a Purpose, a Preamble, an Introduction), cut at a sentence end when it is long. A contents list
    and bare headings are passed over: they do not end as a sentence does. A page with no such paragraph (a
    pointer to another page, a link to a chart) gives the first line it has that is not a heading."""
    blocks = [" ".join(block.split()) for block in body.split("\n\n")]
    blocks = [b for b in blocks if b and not b.startswith("#")]
    for text in blocks:
        if len(text) < 60 or text.rstrip("”\"')")[-1:] not in (".", "?", "!"):
            continue
        if len(text) > COVERS_CHARS:
            cut = text.rfind(". ", 0, COVERS_CHARS)
            text = text[: cut + 1] if cut > 0 else text[:COVERS_CHARS].rstrip() + "…"
        return text
    return next((b[:COVERS_CHARS] for b in blocks if not b.endswith(":")), "")


def policy_outline(text: str) -> list[tuple[int, str, int]]:
    """A policy's own sections as (offset, heading, end): the lettered ones (A. Purpose) and the numbered ones under
    them (E-1. Salaries), each with where its part ends. Read from the text itself, so it follows the policy when
    the policy changes. Sections come in order, so a label that does not follow the last one is a list item
    inside a section and is passed over; and when the labels start again at A after a run of bare titles, that
    run was a contents list and the sections begin at the second A."""
    found: list[tuple[int, int, str]] = []
    last, bare = ("", 0), True
    for m in _SECTION.finditer(text):
        key = (m.group(1), int(m.group(2)[1:]) if m.group(2) else 0)
        rest = m.group(3).strip()
        if key <= last:
            if key != ("A", 0) or not bare:
                continue
            found, bare = [], True   # a contents list came first
        title = re.split(r"(?<=\w{3})\.(?: |$)|: | – ", rest, maxsplit=1)[0][:80].rstrip(". ")
        found.append((m.start(), 2 if m.group(2) else 1, f"{m.group(1)}{m.group(2) or ''}. {title}"))
        last, bare = key, bare and not re.search(r"\.( |$)|:", rest)
    return _text.with_ends(found, len(text))


def parse_policy_ref(policy: str) -> tuple[str, str, str] | None:
    """'APM 45.06' -> ('APM', '45', '06'); 'FSH 5100' or '5100' -> ('FSH', '5', '5100')."""
    m = _POLICY_REF.match(policy or "")
    if not m:
        return None
    source, number = (m.group(1) or "").upper(), m.group(2)
    if "." in number:
        ch, num = number.split(".")
        return ("APM", ch, num) if source in ("", "APM") else None
    return ("FSH", number[0], number) if source in ("", "FSH") else None


async def _chapters(source: str) -> list[dict]:
    async def make():
        _, text = await _whole_text(SOURCES[source]["landing"])
        return parse_chapters(source, text)
    return await _cache.remember(f"chapters:{source}", DAY, make)


async def _policies(source: str, chapter: dict) -> list[dict]:
    async def make():
        _, text = await _whole_text(chapter["url"])
        return parse_policies(source, chapter["chapter"], text)
    return await _cache.remember(f"policies:{chapter['url']}", DAY, make)


async def _policy_page(url: str) -> dict:
    """A policy page read and parsed, kept for a day."""
    async def make():
        _, text = await _whole_text(url)
        return parse_policy_page(text)
    return await _cache.remember(f"policy:{url}", DAY, make)


async def _chapter_index(source: str, chapter: dict) -> dict:
    """Every policy of one chapter with what it covers, read from the policy pages themselves, so nothing is kept by
    hand and an entry changes when its policy does. A page that cannot be read is listed as unread, not left out."""
    gate = asyncio.Semaphore(INDEX_FETCHES)

    async def one(p: dict) -> dict:
        async with gate:
            try:
                page = await _policy_page(p["url"])
            except Exception as e:
                return {"policy": p["policy"], "title": p["title"], "url": p["url"], "unread": str(e)}
        if not page["title"]:
            return {"policy": p["policy"], "title": p["title"], "url": p["url"], "unread": "the page has no policy text"}
        return {"policy": p["policy"], "title": p["title"], "covers": opening_paragraph(page["text"]),
                "last_updated": page["last_updated"], "url": p["url"]}

    rows = await asyncio.gather(*(one(p) for p in await _policies(source, chapter)))
    return {"chapter": f"{source} {chapter['chapter']}", "title": chapter["title"], "url": chapter["url"],
            "policies": [r for r in rows if "unread" not in r], "unread": [r for r in rows if "unread" in r],
            "note": "covers is each policy's own opening paragraph. Choose the policy by what it covers, then read it with uidaho_guidance_get. A policy under unread could not be read just now and may still be the one that governs."}


async def _all_policies(source_filter: str = "") -> list[dict]:
    out = []
    for source in SOURCES:
        if source_filter and source != source_filter:
            continue
        for chapter in await _chapters(source):
            for p in await _policies(source, chapter):
                out.append({**p, "source": source, "chapter_title": chapter["title"]})
    return out


@mcp.tool(name="uidaho_guidance_index", annotations=_READ_ONLY)
async def uidaho_guidance_index(chapter: str = "") -> dict:
    """University of Idaho policy for sponsored projects: find the policy that governs something. START HERE, with a chapter.

    With a chapter: every policy of that chapter with what it covers (the policy's own opening paragraph),
    its 'Last updated' date and its URL. Choose by what a policy covers, then read it with
    uidaho_guidance_get. 'APM 45' is sponsored projects: proposals, allowable costs, cost sharing, effort,
    F&A, subawards. No call without a chapter is needed first.
    With no chapter: the APM and FSH with every chapter and its URL, where the F&A and fringe rates are,
    and the rules for using the other uidaho tools. For a matter whose chapter you do not know.

    Args:
        chapter: 'APM 45' (sponsored projects), 'FSH 5' (research policy), or any chapter the index lists. Empty for the list of chapters.
    """
    if (chapter or "").strip():
        m = _CHAPTER_REF.match(chapter)
        if not m:
            return {"error": "chapter must look like 'APM 45' or 'FSH 5'"}
        source, number = m.group(1).upper(), int(m.group(2))
        chapters = await _chapters(source)
        found = next((c for c in chapters if int(c["chapter"]) == number), None)
        if not found:
            return {"error": f"{source} has no chapter {number}", "chapters": [f"{source} {c['chapter']}: {c['title']}" for c in chapters]}
        return await _chapter_index(source, found)
    sources = {}
    for source, meta in SOURCES.items():
        sources[source] = {**meta, "chapters": await _chapters(source)}
    return {"sources": sources, "rates": RATES, "usage_notes": USAGE_NOTES}


@mcp.tool(name="uidaho_guidance_search", annotations=_READ_ONLY)
async def uidaho_guidance_search(query: str, source: str = "", limit: int = 20) -> dict:
    """Find University of Idaho policies by number or title words.

    Matches the policy number and title as listed in each chapter's index, not the full text. Use it
    to find the policy that covers a topic, then read it with uidaho_guidance_get.

    Args:
        query: Words from a title ('cost sharing', 'subaward', 'effort') or a policy number ('45.08').
        source: 'APM' or 'FSH' to limit; empty for both.
        limit: Hits to return, 1-50. Default 20.
    Returns: hits with policy, title, chapter, url, ordered by match.
    """
    words = [w for w in re.findall(r"[a-z0-9.]+", (query or "").lower()) if w]
    if not words:
        return {"error": "query is required"}
    source = (source or "").strip().upper()
    if source and source not in SOURCES:
        return {"error": "source must be APM, FSH or empty"}
    limit = max(1, min(int(limit or 20), 50))
    hits = []
    for p in await _all_policies(source):
        hay = f"{p['policy']} {p['title']} {p['chapter_title']}".lower()
        score = sum(2 if w in p["policy"].lower() else 1 for w in words if w in hay)
        if score:
            hits.append((score, p))
    hits.sort(key=lambda t: (-t[0], t[1]["policy"]))
    return {"query": query, "hit_count": len(hits), "hits": [p for _, p in hits[:limit]],
            "note": "Title and number matches only; read a policy with uidaho_guidance_get to check its text."}


@mcp.tool(name="uidaho_guidance_get", annotations=_READ_ONLY)
async def uidaho_guidance_get(policy: str, offset: int = 0) -> dict:
    """Read one University of Idaho policy as clean text by its number: all of it, or one section of it.

    Returns the title, owner, 'Last updated' date, URL and text. Cite the policy number, the URL and
    the date. A policy up to 12,000 characters comes back whole; there is no size to set. A longer one comes back as an outline:
    its own sections, each as "offset: heading" (A. Purpose, E-1. Salaries), with only the lines before
    the first of them. Choose the section you need and call again with offset = that heading's offset:
    the section is read to its end, with the numbered sections under a lettered one. Ask for several
    sections in one round of calls. A long policy with no such sections comes back a page at a time:
    when truncated, call again with offset = next_offset.

    Args:
        policy: 'APM 45.06', '45.06', 'FSH 5100' or '5100'.
        offset: Character position to start from: a heading's offset from the outline, or next_offset. Default 0.
    """
    ref = parse_policy_ref(policy)
    if not ref:
        return {"error": "policy must look like 'APM 45.06' or 'FSH 5100'"}
    source, chapter, number = ref
    url = f"{SOURCES[source]['landing']}/{chapter}/{number}"
    try:
        page = await _policy_page(url)
    except ValueError as e:
        return {"error": str(e), "url": url}
    if not page["title"]:
        return {"error": "the page has no policy text; it may not exist or may be script-rendered", "url": url}
    offset = max(0, int(offset or 0))
    text = page["text"]
    label = f"{source} {chapter}.{number}" if source == "APM" else f"FSH {number}"
    return {"policy": label, "title": page["title"], "owner": page["owner"], "last_updated": page["last_updated"], "url": url,
            **_text.read(text, policy_outline(text), offset)}


@mcp.tool(name="uidaho_rates", annotations=_READ_ONLY)
async def uidaho_rates(kind: str, offset: int = 0, max_chars: int = 12000) -> dict:
    """Read the University of Idaho's rate documents: the F&A rate agreement or the fringe-rate page.

    Quote each figure with its effective period and the document it came from.

    Args:
        kind: 'fa' for the facilities and administrative (indirect) rate agreement PDF; 'fringe' for the consolidated fringe rates by fiscal year.
        offset: Character position to start from. Default 0.
        max_chars: Characters to return, 1000-40000. Default 12000.
    """
    kind = (kind or "").strip().lower()
    if kind not in RATES:
        return {"error": "kind must be 'fa' or 'fringe'", "kinds": {k: v["label"] for k, v in RATES.items()}}
    if kind == "fringe":
        # The budget office page is mostly navigation and budget-book links; only its fringe section is returned,
        # so a model reads the rates and nothing else. Offsets apply to the section.
        page = await _fetch.fetch_document(RATES[kind]["url"], offset=0, max_chars=40000)
        m = _FRINGE_SECTION.search(page.get("text") or "")
        if m:
            text = "## Consolidated fringe rates by fiscal year\n\n" + m.group(1).strip()
            offset = max(0, offset)
            chunk = text[offset:offset + max(1000, min(int(max_chars or 12000), 40000))]
            page.update({"total_chars": len(text), "offset": offset, "returned_chars": len(chunk),
                         "truncated": offset + len(chunk) < len(text), "text": chunk, "trimmed_to": "the consolidated fringe rates section of the page"})
            page.pop("next_offset", None)
            if page["truncated"]:
                page["next_offset"] = offset + len(chunk)
        return {"kind": kind, **RATES[kind], **page}
    url, how = await _fa_agreement_url()
    page = await _fetch.fetch_document(url, offset=offset, max_chars=max_chars)
    return {"kind": kind, **RATES[kind], **page, "url": page.get("url", url), "resolved_via": how}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
