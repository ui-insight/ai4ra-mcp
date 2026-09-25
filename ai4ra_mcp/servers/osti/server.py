"""osti: OSTI.GOV, the Department of Energy's record of the papers, reports and data its awards produced.

Upstream: https://www.osti.gov/api/v1/records. No key; Accept: application/json, since the default is XML.
A search's total is the X-Total-Count header. Dates are MM/DD/YYYY; 20 rows a page by default. OSTI
rate-limits aggressively (a 429, or a dropped connection, on a second quick call), so one request goes at a
time and an hour's cache holds.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HEADERS, HOUR, TIMEOUT_S, TTLCache
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://www.osti.gov/api/v1"
_DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
_cache = TTLCache()
_lock = asyncio.Lock()

mcp = MCPServer(
    "osti",
    instructions="OSTI.GOV: what a DOE award reported, by contract number, author, institution, sponsor, dates or words; one record with its abstract. Read osti_index first.",
)


async def _get(path: str, params: dict) -> tuple[dict | list, dict]:
    """GET one OSTI URL and return the body with the response headers, because a search's count is only in
    X-Total-Count. One call at a time: OSTI answers a second quick request with a 429 or by dropping the line."""
    async with _lock:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S, headers={**HEADERS, "Accept": "application/json"}, follow_redirects=True) as client:
                resp = await client.get(f"{BASE}{path}", params=params)
        except httpx.HTTPError as e:
            raise ValueError(f"www.osti.gov dropped the connection ({type(e).__name__}); OSTI rate-limits aggressively, wait a minute before retrying") from None
    if resp.status_code == 429:
        raise ValueError("rate limit exceeded at www.osti.gov; wait a minute before retrying")
    if resp.status_code == 404:
        raise ValueError(f"404 from {BASE}{path}: nothing at that address")
    if resp.status_code >= 400:
        raise ValueError(f"{resp.status_code} from www.osti.gov: {resp.text[:200]}")
    try:
        body = resp.json()
    except ValueError:
        raise ValueError("www.osti.gov did not return JSON") from None
    return body, {k.lower(): v for k, v in resp.headers.items()}


def _split(v: str | None) -> list[str]:
    return [s.strip() for s in (v or "").split(";") if s.strip()]


def _slim_record(r: dict) -> dict:
    oid = r.get("osti_id")
    authors = r.get("authors") or []
    links = {l.get("rel"): l.get("href") for l in r.get("links") or [] if l.get("rel")}
    out = {
        "osti_id": oid, "title": r.get("title"), "authors": authors[:10], "author_count": len(authors),
        "publication_date": (r.get("publication_date") or "")[:10] or None, "product_type": r.get("product_type"), "article_type": r.get("article_type"),
        "journal": {"name": r.get("journal_name"), "volume": r.get("journal_volume"), "issue": r.get("journal_issue"), "pages": r.get("format")} if r.get("journal_name") else None,
        "doi": r.get("doi"), "doe_contract_numbers": _split(r.get("doe_contract_number")), "other_contract_numbers": _split(r.get("nondoe_contract_number")),
        "doe_funded": r.get("doe_funded_flag"), "research_orgs": r.get("research_orgs") or [], "sponsor_orgs": r.get("sponsor_orgs") or [],
        "report_number": r.get("report_number"), "publisher": r.get("publisher"),
        "links": {"citation": links.get("citation"), "fulltext": links.get("fulltext")},
        "link": f"https://www.osti.gov/biblio/{oid}",
    }
    return out


@mcp.tool(name="osti_index", annotations=_READ_ONLY)
async def osti_index() -> dict:
    """How to use the OSTI.GOV tools. READ THIS FIRST: the contract number search, product types, date format, the pace."""
    return {
        "upstream": "https://www.osti.gov/api/v1/records, no key",
        "workflow": ["osti_search by doe_contract for what an award reported; by research_org, author, sponsor_org or query otherwise; note the osti_id",
                     "osti_record for one record with its abstract, subjects and availability"],
        "notes": ["DOE award terms require accepted manuscripts, technical reports and data to be submitted to OSTI under the award's contract number, so doe_contract is the search for 'what did this award report'. Give the number as OSTI holds it: 'SC0019327' for DE-SC0019327 (the DE- prefix is dropped), 'AC07-05ID14517' for a lab contract.",
                  "product_type values: Journal Article, Technical Report, Dataset, Conference, Book, Thesis/Dissertation, Patent, Software, Program Document; a record's article_type says Accepted Manuscript or Published Article.",
                  "Dates are MM/DD/YYYY in requests and YYYY-MM-DD in results. A record's doe_contract_numbers lists every contract it acknowledges.",
                  "OSTI rate-limits aggressively: this server sends one request at a time and caches an hour; on a 'wait' answer, wait a minute rather than retrying at once. Ask for what you need in one search rather than many small ones.",
                  "Cite the OSTI link (https://www.osti.gov/biblio/<osti_id>) and the DOI; links.fulltext is the public copy when OSTI holds one."],
        "limits": {"rows": "1-50 a page", "total": "from the X-Total-Count header, given as total"},
    }


@mcp.tool(name="osti_search", annotations=_READ_ONLY)
async def osti_search(
    query: str = "",
    author: str = "",
    doe_contract: str = "",
    research_org: str = "",
    sponsor_org: str = "",
    from_date: str = "",
    to_date: str = "",
    product_type: str = "",
    page: int = 1,
    rows: int = 20,
) -> dict:
    """Search OSTI.GOV records: the papers, reports, data and software DOE-funded work reported.

    Give at least one of query, author, doe_contract, research_org or sponsor_org. Returns each record with its
    OSTI id, title, authors, date, product type, journal, DOI, contract numbers, organizations and links.

    Args:
        query: Words in the title, abstract or subjects, e.g. 'soil carbon'.
        author: An author's name, e.g. 'Smith, J'.
        doe_contract: The DOE contract or award number as OSTI holds it, e.g. 'SC0019327' or 'AC07-05ID14517'.
        research_org: The performing institution, e.g. 'University of Idaho'.
        sponsor_org: The sponsoring DOE office, e.g. 'USDOE Office of Science'.
        from_date: Published on or after MM/DD/YYYY.
        to_date: Published on or before MM/DD/YYYY.
        product_type: One product type, e.g. 'Journal Article', 'Technical Report', 'Dataset'. Empty for all.
        page: Page number, 1-based. Default 1.
        rows: Records a page, 1-50. Default 20.
    """
    names = {"q": query, "author": author, "doe_contract_number": doe_contract, "research_org": research_org, "sponsor_org": sponsor_org,
             "publication_date_start": from_date, "publication_date_end": to_date, "product_type": product_type}
    params: dict = {k: v.strip() for k, v in names.items() if v and v.strip()}
    if not any(k in params for k in ("q", "author", "doe_contract_number", "research_org", "sponsor_org")):
        return {"error": "give at least one of query, author, doe_contract, research_org or sponsor_org"}
    for k in ("publication_date_start", "publication_date_end"):
        if k in params and not _DATE.fullmatch(params[k]):
            return {"error": "dates must be MM/DD/YYYY"}
    if "doe_contract_number" in params:
        params["doe_contract_number"] = re.sub(r"^DE-", "", params["doe_contract_number"], flags=re.I)
    params["page"] = max(1, int(page or 1))
    params["rows"] = max(1, min(int(rows or 20), 50))
    try:
        body, headers = await _cache.remember("search:" + repr(sorted(params.items())), HOUR, lambda: _get("/records", params))
    except ValueError as e:
        return {"error": str(e)}
    records = [_slim_record(r) for r in (body if isinstance(body, list) else [])]
    out = {"page": params["page"], "rows": params["rows"], "returned": len(records), "records": records}
    count = headers.get("x-total-count")
    if count and str(count).isdigit():
        out["total"] = int(count)
        if params["page"] * params["rows"] < out["total"]:
            out["next_page"] = params["page"] + 1
    return out


@mcp.tool(name="osti_record", annotations=_READ_ONLY)
async def osti_record(osti_id: str) -> dict:
    """One OSTI.GOV record by id, with its abstract, subjects and availability.

    Args:
        osti_id: The numeric OSTI id, e.g. '2282731'.
    """
    oid = (osti_id or "").strip()
    if not oid.isdigit():
        return {"error": "osti_id must be the numeric OSTI id"}
    try:
        body, _ = await _cache.remember(f"record:{oid}", DAY, lambda: _get(f"/records/{oid}", {}))
    except ValueError as e:
        return {"error": str(e)}
    rec = body[0] if isinstance(body, list) and body else body if isinstance(body, dict) else None
    if not rec or not rec.get("osti_id"):
        return {"error": f"no OSTI record {oid}", "osti_id": oid}
    return {**_slim_record(rec), "abstract": rec.get("description"), "subjects": rec.get("subjects") or [], "availability": rec.get("availability"),
            "language": rec.get("language"), "country_publication": rec.get("country_publication"), "entry_date": (rec.get("entry_date") or "")[:10] or None,
            "other_identifiers": rec.get("other_identifiers") or []}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
