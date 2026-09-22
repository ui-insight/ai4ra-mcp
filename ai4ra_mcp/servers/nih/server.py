"""nih: NIH RePORTER, the public record of NIH-funded projects and their publications.

Upstream: https://api.reporter.nih.gov/ (v2). No key. One request a second is the advised pace;
500 records a page; the offset cannot pass 14,999.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, post_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://api.reporter.nih.gov/v2"
PROJECT_FIELDS = ["ApplId", "ProjectNum", "CoreProjectNum", "ProjectTitle", "FiscalYear", "AwardAmount", "DirectCostAmt", "IndirectCostAmt",
                  "ProjectStartDate", "ProjectEndDate", "BudgetStart", "BudgetEnd", "AgencyIcAdmin", "AgencyCode", "ActivityCode", "AwardType", "SubprojectId",
                  "FundingMechanism", "Organization", "PrincipalInvestigators", "ContactPiName", "ProgramOfficers", "IsActive", "OpportunityNumber",
                  "CfdaCode", "ProjectDetailUrl"]
_cache = TTLCache()

mcp = MCPServer(
    "nih",
    instructions="NIH RePORTER: NIH-funded projects by PI, organization, year, activity code or text, one project by number, and the publications of a project. Read nih_index first.",
)


def _slim_project(p: dict) -> dict:
    org = p.get("organization") or {}
    ic = p.get("agency_ic_admin") or {}
    return {
        "appl_id": p.get("appl_id"), "project_num": p.get("project_num"), "core_project_num": p.get("core_project_num"), "subproject_id": p.get("subproject_id"),
        "title": p.get("project_title"), "fiscal_year": p.get("fiscal_year"),
        "award_amount": p.get("award_amount"), "direct_cost": p.get("direct_cost_amt"), "indirect_cost": p.get("indirect_cost_amt"),
        "project_start": (p.get("project_start_date") or "")[:10] or None, "project_end": (p.get("project_end_date") or "")[:10] or None,
        "budget_start": (p.get("budget_start") or "")[:10] or None, "budget_end": (p.get("budget_end") or "")[:10] or None,
        "agency": ic.get("abbreviation") or p.get("agency_code"), "activity_code": p.get("activity_code"), "award_type": p.get("award_type"),
        "funding_mechanism": p.get("funding_mechanism"), "is_active": p.get("is_active"), "opportunity_number": p.get("opportunity_number"),
        "assistance_listing": p.get("cfda_code"),
        "organization": {"name": org.get("org_name"), "city": org.get("org_city"), "state": org.get("org_state"), "uei": org.get("primary_uei")},
        "principal_investigators": [{"name": i.get("full_name"), "contact_pi": i.get("is_contact_pi")} for i in p.get("principal_investigators") or []],
        "program_officers": [o.get("full_name") for o in p.get("program_officers") or []],
        "link": p.get("project_detail_url"),
    }


def _csv(v: str) -> list[str]:
    return [s.strip() for s in re.split(r"[|,]", v or "") if s.strip()]


async def _search(criteria: dict, offset: int, limit: int, fields: list[str] | None = None, sort: str | None = None) -> dict:
    payload = {"criteria": criteria, "offset": offset, "limit": limit, "include_fields": fields or PROJECT_FIELDS}
    if sort:
        payload["sort_field"] = sort
        payload["sort_order"] = "desc"
    key = "search:" + repr(sorted(payload.items()))
    return await _cache.remember(key, HOUR, lambda: post_json(f"{BASE}/projects/search", payload))


@mcp.tool(name="nih_index", annotations=_READ_ONLY)
async def nih_index() -> dict:
    """How to use the NIH RePORTER tools. READ THIS FIRST.

    Returns the search criteria each tool accepts, the pace to keep, and the workflow: search by PI or organization,
    then read one project by number, then its publications by core project number.
    """
    return {
        "upstream": "https://api.reporter.nih.gov/ (v2), no key; keep to about one request a second",
        "workflow": ["nih_projects_search by PI name, organization, fiscal years, activity codes or text",
                     "nih_project for one project by its number (e.g. 5R01AI135270-05 or the core R01AI135270)",
                     "nih_publications for a project's publications by core project number; each has a PubMed id"],
        "notes": ["Fiscal years are NIH fiscal years (October to September).",
                  "A project number's leading digit is the application type (1 new, 5 continuation, 3 supplement); the core project number drops it and the year suffix.",
                  "award_amount is the fiscal year's total costs; direct and indirect are given when RePORTER has them.",
                  "Names match any part: 'Layman' finds every PI with that word in the name; give first and last to narrow.",
                  "A center or program grant (P30, P50, U54) returns one record per component with the same project number and a subproject_id; the record with no subproject_id is the parent.",
                  "Results carry a link to the RePORTER project page; cite it."],
        "limits": {"page": "1-500 records", "offset_max": 14999},
    }


@mcp.tool(name="nih_projects_search", annotations=_READ_ONLY)
async def nih_projects_search(
    pi_name: str = "",
    organization: str = "",
    fiscal_years: str = "",
    activity_codes: str = "",
    agencies: str = "",
    text: str = "",
    active_only: bool = False,
    org_state: str = "",
    offset: int = 0,
    limit: int = 25,
) -> dict:
    """Search NIH-funded projects in RePORTER.

    Give at least one of pi_name, organization, text, activity_codes or agencies. Returns projects with number,
    title, PI(s), organization, agency, amounts, dates and a link.

    Args:
        pi_name: Any part of a PI's name, e.g. 'Layman' or 'Nathan Layman'.
        organization: Organization name, e.g. 'University of Idaho' (partial match).
        fiscal_years: Comma-separated NIH fiscal years, e.g. '2024,2025'. Empty for all.
        activity_codes: Comma-separated activity codes, e.g. 'R01,R21,P20'. Empty for all.
        agencies: Comma-separated NIH institute or agency codes, e.g. 'NIAID,NIGMS'. Empty for all.
        text: Words to match in the title, abstract and terms.
        active_only: True for projects active today only.
        org_state: Two-letter state, e.g. 'ID'.
        offset: Record to start from. Default 0.
        limit: Records to return, 1-500. Default 25.
    """
    criteria: dict = {}
    if pi_name.strip():
        parts = pi_name.strip().split()
        criteria["pi_names"] = [{"any_name": pi_name.strip()}] if len(parts) == 1 else [{"first_name": parts[0], "last_name": parts[-1]}]
    if organization.strip():
        criteria["org_names"] = [organization.strip()]
    years = [int(y) for y in _csv(fiscal_years) if y.isdigit()]
    if years:
        criteria["fiscal_years"] = years
    if _csv(activity_codes):
        criteria["activity_codes"] = [c.upper() for c in _csv(activity_codes)]
    if _csv(agencies):
        criteria["agencies"] = [a.upper() for a in _csv(agencies)]
    if text.strip():
        criteria["advanced_text_search"] = {"operator": "and", "search_field": "projecttitle,terms,abstracttext", "search_text": text.strip()}
    if active_only:
        criteria["include_active_projects"] = True
    if org_state.strip():
        criteria["org_states"] = [org_state.strip().upper()]
    if not criteria or set(criteria) <= {"fiscal_years", "include_active_projects", "org_states"}:
        return {"error": "give at least one of pi_name, organization, text, activity_codes or agencies"}
    limit = max(1, min(int(limit or 25), 500))
    offset = max(0, min(int(offset or 0), 14999))
    try:
        body = await _search(criteria, offset, limit, sort="project_start_date")
    except ValueError as e:
        return {"error": str(e)}
    meta = body.get("meta") or {}
    results = [_slim_project(p) for p in body.get("results") or []]
    out = {"criteria": criteria, "total": meta.get("total"), "offset": offset, "returned": len(results), "projects": results}
    if isinstance(meta.get("total"), int) and offset + len(results) < meta["total"]:
        out["next_offset"] = offset + len(results)
    return out


@mcp.tool(name="nih_project", annotations=_READ_ONLY)
async def nih_project(project_num: str) -> dict:
    """One NIH project by its number, with its abstract and public health relevance.

    Args:
        project_num: A full project number ('5R01AI135270-05') or a core project number ('R01AI135270'), which returns every year's record.
    """
    num = (project_num or "").strip().upper()
    if not num:
        return {"error": "project_num is required"}
    core = re.fullmatch(r"[A-Z]\d{2}[A-Z]{2}\d{6}", num) is not None
    criteria = {"project_nums": [num]} if not core else {"project_nums": [f"*{num}*"]}
    fields = PROJECT_FIELDS + ["AbstractText", "PhrText", "Terms", "PrefTerms", "FullStudySection"]
    try:
        body = await _cache.remember(f"project:{num}", DAY, lambda: post_json(f"{BASE}/projects/search", {"criteria": criteria, "limit": 20, "include_fields": fields, "sort_field": "fiscal_year", "sort_order": "desc"}))
    except ValueError as e:
        return {"error": str(e)}
    results = body.get("results") or []
    if not results:
        return {"error": f"no project {num} in RePORTER", "project_num": num}
    out = [{**_slim_project(p), "abstract": p.get("abstract_text"), "public_health_relevance": p.get("phr_text"), "study_section": p.get("full_study_section")} for p in results]
    return {"project_num": num, "records": len(out), "projects": out}


@mcp.tool(name="nih_publications", annotations=_READ_ONLY)
async def nih_publications(core_project_num: str, offset: int = 0, limit: int = 50) -> dict:
    """Publications linked to an NIH project, by core project number. Each has a PubMed id and a link.

    Args:
        core_project_num: The core project number, e.g. 'R01AI135270' (no application type or year suffix).
        offset: Record to start from. Default 0.
        limit: Records to return, 1-500. Default 50.
    """
    core = (core_project_num or "").strip().upper()
    if not core:
        return {"error": "core_project_num is required"}
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))
    payload = {"criteria": {"core_project_nums": [core]}, "offset": offset, "limit": limit}
    try:
        body = await _cache.remember(f"pubs:{core}:{offset}:{limit}", DAY, lambda: post_json(f"{BASE}/publications/search", payload))
    except ValueError as e:
        return {"error": str(e)}
    meta = body.get("meta") or {}
    pubs = [{"pmid": r.get("pmid"), "core_project_num": r.get("coreproject"), "appl_id": r.get("applid"),
             "link": f"https://pubmed.ncbi.nlm.nih.gov/{r.get('pmid')}/"} for r in body.get("results") or []]
    out = {"core_project_num": core, "total": meta.get("total"), "offset": offset, "returned": len(pubs), "publications": pubs,
           "note": "RePORTER gives ids only; fetch a PubMed link with fetch_document on the ai4ra server for the citation."}
    if isinstance(meta.get("total"), int) and offset + len(pubs) < meta["total"]:
        out["next_offset"] = offset + len(pubs)
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
