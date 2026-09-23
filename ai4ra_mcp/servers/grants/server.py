"""grants: funding opportunities on grants.gov."""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common import fetch as _fetch
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}

mcp = MCPServer(
    "grants",
    instructions="Federal funding opportunities from grants.gov: search, then fetch one opportunity's record by id.",
)


@mcp.tool(name="grants_gov_search", annotations=_READ_ONLY)
async def grants_gov_search(
    keyword: str,
    statuses: str = "posted|forecasted",
    agencies: str = "",
    categories: str = "",
    rows: int = 10,
    start: int = 0,
) -> dict:
    """Search federal funding opportunities on grants.gov (RFAs, NOFOs, program solicitations, BAAs).

    START HERE when the user wants to find a funding announcement. Then pass a hit's id to
    grants_gov_opportunity for the full record and its attachment links. When replying to a
    person, list the hits as a numbered markdown list, one line each: the title as a markdown
    link to the hit's link, then agency, status and close date.

    Args:
        keyword: Search words, e.g. 'research security', or an opportunity number like 'PD-25-275Y'.
        statuses: Pipe-separated: posted, forecasted, closed, archived. Default 'posted|forecasted'.
        agencies: Pipe-separated agency codes to narrow, e.g. 'NSF|HHS'. Empty for all; the result lists codes with counts.
        categories: Pipe-separated funding category codes, e.g. 'ST', 'ED', 'HL'. Empty for all.
        rows: Hits to return, 1-50. Default 10.
        start: Record to start from, for paging. Default 0.
    Returns: hit_count, hits (id, number, title, agency, status, open/close dates, link), the agency facet, and next_start when more remain.
    """
    return await _fetch.grants_gov_search(keyword, statuses=statuses, agencies=agencies, categories=categories, rows=rows, start=start)


@mcp.tool(name="grants_gov_opportunity", annotations=_READ_ONLY)
async def grants_gov_opportunity(opportunity_id: str, offset: int = 0, max_chars: int = 12000) -> dict:
    """Fetch one grants.gov opportunity's record by its id (the id field of a search hit).

    Returns the synopsis, dates, ceiling and floor, cost sharing, eligibility and attachment links.
    To read an attachment PDF, pass its link to fetch_document on the general server.

    Args:
        opportunity_id: The numeric grants.gov opportunity id, e.g. '358463'.
        offset: Character position to start from. Default 0.
        max_chars: Characters to return, 1000-40000. Default 12000.
    """
    opp = str(opportunity_id or "").strip()
    if not opp.isdigit():
        return {"error": "opportunity_id must be the numeric id from a search hit"}
    return await _fetch.fetch_document(_fetch.GRANTS_GOV_PAGE.format(id=opp), offset=offset, max_chars=max_chars)


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
