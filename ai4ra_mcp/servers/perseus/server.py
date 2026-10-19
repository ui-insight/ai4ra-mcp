"""perseus: the Perseus Digital Library's Greek and Latin texts through the Scaife Viewer, no key.

Upstream: https://scaife.perseus.org, the Perseus Digital Library's reading environment, every page of which has a JSON twin:
/library/json/ the text groups (authors and corpora), /library/{urn}/json/ an author's works, a work's versions or a
version's record (label, language, kind, description, first passage, table of contents), /library/passage/{urn}/text/ a
passage as plain text and /library/passage/{urn}/json/ the same with its version and ancestors, and /search/json/?q=…&type=library
a search of the library. Texts are CTS URNs: urn:cts:greekLit:tlg0059.tlg030.perseus-grc2:1.327a is author (Plato), work
(Republic), version (the Greek edition) and passage (Book 1, Stephanus 327a). A URN comes from the listing and search tools
and is never composed from memory. A reference the Viewer does not have is answered with another passage, which the server
says. The library and texts are cached a day (they do not change), a search an hour, and four requests at a time at most,
since Perseus's own updates blame its outages on scraping. Texts are CC BY-SA; cite the URN and the reader link.

Perseus 6 (checked 2026-10-19): the project's next site, "Perseus MVP" at https://beta.perseus.tufts.edu (announced
2026-09-29), is static HTML compiled from the TEI corpora with no API, no search yet and no database; the Scaife Viewer and
Perseus 4 are slated for retirement without a date, with a URL converter promised first. The Scaife Viewer is the one Perseus
with a JSON interface, so it is the upstream here until that changes.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json, get_text
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://scaife.perseus.org"
ABOUT = f"{BASE}/about/"
MAX_TEXT, MAX_WORKS, PARALLEL = 20000, 80, 4
_URN = re.compile(r"^urn:cts:[A-Za-z0-9]+:[A-Za-z0-9_.-]+(?::[^\s:]+)?$")
_cache = TTLCache()
_gate = asyncio.Semaphore(PARALLEL)

mcp = MCPServer(
    "perseus",
    instructions="The Perseus Digital Library's Greek and Latin texts through the Scaife Viewer: the library's authors and corpora, an author's works, a work's versions (the original and its translations) with their tables of contents (perseus_library), a passage by CTS URN as plain text, in another version too (perseus_passage), and a search of the library for a word (perseus_search). No key. URNs come from the listing and search tools. Read perseus_index first.",
)


def urn_level(urn: str) -> str | None:
    """'group', 'work', 'version' or 'passage' for a CTS URN; None when it is not one."""
    if not _URN.match(urn or ""):
        return None
    parts = urn.split(":")
    if len(parts) == 5:
        return "passage"
    return {1: "group", 2: "work", 3: "version"}.get(len(parts[3].split(".")))


def reader(urn: str) -> str:
    return f"{BASE}/reader/{urn}/"


def _text_meta(t: dict) -> dict:
    return {"urn": t.get("urn"), "label": t.get("label"), "language": t.get("lang"), "language_name": t.get("human_lang"), "kind": t.get("kind")}


def _toc(v: dict) -> list[dict]:
    return [{"urn": e.get("urn"), "label": " ".join(x for x in (e.get("label"), e.get("num")) if x)} for e in v.get("toc") or []]


def version_record(v: dict) -> dict:
    return {**_text_meta(v), "description": v.get("description"), "right_to_left": v.get("rtl"),
            "first_passage": (v.get("first_passage") or {}).get("urn"), "contents": _toc(v), "reader": f"{BASE}{v.get('reader_url')}" if v.get("reader_url") else reader(v.get("urn", ""))}


def search_hit(r: dict) -> dict:
    p = r.get("passage") or {}
    t = p.get("text") or {}
    ancestors = [a.get("label") for a in t.get("ancestors") or [] if a.get("label")]
    return {"urn": p.get("urn"), "author": ancestors[0] if ancestors else None, "work": ancestors[1] if len(ancestors) > 1 else None,
            "version": _text_meta(t), "snippets": [re.sub(r"\s+", " ", s).strip() for s in (r.get("content") or []) if isinstance(s, str)], "reader": f"{BASE}{p.get('url')}" if p.get("url") else None}


async def _json(path: str, ttl: float = DAY) -> dict:
    return await _cache.remember("json:" + path, ttl, lambda: get_json(f"{BASE}{path}"))


async def _record(urn: str) -> dict:
    async with _gate:
        return await _json(f"/library/{urn}/json/")


async def _records(urns: list[str]) -> list[dict | None]:
    async def one(u: str):
        try:
            return await _record(u)
        except ValueError:
            return None
    return list(await asyncio.gather(*(one(u) for u in urns)))


@mcp.tool(name="perseus_index", annotations=_READ_ONLY)
async def perseus_index() -> dict:
    """How to use the Perseus tools. READ THIS FIRST: what a CTS URN is, where URNs come from, the versions, how to cite."""
    return {
        "upstream": f"The Perseus Digital Library through the Scaife Viewer ({BASE}; about: {ABOUT}). No key. Texts CC BY-SA.",
        "urns": ["A CTS URN names author, work, version and passage: urn:cts:greekLit:tlg0059.tlg030.perseus-grc2:1.327a is Plato (tlg0059), Republic (tlg030), the Greek edition (perseus-grc2), Book 1 Stephanus page 327a. Latin is latinLit (phi0474 is Cicero).",
                 "Versions are named by language and a number: perseus-grc2 and perseus-eng2 are the Greek and the English of the same work; a version record says which translator or editor (description).",
                 "URNs come from perseus_library (the groups, an author's works, a work's versions and their tables of contents) and perseus_search; none is composed from memory. A reference the Viewer lacks is answered with another passage, and perseus_passage says when the URN it got back is not the one asked for."],
        "workflow": ["perseus_library() with a query to find the author or corpus; then the author's URN for the works; then the work's URN for its versions and each one's table of contents, which gives the passage URNs and their ranges",
                     "perseus_passage(urn) for the text; with_version=another version's URN for the same reference in translation or in the original",
                     "perseus_search(query) for a word or phrase across the library, in the language the text is in (an English word finds translations, a Greek form the editions)",
                     "cite the passage by author, work and reference with the URN and the reader link; name the version (translator or editor) when quoting a translation"],
        "notes": ["The passage text is the Viewer's plain text for the reference as the version divides it (a Stephanus page or a section), with footnote text where the edition prints it; a long passage is cut at 20,000 characters and says so.",
                  "An author's works are listed with their labels by reading each work's record (the listing itself carries URNs alone), so a large author takes a moment the first time; cached a day.",
                  "The search is the Viewer's own: a form search matches the word as spelled, a lemma search (kind='lemma') the dictionary form in Greek and Latin texts.",
                  "Perseus 6 (beta.perseus.tufts.edu, 2026-09-29) is a static site without an API or search; the Scaife Viewer is the Perseus this server reads, and the project says it will retire the Viewer some day without a date."],
    }


@mcp.tool(name="perseus_library", annotations=_READ_ONLY)
async def perseus_library(urn: str = "", query: str = "") -> dict:
    """The library's catalog at any level: the authors and corpora (no urn), an author's works, a work's versions, or one version with its table of contents.

    Args:
        urn: Empty for the groups; an author's URN (urn:cts:greekLit:tlg0059) for its works; a work's (…tlg0059.tlg030) for its versions with their contents; a version's (…tlg0059.tlg030.perseus-grc2) for that one.
        query: Words to keep among the groups by label, e.g. 'Plato' or 'Cicero'. Used with an empty urn.
    """
    u = (urn or "").strip()
    if not u:
        try:
            root = await _json("/library/json/")
        except ValueError as e:
            return {"error": str(e)}
        words = [w for w in (query or "").lower().split() if w]
        groups = [{"urn": g.get("urn"), "label": g.get("label"), "works": len(g.get("works") or [])} for g in root.get("text_groups") or []
                  if not words or all(w in (g.get("label") or "").lower() for w in words)]
        out = {"level": "groups", "query": query or None, "returned": len(groups), "groups": groups}
        if not groups:
            out["note"] = "No group's label has those words; try the author's Latin or English name as the library spells it, or fewer words."
        return out
    level = urn_level(u)
    if level is None or level == "passage":
        return {"error": "urn must be an author's, a work's or a version's CTS URN, e.g. urn:cts:greekLit:tlg0059.tlg030; a passage is perseus_passage's"}
    try:
        rec = await _record(u)
    except ValueError as e:
        return {"error": f"{e}; URNs come from perseus_library's listings as given"}
    if level == "group":
        urns = [w.get("urn") for w in rec.get("works") or [] if w.get("urn")]
        recs = await _records(urns[:MAX_WORKS])
        works = [{"urn": wu, "label": (r or {}).get("label"), "versions": [t.get("urn") for t in (r or {}).get("texts") or []]} for wu, r in zip(urns, recs)]
        works += [{"urn": wu, "label": None, "versions": None} for wu in urns[MAX_WORKS:]]
        return {"level": "author", "urn": u, "label": rec.get("label"), "returned": len(works), "works": works, "reader": f"{BASE}{rec.get('url')}" if rec.get("url") else None}
    if level == "work":
        urns = [t.get("urn") for t in rec.get("texts") or [] if t.get("urn")]
        recs = await _records(urns)
        # A work's record carries no ancestors; its versions' records do, so the author's label is read from the first version found.
        author = next((a.get("label") for r in recs if r for a in (r.get("ancestors") or [])[:1] if a.get("label")), None)
        return {"level": "work", "urn": u, "label": rec.get("label"), "author": author,
                "versions": [version_record(r) if r else {"urn": vu} for vu, r in zip(urns, recs)]}
    return {"level": "version", **version_record(rec), "work": next((a.get("label") for a in reversed(rec.get("ancestors") or []) if a.get("label")), None),
            "author": next((a.get("label") for a in rec.get("ancestors") or [] if a.get("label")), None)}


async def _passage(u: str) -> dict:
    meta = await _json(f"/library/passage/{u}/json/")
    text = await _cache.remember("text:" + u, DAY, lambda: get_text(f"{BASE}/library/passage/{u}/text/"))
    t = meta.get("text") or {}
    ancestors = [a.get("label") for a in t.get("ancestors") or [] if a.get("label")]
    got = meta.get("urn")
    out = {"urn": got, "urn_requested": u, "reference": ((meta.get("refs") or {}).get("start") or {}).get("human_reference"),
           "author": ancestors[0] if ancestors else None, "work": ancestors[1] if len(ancestors) > 1 else None, "version": _text_meta(t),
           "text": text.strip()[:MAX_TEXT], "truncated": len(text.strip()) > MAX_TEXT, "words": len(meta.get("word_tokens") or []) or None, "reader": reader(got or u)}
    if got and got != u and got.split(":")[-1] != u.split(":")[-1].rstrip("abcdefgh"):
        out["note"] = f"The Viewer answered for {got}, not the reference asked for; the version's contents (perseus_library) give the references it has."
    return out


@mcp.tool(name="perseus_passage", annotations=_READ_ONLY)
async def perseus_passage(urn: str, with_version: str = "") -> dict:
    """A passage as plain text, by its CTS URN, with the version it is from and the author and work; optionally the same reference in another version.

    Args:
        urn: A passage URN, e.g. urn:cts:greekLit:tlg0059.tlg030.perseus-grc2:1.327a, from a version's contents (perseus_library) or perseus_search.
        with_version: Another version of the same work, e.g. urn:cts:greekLit:tlg0059.tlg030.perseus-eng2, to return the same reference in it. Empty for none.
    """
    u = (urn or "").strip()
    if urn_level(u) != "passage":
        return {"error": "urn must be a passage URN with a reference after the last colon, e.g. urn:cts:greekLit:tlg0059.tlg030.perseus-grc2:1.327a, from perseus_library's contents or perseus_search"}
    try:
        out = await _passage(u)
    except ValueError as e:
        return {"error": f"{e}; passage URNs come from perseus_library's contents or perseus_search as given"}
    v = (with_version or "").strip()
    if v:
        if urn_level(v) != "version":
            return {**out, "with_version": {"error": "with_version must be a version URN, e.g. urn:cts:greekLit:tlg0059.tlg030.perseus-eng2"}}
        try:
            out["with_version"] = await _passage(f"{v}:{u.split(':')[-1]}")
        except ValueError as e:
            out["with_version"] = {"error": str(e)}
    return out


@mcp.tool(name="perseus_search", annotations=_READ_ONLY)
async def perseus_search(query: str, kind: str = "form", page: int = 1, rows: int = 10) -> dict:
    """Search the library's texts for a word or phrase.

    Returns each hit with the passage URN, author, work, version (language and kind) and the snippets with the match marked, and the reader link.

    Args:
        query: The word or phrase, in the text's language: 'unexamined' finds English translations, 'ἀρετή' the Greek editions.
        kind: 'form' (default) matches the word as spelled; 'lemma' the dictionary form in Greek and Latin texts.
        page: Results page, from 1. Default 1.
        rows: Hits to return from the page, 1-50. Default 10.
    """
    q = " ".join((query or "").split())
    if not q:
        return {"error": "query is required"}
    if kind not in ("form", "lemma"):
        return {"error": "kind must be 'form' or 'lemma'"}
    pg = max(1, int(page or 1))
    from urllib.parse import urlencode
    path = "/search/json/?" + urlencode({"q": q, "type": "library", "kind": kind, "page": pg})
    try:
        body = await _json(path, HOUR)
    except ValueError as e:
        return {"error": str(e)}
    hits = [search_hit(r) for r in body.get("results") or []][:max(1, min(int(rows or 10), 50))]
    out = {"query": q, "kind": kind, "page": body.get("page_num") or pg, "returned": len(hits), "total": body.get("total_count"), "hits": hits,
           "link": f"{BASE}/search/?" + urlencode({"q": q, "type": "library", "kind": kind})}
    if not hits:
        out["note"] = "No passage has that form; try the word's other forms or a lemma search, and the language the text is in."
    return out


given(mcp, {"perseus_passage": {"urn": "perseus_library", "with_version": "perseus_library"}})
SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
