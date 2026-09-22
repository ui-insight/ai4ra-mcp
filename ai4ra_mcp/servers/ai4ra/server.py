"""ai4ra: the catch-all server for what belongs to no single upstream.

Two tools: the page reader, and a web search answered by a SearXNG instance beside this process
(AI4RA_MCP_SEARXNG_URL, default http://127.0.0.1:8080). Anything else AI4RA provides that is not
tied to ecfr.gov, grants.gov or one institution goes here too.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common import fetch as _fetch
from ai4ra_mcp.common.http import HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
SEARXNG_URL = os.environ.get("AI4RA_MCP_SEARXNG_URL", "http://127.0.0.1:8080").rstrip("/")
CATEGORIES = ("general", "news", "science", "it", "files", "images", "videos", "map")
_cache = TTLCache()

mcp = MCPServer(
    "ai4ra",
    instructions="AI4RA's general tools. web_search finds pages on the open web (titles, addresses, snippets); fetch_document reads a page or PDF as text, in pages. Search first, then read.",
)


@mcp.tool(name="web_search", annotations=_READ_ONLY)
async def web_search(query: str, count: int = 8, category: str = "general", language: str = "en") -> dict:
    """Search the open web and return the top results: title, address, snippet, and which engines found each.

    Use it when you need an address you do not have: a facility, a dataset, a partner organisation, a
    sponsor's guide, a person's page. Then read the best result with fetch_document. Never guess an
    address when you can search for it. The search runs on this server's own SearXNG, which merges
    Google, Bing, DuckDuckGo, Brave and others; an engine that is rate-limiting drops out silently.

    Args:
        query: The search words, e.g. 'University of Idaho Deep Soil Ecotron'.
        count: Results to return, 1-20. Default 8.
        category: general (default), news, science, it, files, images, videos or map.
        language: Two-letter language code. Default 'en'.
    Returns: query, result_count, results (title, url, snippet, engines, published when known), and the engines that answered or failed.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "query is required"}
    cat = (category or "general").strip().lower()
    if cat not in CATEGORIES:
        return {"error": f"category must be one of {', '.join(CATEGORIES)}"}
    count = max(1, min(int(count or 8), 20))
    lang = (language or "en").strip().lower()[:5] or "en"
    params = {"q": q, "format": "json", "categories": cat, "language": lang, "safesearch": "0"}
    key = f"search:{cat}:{lang}:{q.lower()}"
    try:
        body = await _cache.remember(key, HOUR, lambda: get_json(f"{SEARXNG_URL}/search", params, headers={"Accept": "application/json"}))
    except ValueError as e:
        return {"error": f"web search is not answering: {e}. The search backend (SearXNG at {SEARXNG_URL}) may not be running; a page you already have an address for can still be read with fetch_document."}
    except Exception as e:  # noqa: BLE001 — connection refused, DNS, timeouts
        return {"error": f"web search backend unreachable at {SEARXNG_URL}: {type(e).__name__}. A page you already have an address for can still be read with fetch_document."}
    results = []
    for r in (body.get("results") or [])[:count]:
        results.append({"title": r.get("title"), "url": r.get("url"), "snippet": r.get("content"),
                        "engines": r.get("engines") or ([r["engine"]] if r.get("engine") else []),
                        "published": r.get("publishedDate")})
    failed = [u.get("engine") if isinstance(u, dict) else u for u in body.get("unresponsive_engines") or []]
    out = {"query": q, "category": cat, "result_count": body.get("number_of_results") or len(results), "returned": len(results), "results": results}
    if failed:
        out["engines_not_answering"] = failed
    if body.get("suggestions"):
        out["suggestions"] = body["suggestions"][:5]
    return out


@mcp.tool(name="fetch_document", annotations=_READ_ONLY)
async def fetch_document(url: str, offset: int = 0, max_chars: int = 12000) -> dict:
    """Read any public web page or PDF by its URL and return its text.

    Use it to look up a website the user names, a funding announcement, a policy page or a sponsor
    guide, when the user gives a link instead of pasting text. NSF and other script-rendered pages
    have no text: ask for the PDF link. Long documents come back in pages: when the result says
    truncated, call again with offset = next_offset. When replying, include the url as a markdown
    link so the person can open the original. Fetch only addresses the user gave, that a tool
    returned (web_search gives addresses), or that you know exactly; never guess a path, and on a
    404 do not try others: search instead.

    Args:
        url: The http(s) address of the page or PDF.
        offset: Character position to start from. Default 0.
        max_chars: Characters to return, 1000-40000. Default 12000.
    Returns: url, kind (html, pdf, text, grants.gov), title, total_chars, offset, returned_chars,
    truncated, next_offset and text; or an error.
    """
    return await _fetch.fetch_document(url, offset=offset, max_chars=max_chars)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
