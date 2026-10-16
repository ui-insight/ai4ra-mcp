"""govinfo: GovInfo, the Government Publishing Office's collection of federal documents: public laws, bills, the U.S. Code, CFR, Federal Register, reports.

Upstream: https://api.govinfo.gov/ (JSON; a free api.data.gov key, sent as the X-Api-Key header). The search is a POST to
/search with a query in GovInfo's syntax (collection:(PLAW BILLS) words, congress:119, publishdate:range(2025-01-01,
2026-12-31), a quoted phrase), pageSize to 100 and an offsetMark cursor ('*' first, then the one the answer gives);
each result is a package (a law, a bill version, a report, a Code title) or a granule within one (a Code section, a
Federal Register document), with its collection, date, title and download links. /packages/<id>/summary describes a
package (title, short title, congress, pages, document type, whether it is an appropriation, the laws and Code
sections it references, download links); /packages/<id>/htm is its text. Collections that matter here: PLAW public
laws (the appropriations acts that fund the agencies), BILLS, BILLSTATUS, CRPT committee reports (the report language
behind an appropriation), USCODE, CFR, FR, CHRG hearings, GAOREPORTS, BUDGET, COMPS statute compilations.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, api_key, get_json, get_text, missing_key, post_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_GOVINFO_KEY"
KEY_HOW = "A free key comes from https://api.data.gov/signup/ (an email address is all it asks); the same key serves the fac, regulations, perdiem, congress and scorecard servers."
BASE = "https://api.govinfo.gov"
SITE = "https://www.govinfo.gov/"
DEFAULT_COLLECTIONS = "PLAW,BILLS,CRPT,USCODE,CFR,FR,CHRG,GAOREPORTS,BUDGET,COMPS"
ROWS, MAX_ROWS = 20, 100
TEXT_CHARS, MAX_TEXT_CHARS = 20000, 60000
_PACKAGE = re.compile(r"^[A-Z]+-[A-Za-z0-9.-]+$")
_TAG = re.compile(r"<[^>]+>")
_cache = TTLCache()

mcp = MCPServer(
    "govinfo",
    instructions="GovInfo: federal documents by words, collection and dates (govinfo_search), one document's record (govinfo_package) and its text (govinfo_text), the collections (govinfo_collections). Needs a free api.data.gov key. Read govinfo_index first.",
)


def _headers() -> dict:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    # The key goes as the header api.data.gov accepts, never in the URL or a cache key.
    return {"X-Api-Key": key}


async def _get(path: str, ttl: float = DAY) -> dict | list:
    headers = _headers()
    return await _cache.remember(f"get:{path}", ttl, lambda: get_json(f"{BASE}/{path}", None, headers))


async def _search(payload: dict) -> dict:
    headers = _headers()
    body = await _cache.remember("search:" + repr(sorted(payload.items())), HOUR, lambda: post_json(f"{BASE}/search", payload, headers))
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise ValueError("GovInfo did not return its results list")
    return body


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", fragment))).strip()


def slim_result(r: dict) -> dict:
    dl = r.get("download") or {}
    return {"package_id": r.get("packageId"), "granule_id": r.get("granuleId") if r.get("granuleId") not in (None, "None") else None, "title": r.get("title"),
            "collection": r.get("collectionCode"), "date_issued": r.get("dateIssued"), "last_modified": r.get("lastModified"),
            "authors": r.get("governmentAuthor") if isinstance(r.get("governmentAuthor"), list) else None,
            "formats": sorted(k[:-4] for k in dl if k.endswith("Link") and k != "premisLink"),
            "link": f"{SITE}app/details/{r.get('packageId')}" + (f"/{r['granuleId']}" if r.get("granuleId") not in (None, "None") else "")}


def slim_summary(s: dict) -> dict:
    dl = s.get("download") or {}
    short = s.get("shortTitle")
    refs = s.get("references") or []
    return {"package_id": s.get("packageId"), "title": s.get("title"), "short_titles": [t.get("title") for t in short] if isinstance(short, list) else None,
            "collection": s.get("collectionCode"), "collection_name": s.get("collectionName"), "category": s.get("category"), "document_type": s.get("documentType"),
            "document_number": s.get("documentNumber"), "congress": s.get("congress"), "date_issued": s.get("dateIssued"), "last_modified": s.get("lastModified"),
            "pages": s.get("pages"), "is_appropriation": s.get("isAppropriation"), "publisher": s.get("publisher"), "branch": s.get("branch"),
            "other_identifiers": s.get("otherIdentifier"),
            "references": [{"collection": x.get("collectionCode"), "contents": [{"title": c.get("title"), "label": c.get("label")} for c in (x.get("contents") or [])[:20]]} for x in refs[:5]] if isinstance(refs, list) else None,
            "formats": sorted(k[:-4] for k in dl if k.endswith("Link") and k != "premisLink"), "link": s.get("detailsLink") or f"{SITE}app/details/{s.get('packageId')}"}


@mcp.tool(name="govinfo_index", annotations=_READ_ONLY)
async def govinfo_index() -> dict:
    """How to use the GovInfo tools. READ THIS FIRST: the key, the collections, the query syntax, what a package and a granule are."""
    return {
        "upstream": f"GovInfo at {BASE}, the Government Publishing Office's federal documents; a free api.data.gov key",
        "key": {"required": True, "on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own api.data.gov key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "workflow": ["govinfo_search with words, the collections to search and dates: laws, bills, reports, Code sections, rules; each result a package or a granule with its id",
                     "govinfo_package for a document's record: titles, congress, pages, whether it is an appropriation, the laws and Code sections it cites, the formats",
                     "govinfo_text for the document's text, in pieces of up to 60,000 characters"],
        "notes": ["Collections: PLAW public and private laws (an appropriations act is 'Consolidated Appropriations Act, 2026', is_appropriation true), BILLS bill texts by version, BILLSTATUS, CRPT committee reports (the report language that directs an agency's spending), USCODE the Code by title and section, CFR, FR the Federal Register, CHRG hearings, GAOREPORTS, BUDGET, COMPS compilations of statutes as amended. govinfo_collections lists them all with counts.",
                  "Query syntax is GovInfo's: words match anywhere, a phrase in quotes, OR between alternatives, congress:119, title:(words) for the title; collections and dates are arguments here and become collection:(...) and publishdate:range(...). A Code search returns granules, one per section.",
                  "A package is a document (a law, one version of a bill, a Code title); a granule is a part of one (a Code section, a report's part). The record's references list the laws and Code sections a document cites, which is how a public law's effect on the Code is found.",
                  "The text of an appropriations act runs to hundreds of pages; search the text for the agency or program with govinfo_text's offset, or read the committee report (CRPT) for the directive language.",
                  "For the regulations themselves use the ecfr server (current text) and fedreg (the Federal Register with dates); GovInfo holds the same documents as published volumes.",
                  "Cite a document by its title, date and GovInfo link."],
        "limits": {"search": f"1-{MAX_ROWS} a page, the answer's offset_mark for the next", "text": f"{TEXT_CHARS} characters a call by default, {MAX_TEXT_CHARS} at most, with offset"},
        "link": SITE,
    }


@mcp.tool(name="govinfo_collections", annotations=_READ_ONLY)
async def govinfo_collections() -> dict:
    """GovInfo's collections with their codes, names and document counts: the codes govinfo_search takes."""
    try:
        body = await _get("collections")
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    cols = (body.get("collections") if isinstance(body, dict) else None) or []
    return {"total": len(cols), "collections": [{"code": c.get("collectionCode"), "name": c.get("collectionName"), "packages": c.get("packageCount"), "granules": c.get("granuleCount")} for c in cols], "link": SITE}


@mcp.tool(name="govinfo_search", annotations=_READ_ONLY)
async def govinfo_search(query: str, collections: str = DEFAULT_COLLECTIONS, congress: int = 0, from_date: str = "", to_date: str = "", rows: int = ROWS, offset_mark: str = "*") -> dict:
    """Federal documents in GovInfo by words, collection, Congress and dates: laws, bills, committee reports, Code sections, rules, hearings, reports.

    Args:
        query: Words in GovInfo's syntax: 'National Science Foundation appropriations', '"indirect cost"', 'title:(research security)'.
        collections: Comma-separated collection codes; default PLAW,BILLS,CRPT,USCODE,CFR,FR,CHRG,GAOREPORTS,BUDGET,COMPS. See govinfo_collections.
        congress: Limit to one Congress, e.g. 119; 0 for any.
        from_date: Earliest publish date, YYYY-MM-DD.
        to_date: Latest publish date, YYYY-MM-DD.
        rows: Results a page, 1-100. Default 20.
        offset_mark: The cursor the previous answer returned as offset_mark; '*' for the first page.
    """
    q = query.strip()
    if not q:
        return {"error": "query is required"}
    cols = [c.strip().upper() for c in collections.split(",") if c.strip()]
    if not cols or not all(re.fullmatch(r"[A-Z0-9]+", c) for c in cols):
        return {"error": "collections must be comma-separated collection codes like PLAW,BILLS"}
    for label, v in (("from_date", from_date), ("to_date", to_date)):
        if v.strip() and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
            return {"error": f"{label} must be YYYY-MM-DD"}
    parts = [f"collection:({' '.join(cols)})", q]
    if congress:
        parts.append(f"congress:{int(congress)}")
    if from_date.strip() or to_date.strip():
        parts.append(f"publishdate:range({from_date.strip() or '1789-01-01'},{to_date.strip() or '2100-12-31'})")
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    payload = {"query": " ".join(parts), "pageSize": rows, "offsetMark": offset_mark.strip() or "*", "sorts": [{"field": "publishdate", "sortOrder": "DESC"}]}
    try:
        body = await _search(payload)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    results = [slim_result(r) for r in body["results"]]
    out = {"query": payload["query"], "total": body.get("count"), "returned": len(results), "results": results, "link": SITE}
    if body.get("offsetMark") and results and isinstance(body.get("count"), int) and body["count"] > len(results):
        out["offset_mark"] = body["offsetMark"]
        out["note"] = f"{body['count']} documents match, newest first; pass offset_mark for the next {rows}."
    return out


@mcp.tool(name="govinfo_package", annotations=_READ_ONLY)
async def govinfo_package(package_id: str) -> dict:
    """One GovInfo document's record: titles, collection, Congress, date, pages, whether it is an appropriation, the laws and Code sections it references, the formats.

    Args:
        package_id: The package id from govinfo_search, e.g. 'PLAW-119publ75', 'BILLS-119s5526rs', 'USCODE-2024-title35'.
    """
    pid = package_id.strip()
    if not _PACKAGE.match(pid):
        return {"error": "package_id must be a GovInfo package id like PLAW-119publ75"}
    try:
        body = await _get(f"packages/{pid}/summary")
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no package {pid} in GovInfo"}
        return {"error": str(e), "upstream": BASE}
    return slim_summary(body if isinstance(body, dict) else {})


@mcp.tool(name="govinfo_text", annotations=_READ_ONLY)
async def govinfo_text(package_id: str, granule_id: str = "", offset: int = 0, max_chars: int = TEXT_CHARS) -> dict:
    """The text of a GovInfo document, or of one granule of it, in pieces: read a law, a bill, a Code section or a report.

    Args:
        package_id: The package id, e.g. 'PLAW-119publ75'.
        granule_id: A granule within it, e.g. 'USCODE-2024-title35-partII-chap18-sec212'; empty for the whole package.
        offset: Character position to start from; the answer says where the next piece begins. Default 0.
        max_chars: Characters to return, up to 60,000. Default 20,000.
    """
    pid, gid = package_id.strip(), granule_id.strip()
    if not _PACKAGE.match(pid) or (gid and not _PACKAGE.match(gid)):
        return {"error": "package_id (and granule_id) must be GovInfo ids like PLAW-119publ75"}
    offset = max(0, int(offset or 0))
    max_chars = max(1000, min(int(max_chars or TEXT_CHARS), MAX_TEXT_CHARS))
    path = f"packages/{pid}/granules/{gid}/htm" if gid else f"packages/{pid}/htm"
    try:
        headers = _headers()
        page = await _cache.remember(f"text:{path}", DAY, lambda: get_text(f"{BASE}/{path}", None, headers))
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no text at {path}; the package may offer only PDF or XML (see govinfo_package's formats)"}
        return {"error": str(e), "upstream": BASE}
    full = text(page)
    piece = full[offset:offset + max_chars]
    out = {"package_id": pid, "granule_id": gid or None, "total_chars": len(full), "offset": offset, "returned": len(piece), "text": piece,
           "link": f"{SITE}app/details/{pid}" + (f"/{gid}" if gid else "")}
    if offset + len(piece) < len(full):
        out["next_offset"] = offset + len(piece)
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A package or granule id the model names waits on a search that returned it (#40); one a person gives passes as given.
given(mcp, {"govinfo_package": {"package_id": "govinfo_search"}, "govinfo_text": {"package_id": "govinfo_search", "granule_id": "govinfo_search"}, "govinfo_search": {"collections": "govinfo_collections"}})
