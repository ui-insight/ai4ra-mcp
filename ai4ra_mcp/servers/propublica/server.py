"""propublica: ProPublica's Nonprofit Explorer, the IRS Form 990 record of tax-exempt organizations.

Upstream: https://projects.propublica.org/nonprofits/api/v2/ (search.json, organizations/{ein}.json). No key.
25 results a page, page numbers from 0. Filings carry the IRS extract's totals for the filing year and a PDF link.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
BASE = "https://projects.propublica.org/nonprofits/api/v2"
# IRS subsection codes, as the API's subseccd / subsection_code and its c_code filter use them.
SUBSECTIONS = {2: "title-holding corporation", 3: "charitable, educational, religious or scientific", 4: "social welfare organization",
               5: "labor or agricultural organization", 6: "business league or chamber of commerce", 7: "social or recreational club",
               8: "fraternal beneficiary society", 9: "voluntary employees' beneficiary association", 10: "domestic fraternal society",
               12: "benevolent life insurance or cooperative", 13: "cemetery company", 14: "credit union", 15: "mutual insurance company",
               17: "supplemental unemployment benefit trust", 19: "veterans' organization", 25: "title-holding corporation for multiple parents"}
# The ntee filter takes a category number, not an NTEE letter code.
NTEE_CATEGORIES = {1: "Arts, Culture and Humanities", 2: "Education", 3: "Environment and Animals", 4: "Health", 5: "Human Services",
                   6: "International, Foreign Affairs", 7: "Public, Societal Benefit", 8: "Religion Related", 9: "Mutual/Membership Benefit", 10: "Unknown, Unclassified"}
FORMS = {0: "990", 1: "990-EZ", 2: "990-PF"}
_cache = TTLCache()

mcp = MCPServer(
    "propublica",
    instructions="ProPublica Nonprofit Explorer: a tax-exempt organization by name or EIN, its IRS status, and its Form 990 revenue, expenses, assets and liabilities by year. Read propublica_nonprofit_index first.",
)


def _subsection(code) -> str | None:
    if code is None:
        return None
    if code == 92:
        return "4947(a)(1) non-exempt charitable trust"
    label = SUBSECTIONS.get(code)
    return f"501(c)({code})" + (f" {label}" if label else "")


def _strein(ein) -> str | None:
    s = str(ein).zfill(9) if ein is not None else ""
    return f"{s[:2]}-{s[2:]}" if len(s) == 9 else None


def _link(ein) -> str:
    return f"https://projects.propublica.org/nonprofits/organizations/{ein}"


def slim_search_org(o: dict) -> dict:
    return {"ein": o.get("ein"), "ein_formatted": o.get("strein") or _strein(o.get("ein")), "name": o.get("name"), "city": o.get("city"), "state": o.get("state"),
            "ntee_code": o.get("ntee_code"), "subsection": _subsection(o.get("subseccd")), "score": o.get("score"), "link": _link(o.get("ein"))}


def slim_organization(o: dict) -> dict:
    return {"name": o.get("name"), "ein": o.get("ein"), "ein_formatted": _strein(o.get("ein")), "care_of": o.get("careofname"),
            "address": o.get("address"), "city": o.get("city"), "state": o.get("state"), "zip": o.get("zipcode"),
            "ntee_code": o.get("ntee_code"), "subsection": _subsection(o.get("subsection_code")), "ruling_date": o.get("ruling_date"),
            "latest_tax_period": o.get("tax_period"), "irs_data_as_of": o.get("data_source"), "link": _link(o.get("ein"))}


def slim_filing(f: dict) -> dict:
    return {"tax_year": f.get("tax_prd_yr"), "tax_period": f.get("tax_prd"), "form": FORMS.get(f.get("formtype"), f.get("formtype_str")),
            "total_revenue": f.get("totrevenue"), "total_expenses": f.get("totfuncexpns"), "total_assets_end": f.get("totassetsend"),
            "total_liabilities_end": f.get("totliabend"), "net_assets_end": f.get("totnetassetend"), "contributions_and_grants": f.get("totcntrbgfts"),
            "pdf_url": f.get("pdf_url")}


@mcp.tool(name="propublica_nonprofit_index", annotations=_READ_ONLY)
async def propublica_nonprofit_index() -> dict:
    """How to use the Nonprofit Explorer tools. READ THIS FIRST: what the data is and is not, and how to read the figures."""
    return {
        "upstream": BASE + "/ (ProPublica, from the IRS Exempt Organizations Business Master File and Form 990 extracts), no key",
        "workflow": ["propublica_nonprofit_search by name, narrowed by state, subsection or NTEE category; note the EIN",
                     "propublica_nonprofit_organization by EIN for the IRS record and the Form 990 totals by year"],
        "notes": ["This is IRS Form 990 data: a public university, a state agency or a tribal government does not file a 990 and may not appear or may appear with no filings. Absence is not a finding.",
                  "total_revenue and total_expenses are the organization's whole year, all sources. The single-audit threshold under 2 CFR 200.501 is federal expenditure, not revenue, so this is context on size and health; the audit check is the fac server.",
                  "subsection says the exemption: 501(c)(3) is a charity or educational organization; 501(c)(4) and (6) are not charities and may need a different subaward basis.",
                  "ruling_date is when the IRS recognized the exemption; a recent one on a large budget is worth a question.",
                  "Filings are newest first, at most 10; older ones and any without extracted data are counted. pdf_url is the filed form.",
                  "25 results a page, pages from 0; cite the link, which is the organization's page on Nonprofit Explorer."],
    }


@mcp.tool(name="propublica_nonprofit_search", annotations=_READ_ONLY)
async def propublica_nonprofit_search(query: str, state: str = "", ntee_category: str = "", subsection: str = "", page: int = 0) -> dict:
    """Search tax-exempt organizations by name.

    Returns each organization with its EIN, city, state, NTEE code, subsection and a link; then use the EIN for the
    organization's record and filings.

    Args:
        query: Words of the name, e.g. 'Idaho Community Foundation'.
        state: Two-letter state, e.g. 'ID'. Empty for any.
        ntee_category: NTEE category number 1-10 (1 arts, 2 education, 3 environment and animals, 4 health, 5 human services, 6 international, 7 public benefit, 8 religion, 9 membership, 10 unclassified). Empty for any.
        subsection: IRS subsection code, e.g. '3' for 501(c)(3), '4', '6'; '92' for a 4947(a)(1) trust. Empty for any.
        page: Page number from 0. Default 0.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "query is required"}
    params: dict = {"q": q, "page": max(0, int(page or 0))}
    if state.strip():
        params["state[id]"] = state.strip().upper()
    if ntee_category.strip():
        if not ntee_category.strip().isdigit() or int(ntee_category) not in NTEE_CATEGORIES:
            return {"error": "ntee_category must be a number 1-10"}
        params["ntee[id]"] = int(ntee_category)
    if subsection.strip():
        if not subsection.strip().isdigit():
            return {"error": "subsection must be a number, e.g. 3 for 501(c)(3)"}
        params["c_code[id]"] = int(subsection)
    key = "search:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(key, HOUR, lambda: get_json(f"{BASE}/search.json", params))
    except ValueError as e:
        return {"error": str(e)}
    orgs = [slim_search_org(o) for o in body.get("organizations") or []]
    out = {"query": q, "page": body.get("cur_page", params["page"]), "returned": len(orgs), "total": body.get("total_results"), "num_pages": body.get("num_pages"), "organizations": orgs}
    if isinstance(body.get("num_pages"), int) and out["page"] + 1 < body["num_pages"]:
        out["next_page"] = out["page"] + 1
    return out


@mcp.tool(name="propublica_nonprofit_organization", annotations=_READ_ONLY)
async def propublica_nonprofit_organization(ein: str) -> dict:
    """One tax-exempt organization by EIN: the IRS record and its Form 990 totals by year, newest first.

    Args:
        ein: The employer identification number, with or without the hyphen, e.g. '82-6000945'.
    """
    digits = "".join(ch for ch in (ein or "") if ch.isdigit())
    if not digits or len(digits) > 9:
        return {"error": "ein must be the 9-digit employer identification number"}
    try:
        body = await _cache.remember(f"org:{digits}", DAY, lambda: get_json(f"{BASE}/organizations/{int(digits)}.json"))
    except ValueError as e:
        if "404" in str(e):
            return {"error": f"no organization with EIN {digits} in Nonprofit Explorer; a government unit or a public university may not file a Form 990", "ein": digits}
        return {"error": str(e)}
    org = body.get("organization") or {}
    with_data = sorted(body.get("filings_with_data") or [], key=lambda f: f.get("tax_prd") or 0, reverse=True)
    without = body.get("filings_without_data") or []
    return {**slim_organization(org), "filings": [slim_filing(f) for f in with_data[:10]], "filings_with_data_count": len(with_data),
            "filings_without_data": sorted({f.get("tax_prd_yr") for f in without if f.get("tax_prd_yr")}, reverse=True),
            "note": "No filing with extracted data; the organization may be new, file a form ProPublica does not extract, or not file a 990 at all." if not with_data else None}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
