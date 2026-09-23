"""nsf: NSF Award Search, the public record of NSF awards.

Upstream: https://api.nsf.gov/services/v1/ (awards.json, awards/{id}.json, awards/{id}/projectoutcomes.json).
No key. 25 results a page, 3,000 at most for one query. Dates are MM/DD/YYYY.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.nsf.gov/services/v1"
LIST_FIELDS = "id,title,awardeeName,awardeeCity,awardeeStateCode,pdPIName,coPDPI,date,startDate,expDate,fundsObligatedAmt,estimatedTotalAmt,primaryProgram,fundProgramDir,agency,cfdaNumber,ueiNumber"
AWARD_FIELDS = LIST_FIELDS + ",abstractText,piFirstName,piLastName,piEmail,poName,awardeeAddress,perfLocation,transType,publicationResearch,publicationConference"
_cache = TTLCache()

mcp = MCPServer(
    "nsf",
    instructions="NSF Award Search: awards by PI, institution, program, dates or keyword; one award by id with its abstract; an award's project outcomes report. Read nsf_index first.",
)


def _slim(a: dict) -> dict:
    return {
        "id": a.get("id"), "title": a.get("title"), "pi": a.get("pdPIName"), "co_pis": a.get("coPDPI"),
        "awardee": a.get("awardeeName"), "awardee_city": a.get("awardeeCity"), "awardee_state": a.get("awardeeStateCode"), "awardee_uei": a.get("ueiNumber"),
        "award_date": a.get("date"), "start_date": a.get("startDate"), "end_date": a.get("expDate"),
        "obligated_amount": a.get("fundsObligatedAmt"), "estimated_total": a.get("estimatedTotalAmt"),
        "program": a.get("primaryProgram"), "directorate": a.get("fundProgramDir"), "agency": a.get("agency"), "assistance_listing": a.get("cfdaNumber"),
        "link": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={a.get('id')}",
    }


@mcp.tool(name="nsf_index", annotations=_READ_ONLY)
async def nsf_index() -> dict:
    """How to use the NSF Award Search tools. READ THIS FIRST."""
    return {
        "upstream": "https://api.nsf.gov/services/v1/, no key",
        "workflow": ["nsf_awards_search by PI, awardee institution, keyword, program or date range",
                     "nsf_award for one award by id, with its abstract",
                     "nsf_award_outcomes for the project outcomes report the PI filed"],
        "notes": ["Dates are MM/DD/YYYY in both requests and results.",
                  "obligated_amount is what NSF has obligated so far; estimated_total is the full expected value.",
                  "Results carry a link to the award page on nsf.gov; cite it.",
                  "25 results a page and 3,000 at most for one query; narrow by date or awardee when a search is large."],
    }


@mcp.tool(name="nsf_awards_search", annotations=_READ_ONLY)
async def nsf_awards_search(
    keyword: str = "",
    pi_name: str = "",
    awardee: str = "",
    program: str = "",
    date_start: str = "",
    date_end: str = "",
    awardee_state: str = "",
    offset: int = 1,
    limit: int = 25,
) -> dict:
    """Search NSF awards.

    Give at least one of keyword, pi_name, awardee or program. Returns awards with id, title, PI, awardee,
    dates, amounts, program and a link.

    Args:
        keyword: Words in the title or abstract, e.g. 'wildfire smoke'.
        pi_name: Principal investigator name, e.g. 'Jane Smith'.
        awardee: Awardee institution, e.g. 'University of Idaho'; matched as a phrase, so give one name at a time (a former name is a second search).
        program: Program name or element code, e.g. 'EPSCoR'.
        date_start: Awards starting on or after MM/DD/YYYY.
        date_end: Awards starting on or before MM/DD/YYYY.
        awardee_state: Two-letter state, e.g. 'ID'.
        offset: First record, 1-based. Default 1.
        limit: Records to return, 1-25. Default 25.
    """
    params: dict = {"printFields": LIST_FIELDS, "rpp": max(1, min(int(limit or 25), 25)), "offset": max(1, int(offset or 1))}
    if keyword.strip():
        params["keyword"] = keyword.strip()
    if pi_name.strip():
        params["pdPIName"] = pi_name.strip()
    if awardee.strip():
        # The API matches an unquoted name on any word ("Canisius University" is every university); a quoted
        # phrase matches the name. A PI name is left unquoted: any-word finds "Andrew D Stewart" from "Andrew Stewart".
        name = awardee.strip()
        params["awardeeName"] = name if (name.startswith('"') or " " not in name) else f'"{name}"'
    if program.strip():
        params["primaryProgram"] = program.strip()
    if date_start.strip():
        params["dateStart"] = date_start.strip()
    if date_end.strip():
        params["dateEnd"] = date_end.strip()
    if awardee_state.strip():
        params["awardeeStateCode"] = awardee_state.strip().upper()
    if not any(k in params for k in ("keyword", "pdPIName", "awardeeName", "primaryProgram")):
        return {"error": "give at least one of keyword, pi_name, awardee or program"}
    key = "search:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(key, HOUR, lambda: get_json(f"{BASE}/awards.json", params))
    except ValueError as e:
        return {"error": str(e)}
    resp = body.get("response") or {}
    awards = [_slim(a) for a in resp.get("award") or []]
    out = {"offset": params["offset"], "returned": len(awards), "awards": awards}
    meta = resp.get("metadata") or {}
    if meta.get("totalCount") is not None:
        out["total"] = meta.get("totalCount")
    if len(awards) == params["rpp"]:
        out["next_offset"] = params["offset"] + len(awards)
    return out


@mcp.tool(name="nsf_award", annotations=_READ_ONLY)
async def nsf_award(award_id: str) -> dict:
    """One NSF award by id, with its abstract, program officer and performance location.

    Args:
        award_id: The seven-digit award id, e.g. '2425033'.
    """
    aid = (award_id or "").strip()
    if not aid.isdigit():
        return {"error": "award_id must be the numeric NSF award id"}
    try:
        body = await _cache.remember(f"award:{aid}", DAY, lambda: get_json(f"{BASE}/awards/{aid}.json", {"printFields": AWARD_FIELDS}))
    except ValueError as e:
        return {"error": str(e)}
    awards = (body.get("response") or {}).get("award") or []
    if not awards:
        return {"error": f"no NSF award {aid}", "award_id": aid}
    a = awards[0]
    return {**_slim(a), "abstract": a.get("abstractText"), "program_officer": a.get("poName"), "pi_email": a.get("piEmail"),
            "performance_location": a.get("perfLocation"), "transaction_type": a.get("transType"),
            "publications_research": a.get("publicationResearch"), "publications_conference": a.get("publicationConference")}


@mcp.tool(name="nsf_award_outcomes", annotations=_READ_ONLY)
async def nsf_award_outcomes(award_id: str) -> dict:
    """The project outcomes report the PI filed for an NSF award, as text.

    Args:
        award_id: The seven-digit award id.
    """
    aid = (award_id or "").strip()
    if not aid.isdigit():
        return {"error": "award_id must be the numeric NSF award id"}
    try:
        body = await _cache.remember(f"outcomes:{aid}", DAY, lambda: get_json(f"{BASE}/awards/{aid}/projectoutcomes.json", {"printFields": "id,title,projectOutcomesReport"}))
    except ValueError as e:
        return {"error": str(e)}
    awards = (body.get("response") or {}).get("award") or []
    if not awards:
        return {"error": f"no NSF award {aid}", "award_id": aid}
    a = awards[0]
    report = a.get("projectOutcomesReport")
    return {"id": a.get("id"), "title": a.get("title"), "outcomes_report": report,
            "note": None if report else "no project outcomes report has been filed for this award",
            "link": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={aid}"}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
