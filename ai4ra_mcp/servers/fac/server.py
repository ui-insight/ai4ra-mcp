"""fac: the Federal Audit Clearinghouse, single audits under 2 CFR 200 Subpart F.

Upstream: https://api.fac.gov (PostgREST). A free api.data.gov key, from AI4RA_MCP_FAC_KEY or the
client's bearer token, sent as X-Api-Key. Filters are PostgREST operators: eq., ilike.*x*, order=.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_FAC_KEY"
KEY_HOW = "A free key comes from the FAC API signup at https://www.fac.gov/api/ (api.data.gov, an email address is all it asks). Or send your own key as a bearer token."
BASE = "https://api.fac.gov"
GENERAL_FIELDS = ["report_id", "audit_year", "auditee_name", "auditee_uei", "auditee_ein", "auditee_city", "auditee_state", "fy_start_date", "fy_end_date",
                  "audit_type", "audit_period_covered", "auditor_firm_name", "cognizant_agency", "oversight_agency", "gaap_results",
                  "is_going_concern_included", "is_internal_control_material_weakness_disclosed", "is_internal_control_deficiency_disclosed",
                  "is_material_noncompliance_disclosed", "is_low_risk_auditee", "dollar_threshold", "total_amount_expended", "fac_accepted_date",
                  "agencies_with_prior_findings"]
_cache = TTLCache()

mcp = MCPServer(
    "fac",
    instructions="Federal Audit Clearinghouse: an entity's single audits by name, UEI or EIN and year; the findings of one audit; its schedule of federal awards. Needs a free api.data.gov key. Read fac_index first.",
)


async def _get(path: str, params: dict) -> list:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    cache_key = path + "?" + repr(sorted(params.items()))
    body = await _cache.remember(cache_key, DAY, lambda: get_json(f"{BASE}/{path}", params, {"X-Api-Key": key}))
    return body if isinstance(body, list) else []


def slim_audit(g: dict) -> dict:
    rid = g.get("report_id")
    return {
        "report_id": rid, "audit_year": g.get("audit_year"), "auditee": g.get("auditee_name"), "uei": g.get("auditee_uei"), "ein": g.get("auditee_ein"),
        "city": g.get("auditee_city"), "state": g.get("auditee_state"),
        "fiscal_year": {"start": g.get("fy_start_date"), "end": g.get("fy_end_date")}, "audit_type": g.get("audit_type"), "period_covered": g.get("audit_period_covered"),
        "auditor": g.get("auditor_firm_name"), "cognizant_agency": g.get("cognizant_agency"), "oversight_agency": g.get("oversight_agency"),
        "financial_statement_opinion": g.get("gaap_results"),
        "flags": {"going_concern": g.get("is_going_concern_included"), "material_weakness": g.get("is_internal_control_material_weakness_disclosed"),
                  "significant_deficiency": g.get("is_internal_control_deficiency_disclosed"), "material_noncompliance": g.get("is_material_noncompliance_disclosed"),
                  "low_risk_auditee": g.get("is_low_risk_auditee")},
        "dollar_threshold": g.get("dollar_threshold"), "total_federal_expended": g.get("total_amount_expended"),
        "agencies_with_prior_findings": g.get("agencies_with_prior_findings"), "accepted": g.get("fac_accepted_date"),
        "link": f"https://app.fac.gov/dissemination/summary/{rid}" if rid else None,
    }


def slim_finding(f: dict, text: str | None = None) -> dict:
    return {
        "reference": f.get("reference_number"), "award_reference": f.get("award_reference"), "compliance_requirement": f.get("type_requirement"),
        "modified_opinion": f.get("is_modified_opinion"), "other_matters": f.get("is_other_matters"), "material_weakness": f.get("is_material_weakness"),
        "significant_deficiency": f.get("is_significant_deficiency"), "other_findings": f.get("is_other_findings"),
        "questioned_costs": f.get("is_questioned_costs"), "repeat_finding": f.get("is_repeat_finding"), "prior_finding_references": f.get("prior_finding_ref_numbers"),
        "text": text,
    }


def slim_award(a: dict) -> dict:
    prefix, ext = a.get("federal_agency_prefix"), a.get("federal_award_extension")
    return {
        "award_reference": a.get("award_reference"), "assistance_listing": f"{prefix}.{ext}" if prefix and ext else None,
        "program": a.get("federal_program_name"), "cluster": a.get("cluster_name"), "amount_expended": a.get("amount_expended"),
        "direct": a.get("is_direct"), "passthrough": a.get("is_passthrough_award"), "passthrough_amount": a.get("passthrough_amount"),
        "major_program": a.get("is_major"), "audit_report_type": a.get("audit_report_type"), "findings_count": a.get("findings_count"),
    }


@mcp.tool(name="fac_index", annotations=_READ_ONLY)
async def fac_index() -> dict:
    """How to use the Federal Audit Clearinghouse tools. READ THIS FIRST: the key, the workflow, what the flags mean."""
    return {
        "upstream": "https://api.fac.gov (PostgREST over the public single-audit data)",
        "key": {"configured": api_key(KEY_ENV) is not None, "env": KEY_ENV, "how": KEY_HOW},
        "workflow": ["fac_audits_search by auditee name, UEI or EIN, newest first; note the report_id",
                     "fac_findings for that report: each finding with its compliance requirement, flags and text",
                     "fac_federal_awards for that report: the schedule of expenditures by program, with findings counts"],
        "notes": ["A single audit is required of a non-federal entity that expends $1,000,000 or more in federal awards in a year ($750,000 before FY2025); an entity with no audit may be below the threshold, not delinquent.",
                  "flags: material_weakness and material_noncompliance on the audit, questioned_costs and repeat_finding on a finding, are what a subrecipient risk assessment under 2 CFR 200.332 looks at.",
                  "low_risk_auditee True means the auditor judged the entity low risk under 2 CFR 200.520.",
                  "Cite the report link and the audit year; audits are filed months after the fiscal year ends."],
    }


@mcp.tool(name="fac_audits_search", annotations=_READ_ONLY)
async def fac_audits_search(name: str = "", uei: str = "", ein: str = "", audit_year: str = "", state: str = "", limit: int = 25) -> dict:
    """Single audits filed with the Federal Audit Clearinghouse, newest fiscal year first.

    Give one of name, uei or ein. Returns each audit with its report id, fiscal year, auditor, opinion, flags,
    total federal expenditure and a link.

    Args:
        name: Auditee name, partial (e.g. 'University of Idaho').
        uei: The auditee's Unique Entity ID.
        ein: The auditee's EIN, digits only.
        audit_year: One audit year, e.g. '2024'; empty for all.
        state: Two-letter state to narrow a name search.
        limit: Audits to return, 1-100. Default 25.
    """
    params: dict = {"select": ",".join(GENERAL_FIELDS), "order": "fy_end_date.desc", "limit": max(1, min(int(limit or 25), 100))}
    if uei.strip():
        params["auditee_uei"] = "eq." + uei.strip().upper()
    elif ein.strip():
        params["auditee_ein"] = "eq." + "".join(ch for ch in ein if ch.isdigit())
    elif name.strip():
        params["auditee_name"] = "ilike.*" + name.strip().replace("*", "") + "*"
    else:
        return {"error": "give one of name, uei or ein"}
    if audit_year.strip():
        params["audit_year"] = "eq." + audit_year.strip()
    if state.strip():
        params["auditee_state"] = "eq." + state.strip().upper()
    try:
        rows = await _get("general", params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    audits = [slim_audit(g) for g in rows]
    return {"returned": len(audits), "audits": audits,
            "note": "Newest first. No rows means no single audit is on file for these terms; the entity may be below the expenditure threshold."}


@mcp.tool(name="fac_findings", annotations=_READ_ONLY)
async def fac_findings(report_id: str) -> dict:
    """The audit findings of one single audit, with each finding's compliance requirement, flags and text.

    Args:
        report_id: The report id from fac_audits_search, e.g. '2023-06-GSAFAC-0000012345'.
    """
    rid = (report_id or "").strip()
    if not rid:
        return {"error": "report_id is required"}
    try:
        findings = await _get("findings", {"report_id": "eq." + rid, "order": "reference_number.asc"})
        texts = await _get("findings_text", {"report_id": "eq." + rid, "select": "finding_ref_number,finding_text"})
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    by_ref = {t.get("finding_ref_number"): t.get("finding_text") for t in texts}
    out = [slim_finding(f, by_ref.get(f.get("reference_number"))) for f in findings]
    return {"report_id": rid, "findings_count": len(out), "findings": out, "link": f"https://app.fac.gov/dissemination/summary/{rid}",
            "note": "No findings means the auditor reported none for this audit." if not out else None}


@mcp.tool(name="fac_federal_awards", annotations=_READ_ONLY)
async def fac_federal_awards(report_id: str, agency_prefix: str = "") -> dict:
    """The schedule of expenditures of federal awards for one single audit: each program with its Assistance Listing
    number, amount expended, whether direct or passthrough, whether major, and its findings count.

    Args:
        report_id: The report id from fac_audits_search.
        agency_prefix: Two-digit federal agency prefix to narrow, e.g. '47' NSF, '93' HHS, '10' USDA. Empty for all.
    """
    rid = (report_id or "").strip()
    if not rid:
        return {"error": "report_id is required"}
    params = {"report_id": "eq." + rid, "order": "amount_expended.desc"}
    if agency_prefix.strip():
        params["federal_agency_prefix"] = "eq." + agency_prefix.strip()
    try:
        rows = await _get("federal_awards", params)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    awards = [slim_award(a) for a in rows]
    return {"report_id": rid, "returned": len(awards), "total_expended": sum(a.get("amount_expended") or 0 for a in rows),
            "awards": awards, "link": f"https://app.fac.gov/dissemination/summary/{rid}"}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
