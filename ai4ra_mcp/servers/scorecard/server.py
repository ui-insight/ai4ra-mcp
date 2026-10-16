"""scorecard: the Department of Education's College Scorecard, the institution facts behind an eligibility check or a partner profile.

Upstream: https://api.data.gov/ed/collegescorecard/v1/schools (JSON; a free api.data.gov key as the X-Api-Key header).
One record per institution (IPEDS unit id), filtered by school.name (contains), school.state, school.city, control
(school.ownership 1 public, 2 private nonprofit, 3 private for-profit), predominant degree (school.degrees_awarded.
predominant 1 certificate, 2 associate, 3 bachelor's, 4 graduate), with fields chosen by name: location, control,
Carnegie classification codes, locale code, accreditor, the minority-serving flags (historically black, tribal;
hispanic and the others are null in the current release), enrollment, graduate students, race and ethnicity shares,
Pell grant rate, admission rate, tuition, net price, completion, median earnings, and program shares. The data is the
Department's yearly release; `latest` fields are the most recent year each measure was reported.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_SCORECARD_KEY"
KEY_HOW = "A free key comes from https://api.data.gov/signup/ (an email address is all it asks); the same key serves the fac, regulations, perdiem, govinfo and congress servers."
BASE = "https://api.data.gov/ed/collegescorecard/v1/schools"
SITE = "https://collegescorecard.ed.gov/"
DICTIONARY = "https://collegescorecard.ed.gov/data/documentation/"
ROWS, MAX_ROWS = 20, 100
LIST_FIELDS = "id,school.name,school.city,school.state,school.ownership,school.degrees_awarded.predominant,school.degrees_awarded.highest,school.carnegie_basic,latest.student.size,school.school_url"
SCHOOL_FIELDS = (LIST_FIELDS + ",school.zip,school.main_campus,school.branches,school.carnegie_undergrad,school.carnegie_size_setting,school.locale,school.accreditor,school.ope6_id,school.ope8_id,"
                 "school.minority_serving.historically_black,school.minority_serving.hispanic,school.minority_serving.tribal,school.minority_serving.aanapii,school.minority_serving.nant,school.minority_serving.annh,school.minority_serving.predominantly_black,"
                 "school.men_only,school.women_only,school.religious_affiliation,school.under_investigation,"
                 "latest.student.grad_students,latest.student.part_time_share,latest.student.demographics.race_ethnicity.white,latest.student.demographics.race_ethnicity.black,latest.student.demographics.race_ethnicity.hispanic,"
                 "latest.student.demographics.race_ethnicity.asian,latest.student.demographics.race_ethnicity.aian,latest.student.demographics.race_ethnicity.nhpi,"
                 "latest.aid.pell_grant_rate,latest.aid.federal_loan_rate,latest.admissions.admission_rate.overall,latest.cost.tuition.in_state,latest.cost.tuition.out_of_state,latest.cost.avg_net_price.public,latest.cost.avg_net_price.private,"
                 "latest.completion.consumer_rate,latest.student.retention_rate.four_year.full_time_pooled,latest.earnings.10_yrs_after_entry.median")
OWNERSHIP = {1: "public", 2: "private nonprofit", 3: "private for-profit"}
DEGREES = {0: "not classified", 1: "certificate", 2: "associate", 3: "bachelor's", 4: "graduate"}
_cache = TTLCache()

mcp = MCPServer(
    "scorecard",
    instructions="College Scorecard: institutions by name, state, city, control or predominant degree (scorecard_search) and one institution's record, from control and Carnegie codes to enrollment, Pell rate, cost and outcomes (scorecard_school). Needs a free api.data.gov key. Read scorecard_index first.",
)


def _headers() -> dict:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    return {"X-Api-Key": key}


async def _get(params: dict) -> dict:
    headers = _headers()
    body = await _cache.remember("schools:" + repr(sorted(params.items())), DAY, lambda: get_json(BASE, params, headers))
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        raise ValueError("College Scorecard did not return its results list")
    return body


def _pct(v):
    return round(v * 100, 1) if isinstance(v, (int, float)) else None


def slim_row(r: dict) -> dict:
    return {"id": r.get("id"), "name": r.get("school.name"), "city": r.get("school.city"), "state": r.get("school.state"),
            "control": OWNERSHIP.get(r.get("school.ownership"), r.get("school.ownership")), "predominant_degree": DEGREES.get(r.get("school.degrees_awarded.predominant"), r.get("school.degrees_awarded.predominant")),
            "highest_degree": DEGREES.get(r.get("school.degrees_awarded.highest"), r.get("school.degrees_awarded.highest")), "carnegie_basic_code": r.get("school.carnegie_basic"),
            "enrollment": r.get("latest.student.size"), "url": r.get("school.school_url"), "link": f"{SITE}school/?{r.get('id')}"}


def slim_school(r: dict) -> dict:
    out = slim_row(r)
    msi = {k: r.get(f"school.minority_serving.{k}") for k in ("historically_black", "tribal", "hispanic", "aanapii", "nant", "annh", "predominantly_black")}
    out.update({
        "zip": r.get("school.zip"), "main_campus": r.get("school.main_campus"), "branches": r.get("school.branches"), "accreditor": r.get("school.accreditor"),
        "ope6_id": r.get("school.ope6_id"), "ope8_id": r.get("school.ope8_id"),
        "carnegie_codes": {"basic": r.get("school.carnegie_basic"), "undergraduate": r.get("school.carnegie_undergrad"), "size_setting": r.get("school.carnegie_size_setting")}, "locale_code": r.get("school.locale"),
        "minority_serving": {k: (bool(v) if v in (0, 1) else None) for k, v in msi.items()},
        "men_only": bool(r.get("school.men_only")), "women_only": bool(r.get("school.women_only")), "religious_affiliation_code": r.get("school.religious_affiliation"),
        "under_investigation": bool(r.get("school.under_investigation")),
        "students": {"undergraduates": r.get("latest.student.size"), "graduate_students": r.get("latest.student.grad_students"), "part_time_pct": _pct(r.get("latest.student.part_time_share")),
                     "race_ethnicity_pct": {k: _pct(r.get(f"latest.student.demographics.race_ethnicity.{k}")) for k in ("white", "black", "hispanic", "asian", "aian", "nhpi")}},
        "aid": {"pell_grant_rate_pct": _pct(r.get("latest.aid.pell_grant_rate")), "federal_loan_rate_pct": _pct(r.get("latest.aid.federal_loan_rate"))},
        "admission_rate_pct": _pct(r.get("latest.admissions.admission_rate.overall")),
        "cost": {"tuition_in_state": r.get("latest.cost.tuition.in_state"), "tuition_out_of_state": r.get("latest.cost.tuition.out_of_state"),
                 "avg_net_price": r.get("latest.cost.avg_net_price.public") if r.get("latest.cost.avg_net_price.public") is not None else r.get("latest.cost.avg_net_price.private")},
        "outcomes": {"completion_rate_pct": _pct(r.get("latest.completion.consumer_rate")), "retention_rate_pct": _pct(r.get("latest.student.retention_rate.four_year.full_time_pooled")),
                     "median_earnings_10_years_after_entry": r.get("latest.earnings.10_yrs_after_entry.median")},
    })
    return out


@mcp.tool(name="scorecard_index", annotations=_READ_ONLY)
async def scorecard_index() -> dict:
    """How to use the College Scorecard tools. READ THIS FIRST: the key, what the codes mean, which flags are empty, where the data dictionary is."""
    return {
        "upstream": f"College Scorecard at {BASE}, the Department of Education's institution data (IPEDS and federal aid records); a free api.data.gov key",
        "key": {"required": True, "on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own api.data.gov key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "workflow": ["scorecard_search by name (contains), state, city, control or predominant degree for the institutions and their ids",
                     "scorecard_school with an id for the record: control, Carnegie and locale codes, accreditor, minority-serving flags, enrollment, Pell rate, race and ethnicity shares, admission rate, cost, completion, earnings"],
        "notes": ["control is public, private nonprofit or private for-profit; predominant_degree the level most degrees are at (bachelor's for the University of Idaho); carnegie codes are the Carnegie Classification's numeric codes (basic 15 is a doctoral university with very high research activity, 16 high research activity, 17 doctoral/professional) and locale a code for city, suburb, town or rural (32 is a distant town); the data dictionary at " + DICTIONARY + " spells every code out.",
                  "minority_serving: historically_black and tribal are reported; hispanic, aanapii, nant, annh and predominantly_black are null for every institution in the current release, so an HSI or AANAPISI check needs the Department's eligibility matrix, not this. A null is 'not reported', never 'no'.",
                  "Shares are percentages of undergraduates; pell_grant_rate_pct is the share receiving a Pell grant, a measure of low-income enrollment that NSF, NIH and USDA eligibility criteria for institutional programs often reference. enrollment is undergraduates; graduate_students is separate.",
                  "latest means the most recent year each measure was reported, which differs by measure; the release is yearly. For a research profile (expenditures, awards) use the NSF, NIH and USAspending servers.",
                  "Cite as 'College Scorecard, U.S. Department of Education' with the institution's link."],
        "link": SITE,
    }


@mcp.tool(name="scorecard_search", annotations=_READ_ONLY)
async def scorecard_search(name: str = "", state: str = "", city: str = "", control: str = "", predominant_degree: str = "", rows: int = ROWS, page: int = 0) -> dict:
    """Institutions in the College Scorecard by name, state, city, control or predominant degree: id, name, place, control, degree levels, enrollment.

    Args:
        name: Words the institution's name contains, e.g. 'Idaho', 'University of Idaho'.
        state: Two-letter state code, e.g. 'ID'.
        city: City name, e.g. 'Moscow'.
        control: public, nonprofit or for-profit; empty for all.
        predominant_degree: certificate, associate, bachelor's or graduate; empty for all.
        rows: Institutions a page, 1-100. Default 20.
        page: Page, 0-based. Default 0.
    """
    params: dict = {"fields": LIST_FIELDS, "per_page": max(1, min(int(rows or ROWS), MAX_ROWS)), "page": max(0, int(page or 0)), "sort": "school.name"}
    if name.strip():
        params["school.name"] = name.strip()
    if state.strip():
        params["school.state"] = state.strip().upper()
    if city.strip():
        params["school.city"] = city.strip()
    if control.strip():
        code = {"public": 1, "nonprofit": 2, "private nonprofit": 2, "for-profit": 3, "private for-profit": 3}.get(control.strip().lower())
        if not code:
            return {"error": "control must be public, nonprofit or for-profit"}
        params["school.ownership"] = code
    if predominant_degree.strip():
        code = {v: k for k, v in DEGREES.items()}.get(predominant_degree.strip().lower().replace("bachelors", "bachelor's"))
        if code is None:
            return {"error": "predominant_degree must be certificate, associate, bachelor's or graduate"}
        params["school.degrees_awarded.predominant"] = code
    if len(params) == 4:
        return {"error": "give at least one of name, state, city, control or predominant_degree"}
    try:
        body = await _get(params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    meta = body.get("metadata") or {}
    rows_out = [slim_row(r) for r in body["results"]]
    out = {"query": {k: v for k, v in params.items() if k.startswith("school.")}, "total": meta.get("total"), "page": params["page"], "returned": len(rows_out), "institutions": rows_out, "link": SITE}
    if isinstance(meta.get("total"), int) and (params["page"] + 1) * params["per_page"] < meta["total"]:
        out["next_page"] = params["page"] + 1
    return out


@mcp.tool(name="scorecard_school", annotations=_READ_ONLY)
async def scorecard_school(id: int) -> dict:
    """One institution's College Scorecard record: control, Carnegie and locale codes, accreditor, minority-serving flags, enrollment and shares, Pell rate, admission rate, cost, completion, earnings.

    Args:
        id: The institution's id (IPEDS unit id), from scorecard_search; 142285 is the University of Idaho.
    """
    try:
        unit = int(id)
    except (TypeError, ValueError):
        return {"error": "id must be the institution's numeric id"}
    try:
        body = await _get({"id": unit, "fields": SCHOOL_FIELDS})
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e), "upstream": BASE}
    if not body["results"]:
        return {"error": f"no institution {unit} in the College Scorecard"}
    out = slim_school(body["results"][0])
    out["dictionary"] = DICTIONARY
    return out


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# An institution id the model names waits on a search that returned it (#40); one a person gives passes as given.
given(mcp, {"scorecard_school": {"id": "scorecard_search"}})
