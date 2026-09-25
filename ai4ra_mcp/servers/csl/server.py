"""csl: the Consolidated Screening List, the export-control and sanctions lists of Commerce, State and Treasury in one search.

Upstream: https://data.trade.gov/consolidated_screening_list/v1/search. A free trade.gov subscription key, sent as the
subscription-key header. 50 results a page by offset; dates are YYYY-MM-DD; fuzzy_name matches near spellings, so a
hit is a lead to verify against the source list, not a verdict.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import HOUR, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_CSL_KEY"
KEY_HOW = "A free key comes from https://developer.trade.gov/ : sign up, subscribe to the Consolidated Screening List API, and copy the subscription key."
BASE = "https://data.trade.gov/consolidated_screening_list/v1/search"
TYPES = ("Individual", "Entity", "Vessel", "Aircraft")
# The thirteen lists the CSL merges, keyed by the code the sources parameter takes. What each list means for a
# transaction is the agency's, summarized here so a model can say which list a hit is on and why it matters.
SOURCES = {
    "CAP": {"name": "Capta List", "agency": "Treasury, OFAC", "what": "Foreign financial institutions subject to correspondent or payable-through account sanctions."},
    "CMIC": {"name": "Non-SDN Chinese Military-Industrial Complex Companies List", "agency": "Treasury, OFAC", "what": "Companies whose publicly traded securities U.S. persons may not buy or sell; not a blocking list."},
    "DPL": {"name": "Denied Persons List", "agency": "Commerce, BIS", "what": "Persons denied export privileges; no export or reexport transaction with them of items subject to the EAR."},
    "DTC": {"name": "ITAR Debarred", "agency": "State, DDTC", "what": "Persons debarred from exporting defense articles and services under the ITAR (22 CFR 127.7)."},
    "EL": {"name": "Entity List", "agency": "Commerce, BIS", "what": "Foreign parties for which a license is required for exports, reexports and transfers of listed items (EAR Supplement 4 to Part 744)."},
    "FSE": {"name": "Foreign Sanctions Evaders", "agency": "Treasury, OFAC", "what": "Foreign persons found to have evaded Iran or Syria sanctions; U.S. persons may not deal with them."},
    "ISN": {"name": "Nonproliferation Sanctions", "agency": "State, ISN", "what": "Parties sanctioned under nonproliferation statutes and executive orders; the program names the authority."},
    "MEU": {"name": "Military End User List", "agency": "Commerce, BIS", "what": "Parties for which a license is required for listed items because of military end use (EAR Supplement 7 to Part 744)."},
    "NS-MBS": {"name": "Non-SDN Menu-Based Sanctions List", "agency": "Treasury, OFAC", "what": "Persons subject to menu-based sanctions (CAATSA and Ukraine-related); the restrictions are specific, not blocking."},
    "PLC": {"name": "Palestinian Legislative Council List", "agency": "Treasury, OFAC", "what": "PLC members elected on the Hamas slate; U.S. financial institutions must reject their transactions."},
    "SDN": {"name": "Specially Designated Nationals and Blocked Persons", "agency": "Treasury, OFAC", "what": "Assets blocked; U.S. persons are generally prohibited from dealing with them. The most consequential hit."},
    "SSI": {"name": "Sectoral Sanctions Identifications", "agency": "Treasury, OFAC", "what": "Russian entities restricted by sector directive (debt, equity, oil projects); not a blocking list."},
    "UVL": {"name": "Unverified List", "agency": "Commerce, BIS", "what": "Parties BIS could not verify; license exceptions are unavailable and a UVL statement is required before export."},
}
_cache = TTLCache()

mcp = MCPServer(
    "csl",
    instructions="Consolidated Screening List: export-control and sanctions screening of a name against the BIS, OFAC and State lists (Entity List, SDN, Denied Persons, ITAR debarred and the rest). Needs a free trade.gov key. Read csl_index first.",
)


def _source_code(source: str | None) -> str | None:
    # "Entity List (EL) - Bureau of Industry and Security" carries its code in parentheses; NS-MBS says "(NS-MBS List)".
    m = re.search(r"\(([A-Z-]+)(?: List)?\)", source or "")
    return m.group(1) if m else None


def slim_result(r: dict) -> dict:
    out = {
        "name": r.get("name"), "alt_names": r.get("alt_names") or [], "type": r.get("type"),
        "source": _source_code(r.get("source")), "source_list": r.get("source"), "programs": r.get("programs") or [],
        "entity_number": r.get("entity_number"), "id": r.get("id"),
        "addresses": [{"address": a.get("address"), "city": a.get("city"), "state": a.get("state"), "postal_code": a.get("postal_code"), "country": a.get("country")}
                      for a in r.get("addresses") or []],
        "ids": [{"type": i.get("type"), "number": i.get("number"), "country": i.get("country"), "issue_date": i.get("issue_date"), "expiration_date": i.get("expiration_date")}
                for i in r.get("ids") or []],
        "start_date": r.get("start_date"), "end_date": r.get("end_date"),
        "license_requirement": r.get("license_requirement"), "license_policy": r.get("license_policy"),
        "remarks": r.get("remarks") or None, "federal_register_notice": r.get("federal_register_notice") or None,
        "source_list_url": r.get("source_list_url"), "link": r.get("source_information_url"),
    }
    # Person fields, only when the record has them, so an entity's record stays short.
    for k in ("title", "dates_of_birth", "places_of_birth", "nationalities", "citizenships", "country"):
        if r.get(k):
            out[k] = r[k]
    return out


@mcp.tool(name="csl_index", annotations=_READ_ONLY)
async def csl_index() -> dict:
    """How to use the Consolidated Screening List tools. READ THIS FIRST: the key, what the lists are, how to read a hit."""
    return {
        "upstream": "https://data.trade.gov/consolidated_screening_list/v1/search (trade.gov), thirteen lists refreshed hourly from BIS, OFAC and State",
        "key": {"on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own trade.gov subscription key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "workflow": ["csl_search the exact legal name; then each known alias, former name and the principals' names, one search each",
                     "csl_sources when you need to say what a list is and which agency keeps it",
                     "for a hit, cite the source list, the entity_number (OFAC) or id, and the source_list_url; verify on the agency's own list before acting"],
        "notes": ["This is export-control and sanctions screening (BIS, OFAC, State). It is separate from SAM.gov exclusions (debarment from federal awards) and the OIG LEIE; a subrecipient or vendor check runs all three.",
                  "fuzzy matching returns near spellings, so a hit is a lead, not a verdict: compare the addresses, ids, dates of birth and programs before calling it a match.",
                  "A common name on the SDN list matches many unrelated people; narrow with countries or type, and check the alt_names.",
                  "source is the list's code (SDN, EL, DPL, DTC, UVL, ...); csl_sources says what each means for a transaction. An SDN or Entity List hit needs export-control counsel before any dealing.",
                  "entity_number is OFAC's identifier and is absent on BIS and State records; id is the CSL's own and is always present.",
                  "Dates are YYYY-MM-DD; end_date on a Denied Persons record is when the denial expires."],
    }


@mcp.tool(name="csl_search", annotations=_READ_ONLY)
async def csl_search(name: str, fuzzy: bool = True, sources: str = "", countries: str = "", type: str = "", offset: int = 0, size: int = 25) -> dict:
    """Screen a name against the Consolidated Screening List.

    Use it for any foreign or domestic party in a proposal, subaward, purchase or collaboration. Returns each matching
    record with its list, programs, addresses, ids, dates and license terms.

    Args:
        name: The name to screen, e.g. 'Havin Bank Limited'. Search the exact name, then each alias.
        fuzzy: True (default) matches near spellings; False matches the words exactly.
        sources: Comma-separated list codes to search, e.g. 'SDN,EL,DPL'. Empty for all thirteen.
        countries: Comma-separated two-letter country codes, e.g. 'CN,RU'. Empty for any.
        type: 'Individual', 'Entity', 'Vessel' or 'Aircraft'. Empty for any.
        offset: First record, 0-based. Default 0.
        size: Records to return, 1-50. Default 25.
    """
    q = (name or "").strip()
    if not q:
        return {"error": "name is required"}
    params: dict = {"name": q, "fuzzy_name": "true" if fuzzy else "false", "offset": max(0, int(offset or 0)), "size": max(1, min(int(size or 25), 50))}
    if sources.strip():
        codes = [c.strip().upper() for c in sources.split(",") if c.strip()]
        unknown = [c for c in codes if c not in SOURCES]
        if unknown:
            return {"error": f"unknown source codes {unknown}; csl_sources lists them"}
        params["sources"] = ",".join(codes)
    if countries.strip():
        params["countries"] = ",".join(c.strip().upper() for c in countries.split(",") if c.strip())
    if type.strip():
        t = type.strip().capitalize()
        if t not in TYPES:
            return {"error": f"type must be one of {list(TYPES)}"}
        params["type"] = t
    key = api_key(KEY_ENV)
    if not key:
        return missing_key(KEY_ENV, KEY_HOW)
    cache_key = "search:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(cache_key, HOUR, lambda: get_json(BASE, params, {"subscription-key": key}))
    except ValueError as e:
        return {"error": str(e)}
    results = [slim_result(r) for r in body.get("results") or []]
    out = {"name": q, "fuzzy": bool(fuzzy), "offset": params["offset"], "returned": len(results), "total": body.get("total"), "results": results,
           "search_performed_at": body.get("search_performed_at"),
           "sources_used": [{"source": _source_code(s.get("source")), "source_last_updated": s.get("source_last_updated")} for s in body.get("sources_used") or []]}
    if isinstance(body.get("total"), int) and params["offset"] + len(results) < body["total"]:
        out["next_offset"] = params["offset"] + len(results)
    if not results:
        out["note"] = "No record on any searched list matches this name. Search aliases and former names too before recording a clear result."
    return out


@mcp.tool(name="csl_sources", annotations=_READ_ONLY)
async def csl_sources() -> dict:
    """The thirteen lists the Consolidated Screening List merges: code, name, agency and what a listing means."""
    return {"sources": [{"code": code, **info} for code, info in SOURCES.items()],
            "note": "Codes are what csl_search's sources argument takes. Blocking lists (SDN, FSE) bar dealing outright; BIS lists (EL, DPL, UVL, MEU) restrict exports of items subject to the EAR; DTC restricts defense articles; SSI, NS-MBS and CMIC restrict specific transactions."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
