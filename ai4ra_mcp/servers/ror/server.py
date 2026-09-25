"""ror: the Research Organization Registry, persistent identifiers for research organizations worldwide.

Upstream: https://api.ror.org/v2/organizations. No key. 20 results a page, pages from 1; an affiliation search
matches a free-text affiliation string and returns its candidates scored, with chosen on a confident match.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.ror.org/v2/organizations"
PAGE = 20
TYPES = ("education", "healthcare", "company", "archive", "nonprofit", "government", "facility", "funder", "other")
_ID = re.compile(r"0[a-hj-km-np-tv-z0-9]{6}[0-9]{2}")
_cache = TTLCache()

mcp = MCPServer(
    "ror",
    instructions="Research Organization Registry: the ROR id, names, location, type, relationships and Crossref Funder, GRID, ISNI and Wikidata ids of a research organization, by name or affiliation string. Read ror_index first.",
)


def _bare_id(s: str) -> str | None:
    m = _ID.fullmatch((s or "").strip().lower().removeprefix("https://ror.org/").removeprefix("http://ror.org/").removeprefix("ror.org/"))
    return m.group(0) if m else None


def _names(o: dict, kind: str) -> list[str]:
    return [n.get("value") for n in o.get("names") or [] if kind in (n.get("types") or [])]


def slim_organization(o: dict) -> dict:
    display = next(iter(_names(o, "ror_display")), None)
    loc = ((o.get("locations") or [{}])[0].get("geonames_details")) or {}
    links = {l.get("type"): l.get("value") for l in o.get("links") or []}
    return {
        "id": o.get("id"), "name": display,
        "aliases": _names(o, "alias"), "acronyms": _names(o, "acronym"), "labels": [n for n in _names(o, "label") if n != display],
        "types": o.get("types") or [], "status": o.get("status"),
        "country": loc.get("country_code"), "country_name": loc.get("country_name"), "region": loc.get("country_subdivision_name"), "city": loc.get("name"),
        "established": o.get("established"), "domains": o.get("domains") or [],
        "external_ids": {e.get("type"): {"preferred": e.get("preferred") or (e.get("all") or [None])[0], "all": e.get("all") or []} for e in o.get("external_ids") or []},
        "website": links.get("website"), "wikipedia": links.get("wikipedia"),
        "relationships": [{"type": r.get("type"), "name": r.get("label"), "id": r.get("id")} for r in o.get("relationships") or []],
        "last_modified": ((o.get("admin") or {}).get("last_modified") or {}).get("date"),
        "link": o.get("id"),
    }


@mcp.tool(name="ror_index", annotations=_READ_ONLY)
async def ror_index() -> dict:
    """How to use the Research Organization Registry tools. READ THIS FIRST: what a ROR id is for and how to read a match."""
    return {
        "upstream": BASE + " (ROR API v2), no key",
        "workflow": ["ror_search by name, narrowed by country and type; or with affiliation=True on the affiliation string as written on a paper or a CV",
                     "ror_organization by id for the full record: every name, the ids in other registries, parents and children"],
        "notes": ["A ROR id (https://ror.org/03hbp5t65) is the persistent identifier ORCID, OpenAlex, Crossref and DataCite use for an institution; it is the id to record for a collaborator's or subrecipient's institution.",
                  "external_ids.fundref is the Crossref Funder Registry id, the one funder acknowledgements and Crossref metadata use; grid, isni and wikidata are the same organization in those registries.",
                  "An affiliation search returns chosen True on one candidate when ROR is confident; otherwise read the scores and the names yourself. Departments and labs do not have ROR ids; the university does.",
                  "relationships show parents (a health system over a hospital), children (a campus, a center) and related organizations; a subaward goes to the legal entity, which may be the parent.",
                  "status is active, inactive (the organization closed or merged) or withdrawn (the record was an error); an inactive record names its successor in relationships.",
                  "20 results a page, pages from 1; cite the ROR id as the link."],
    }


@mcp.tool(name="ror_search", annotations=_READ_ONLY)
async def ror_search(query: str, affiliation: bool = False, country: str = "", type: str = "", page: int = 1) -> dict:
    """Find research organizations in ROR by name, or match an affiliation string.

    Returns each organization with its ROR id, names, type, location and registry ids. With affiliation True the query
    is a whole affiliation line ('Dept of Biology, University of Idaho, Moscow ID') and each candidate carries a score
    and whether ROR chose it; country, type and page do not apply then.

    Args:
        query: Organization name or words, e.g. 'University of Idaho'; or the affiliation string when affiliation is True.
        affiliation: True to match a free-text affiliation string rather than search names. Default False.
        country: Two-letter country code to narrow, e.g. 'US'. Empty for any.
        type: One organization type: education, healthcare, company, archive, nonprofit, government, facility, funder or other. Empty for any.
        page: Page number from 1. Default 1.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "query is required"}
    params: dict = {}
    if affiliation:
        params["affiliation"] = q
    else:
        params["query"] = q
        filters = []
        if country.strip():
            filters.append("country.country_code:" + country.strip().upper())
        if type.strip():
            t = type.strip().lower()
            if t not in TYPES:
                return {"error": f"type must be one of {list(TYPES)}"}
            filters.append("types:" + t)
        if filters:
            params["filter"] = ",".join(filters)
        params["page"] = max(1, int(page or 1))
    key = "search:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(key, HOUR, lambda: get_json(BASE, params))
    except ValueError as e:
        return {"error": str(e)}
    items = body.get("items") or []
    total = body.get("number_of_results")
    if affiliation:
        matches = [{**slim_organization(i.get("organization") or {}), "score": i.get("score"), "chosen": i.get("chosen"), "matching_type": i.get("matching_type")} for i in items]
        chosen = [m for m in matches if m.get("chosen")]
        return {"affiliation": q, "returned": len(matches), "chosen": chosen[0]["id"] if chosen else None, "matches": matches,
                "note": "ROR chose no candidate with confidence; compare names and locations." if not chosen else None}
    orgs = [slim_organization(i) for i in items]
    out = {"query": q, "page": params["page"], "returned": len(orgs), "total": total, "organizations": orgs}
    if isinstance(total, int) and params["page"] * PAGE < total:
        out["next_page"] = params["page"] + 1
    return out


@mcp.tool(name="ror_organization", annotations=_READ_ONLY)
async def ror_organization(ror_id: str) -> dict:
    """One organization's full ROR record by id: names, location, types, registry ids, relationships and status.

    Args:
        ror_id: The ROR id, as 'https://ror.org/03hbp5t65' or the bare '03hbp5t65'.
    """
    bare = _bare_id(ror_id)
    if not bare:
        return {"error": "ror_id must be a ROR id like https://ror.org/03hbp5t65 or 03hbp5t65"}
    try:
        body = await _cache.remember(f"org:{bare}", DAY, lambda: get_json(f"{BASE}/{bare}"))
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no ROR record {bare}", "ror_id": bare}
        return {"error": str(e)}
    return slim_organization(body)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
