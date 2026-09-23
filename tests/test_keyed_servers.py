"""Offline checks for the four upstream servers: the slimming of each upstream's record shape, the
missing-key answer when no key is configured, and the bearer token that overrides the environment."""

import json

import pytest
from starlette.testclient import TestClient

from ai4ra_mcp.app import build_app
from ai4ra_mcp.common import http as h
from ai4ra_mcp.servers.fac import server as fac
from ai4ra_mcp.servers.nih import server as nih
from ai4ra_mcp.servers.nsf import server as nsf
from ai4ra_mcp.servers.sam import server as sam

NIH_PROJECT = {
    "appl_id": 10748490, "project_num": "1I01HX003627-01A2", "core_project_num": "I01HX003627", "project_title": "Shared decision making",
    "fiscal_year": 2024, "award_amount": 250000, "project_start_date": "2023-10-01T00:00:00", "project_end_date": "2026-09-30T00:00:00",
    "agency_ic_admin": {"code": "VA", "abbreviation": "VA", "name": "Veterans Affairs"}, "activity_code": "I01", "is_active": False,
    "organization": {"org_name": "EDITH NOURSE ROGERS MEMORIAL VETERANS HOSPITAL", "org_city": "BEDFORD", "org_state": "MA", "primary_uei": "DFAKNKKAN2T1"},
    "principal_investigators": [{"full_name": "Marla L. Clayman", "is_contact_pi": True}, {"full_name": "Jason L Vassy", "is_contact_pi": False}],
    "program_officers": [], "project_detail_url": "https://reporter.nih.gov/project-details/10748490",
}
NSF_AWARD = {"id": "2425033", "title": "EPSCoR Graduate Fellowship", "awardeeName": "University of Montana", "awardeeStateCode": "MT", "pdPIName": "Jane Smith",
             "date": "08/15/2024", "startDate": "09/01/2024", "expDate": "08/31/2027", "fundsObligatedAmt": "1200000", "primaryProgram": "EPSCoR", "fundProgramDir": "OD"}
SAM_ENTITY = {"entityRegistration": {"ueiSAM": "RV56IG5JM6G9", "legalBusinessName": "REGENTS OF THE UNIVERSITY OF IDAHO", "cageCode": "1ABC2",
                                     "registrationStatus": "Active", "registrationDate": "2024-05-01", "registrationExpirationDate": "2025-05-01", "exclusionStatusFlag": "N",
                                     "purposeOfRegistrationDesc": "All Awards"},
              "coreData": {"entityInformation": {"entityURL": "https://www.uidaho.edu", "fiscalYearEndCloseDate": "06/30"},
                           "physicalAddress": {"addressLine1": "875 Perimeter Dr", "city": "Moscow", "stateOrProvinceCode": "ID", "zipCode": "83844", "countryCode": "USA"},
                           "generalInformation": {"entityStructureDesc": "State Government", "entityTypeDesc": "Business or Organization"},
                           "businessTypes": {"businessTypeList": [{"businessTypeDesc": "Public Institution of Higher Education"}]}}}
SAM_EXCLUSION = {"exclusionDetails": {"classificationType": "Firm", "exclusionType": "Ineligible (Proceedings Completed)", "exclusionProgram": "Reciprocal",
                                      "excludingAgencyName": "Department of Health and Human Services", "excludingAgencyCode": "HHS"},
                 "exclusionIdentification": {"ueiSAM": "ABC123DEF456", "entityName": "ACME RESEARCH LLC"},
                 "exclusionActions": {"listOfActions": [{"activateDate": "2024-01-15", "terminationDate": "Indefinite", "recordStatus": "Active", "updateDate": "2024-01-16"}]},
                 "exclusionPrimaryAddress": {"city": "Boise", "stateOrProvinceCode": "ID", "countryCode": "USA"}, "exclusionOtherInformation": {"ctCode": None}}
SAM_LISTING = {"assistanceListingId": "47.070", "title": "Computer and Information Science and Engineering", "status": "Active", "fiscalYear": 2025,
               "federalOrganization": {"department": "National Science Foundation", "agency": "National Science Foundation"},
               "overview": {"objective": "To support research", "assistanceListingDescription": "Long text"},
               "compliance": {"CFR200Requirements": {"questions": [{"code": "subpartB", "isSelected": True}, {"code": "subpartC", "isSelected": False}], "description": "2 CFR 200 applies"},
                              "formulaAndMatching": {"types": {"matching": False}, "matching": {"percent": None, "description": "No matching"}}},
               "criteriaForApplying": {"applicant": {"types": [{"code": "ET25010", "name": "Public institution of higher education"}], "description": "Universities"}},
               "contacts": {"headquarters": [{"fullName": "A Person", "email": "a@nsf.gov", "phone": "703-292-0000"}]}}
FAC_GENERAL = {"report_id": "2023-06-GSAFAC-0000012345", "audit_year": "2023", "auditee_name": "UNIVERSITY OF IDAHO", "auditee_uei": "RV56IG5JM6G9",
               "fy_start_date": "2022-07-01", "fy_end_date": "2023-06-30", "auditor_firm_name": "Moss Adams LLP", "gaap_results": "unmodified_opinion",
               "is_going_concern_included": False, "is_internal_control_material_weakness_disclosed": False, "is_low_risk_auditee": True,
               "total_amount_expended": 123456789, "agencies_with_prior_findings": ["47"]}
FAC_FINDING = {"reference_number": "2023-001", "award_reference": "AWARD-0001", "type_requirement": "B", "is_material_weakness": False,
               "is_significant_deficiency": True, "is_questioned_costs": True, "is_repeat_finding": False, "prior_finding_ref_numbers": None}
FAC_AWARD = {"award_reference": "AWARD-0001", "federal_agency_prefix": "47", "federal_award_extension": "070", "federal_program_name": "CISE",
             "amount_expended": 5000000, "is_direct": True, "is_major": True, "audit_report_type": "U", "findings_count": 1}


def test_nih_slim_project():
    p = nih._slim_project(NIH_PROJECT)
    assert p["project_num"] == "1I01HX003627-01A2" and p["project_start"] == "2023-10-01" and p["agency"] == "VA"
    assert p["organization"]["uei"] == "DFAKNKKAN2T1"
    assert [i["name"] for i in p["principal_investigators"] if i["contact_pi"]] == ["Marla L. Clayman"]
    assert p["link"].endswith("/10748490")


def test_nsf_slim_award():
    a = nsf._slim(NSF_AWARD)
    assert a["id"] == "2425033" and a["obligated_amount"] == "1200000" and a["directorate"] == "OD"
    assert a["link"] == "https://www.nsf.gov/awardsearch/showAward?AWD_ID=2425033"


def test_sam_slim_records():
    e = sam.slim_entity(SAM_ENTITY)
    assert e["uei"] == "RV56IG5JM6G9" and e["registration_status"] == "Active" and e["address"]["state"] == "ID"
    assert e["business_types"] == ["Public Institution of Higher Education"] and e["link"] == "https://sam.gov/entity/RV56IG5JM6G9/coreData"
    x = sam.slim_exclusion(SAM_EXCLUSION)
    assert x["name"] == "ACME RESEARCH LLC" and x["excluding_agency_code"] == "HHS" and x["activation_date"] == "2024-01-15"
    assert "sfm%5BexclusionName%5D=ACME" in x["link"] or "ACME" in x["link"]
    short = sam.slim_listing(SAM_LISTING)
    assert short["assistance_listing"] == "47.070" and "description" not in short and short["link"] == "https://sam.gov/fal/47.070/view"
    full = sam.slim_listing(SAM_LISTING, full=True)
    assert full["cfr_200_subparts_applied"] == ["subpartB"] and full["applicant_types"] == ["Public institution of higher education"]
    assert full["matching"]["required"] is False and full["contacts"][0]["email"] == "a@nsf.gov"


def test_fac_slim_records():
    g = fac.slim_audit(FAC_GENERAL)
    assert g["report_id"] == "2023-06-GSAFAC-0000012345" and g["flags"]["low_risk_auditee"] is True and g["fiscal_year"]["end"] == "2023-06-30"
    assert g["link"] == "https://app.fac.gov/dissemination/summary/2023-06-GSAFAC-0000012345"
    f = fac.slim_finding(FAC_FINDING, "The finding text")
    assert f["reference"] == "2023-001" and f["questioned_costs"] is True and f["text"] == "The finding text"
    a = fac.slim_award(FAC_AWARD)
    assert a["assistance_listing"] == "47.070" and a["major_program"] is True


@pytest.mark.parametrize("tool,args", [
    (sam.sam_entity, {"uei": "RV56IG5JM6G9"}), (sam.sam_exclusions_search, {"name": "Acme"}), (sam.sam_assistance_listing, {"number": "47.070"}),
    (sam.sam_assistance_listings_search, {}), (fac.fac_audits_search, {"uei": "RV56IG5JM6G9"}), (fac.fac_findings, {"report_id": "x"}), (fac.fac_federal_awards, {"report_id": "x"}),
])
async def test_keyed_tool_without_key_says_so(monkeypatch, tool, args):
    monkeypatch.delenv("AI4RA_MCP_SAM_KEY", raising=False)
    monkeypatch.delenv("AI4RA_MCP_FAC_KEY", raising=False)
    out = await tool(**args)
    assert "no API key" in out["error"]


def test_api_key_prefers_request_bearer(monkeypatch):
    monkeypatch.setenv("AI4RA_MCP_FAC_KEY", "env-key")
    assert h.api_key("AI4RA_MCP_FAC_KEY") == "env-key"
    token = h.request_key.set("user-key")
    try:
        assert h.api_key("AI4RA_MCP_FAC_KEY") == "user-key"
    finally:
        h.request_key.reset(token)
    assert h.api_key("AI4RA_MCP_FAC_KEY") == "env-key"


def test_bearer_middleware_reaches_the_tool(monkeypatch):
    """A bearer token on the HTTP request is the key the fac tool uses; the environment has none."""
    monkeypatch.delenv("AI4RA_MCP_FAC_KEY", raising=False)
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["key"] = (headers or {}).get("X-Api-Key")
        return [FAC_GENERAL]

    monkeypatch.setattr(fac, "get_json", fake_get_json)
    fac._cache._d.clear()
    with TestClient(build_app(["fac"])) as client:
        rpc = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "fac_audits_search", "arguments": {"uei": "RV56IG5JM6G9"}}}
        hdr = {"Accept": "application/json, text/event-stream"}
        r = client.post("/fac/mcp", json=rpc, headers={**hdr, "Authorization": "Bearer user-key"})
        assert r.status_code == 200
        text = r.json()["result"]["content"][0]["text"]
        assert json.loads(text)["returned"] == 1 and seen["key"] == "user-key"
        r = client.post("/fac/mcp", json={**rpc, "id": 2}, headers=hdr)
        assert "no API key" in r.json()["result"]["content"][0]["text"]


async def test_nsf_awardee_is_sent_as_a_phrase(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, **kw):
        seen.update(params or {})
        return {"response": {"award": [NSF_AWARD]}}

    monkeypatch.setattr(nsf, "get_json", fake_get_json)
    nsf._cache._d.clear()
    await nsf.nsf_awards_search(awardee="Canisius University")
    assert seen["awardeeName"] == '"Canisius University"'
    nsf._cache._d.clear()
    await nsf.nsf_awards_search(awardee="Canisius", pi_name="Andrew Stewart")
    assert seen["awardeeName"] == "Canisius" and seen["pdPIName"] == "Andrew Stewart"

