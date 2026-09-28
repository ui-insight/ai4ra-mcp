"""Offline checks for the four upstream servers: the slimming of each upstream's record shape, the
missing-key answer when no key is configured, and the bearer token that overrides the environment."""

import json

import pytest
from starlette.testclient import TestClient

from ai4ra_mcp.app import build_app
from ai4ra_mcp.common import http as h
from ai4ra_mcp.servers.fac import server as fac
from ai4ra_mcp.servers.nih import server as nih
from ai4ra_mcp.servers.lakehouse import server as lakehouse
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
    (lakehouse.lakehouse_streams, {}), (lakehouse.lakehouse_schema, {"stream": "s"}), (lakehouse.lakehouse_query, {"stream": "s", "table": "t"}),
    (lakehouse.lakehouse_files, {"stream": "s"}), (lakehouse.lakehouse_file, {"stream": "s", "hash": "h"}),
])
async def test_keyed_tool_without_key_says_so(monkeypatch, tool, args):
    monkeypatch.delenv("AI4RA_MCP_SAM_KEY", raising=False)
    monkeypatch.delenv("AI4RA_MCP_FAC_KEY", raising=False)
    monkeypatch.delenv("AI4RA_MCP_LAKEHOUSE_SECRET", raising=False)
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


def test_lakehouse_rows_are_capped_by_count_and_size():
    result = {"columns": ["a", "b"], "rows": [{"a": i, "b": "x"} for i in range(1000)], "rowCount": 1000}
    out = lakehouse.slim_rows("t", result, 300)
    assert out["returned"] == 300 and out["row_count"] == 1000 and out["truncated"] is True and out["columns"] == ["a", "b"]
    big = {"columns": ["a"], "rows": [{"a": "y" * 20000} for _ in range(10)], "rowCount": 10}
    out = lakehouse.slim_rows("t", big, 10)
    assert out["returned"] == 1 and out["truncated"] is True


async def test_lakehouse_token_is_minted_once_and_sent_as_bearer(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, status, body=None, content=b"{}", headers=None):
            self.status_code, self._body, self.content, self.headers, self.text = status, body, content, headers or {}, ""
        def json(self): return self._body

    class Client:
        def __init__(self, **kw): self.headers = kw.get("headers") or {}
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, auth=None, data=None):
            calls.append(("token", auth, data)); return Resp(200, {"access_token": "tok-1", "expires_in": 3600}, b"x")
        async def request(self, method, url, params=None, json=None):
            calls.append((method, url, self.headers.get("Authorization"), params, json)); return Resp(200, {"client_id": "mr-365", "querying": ["q"], "submitting": []}, b"x")

    monkeypatch.setattr(lakehouse.httpx, "AsyncClient", Client)
    lakehouse._tokens.clear()
    monkeypatch.setenv("AI4RA_MCP_LAKEHOUSE_SECRET", "s3")
    out = await lakehouse.lakehouse_streams()
    out2 = await lakehouse.lakehouse_streams()
    assert out["querying"] == ["q"] and out2["querying"] == ["q"]
    assert calls[0] == ("token", (lakehouse.CLIENT_ID, "s3"), {"grant_type": "client_credentials"})
    assert sum(1 for c in calls if c[0] == "token") == 1
    assert calls[1][2] == "Bearer tok-1" and calls[1][1].endswith("/streams")


async def test_lakehouse_query_validates_and_builds_the_request(monkeypatch):
    sent = {}

    async def fake_call(method, path, params=None, payload=None, raw=False):
        sent.update(payload); return {"awards": {"rows": [{"a": 1}], "columns": ["a"], "rowCount": 1, "totalCount": 9}}

    monkeypatch.setattr(lakehouse, "_call", fake_call)
    out = await lakehouse.lakehouse_query("s", "awards", limit=5, filters={"fiscal_year": {"gte": 2023}}, offset=0,
                                          group_by=["status"], aggregate=[{"fn": "count", "column": "*", "alias": "n"}])
    assert out["total_count"] == 9 and out["rows"] == [{"a": 1}]
    assert sent["tables"][0] == {"table": "awards", "limit": 5, "filters": {"fiscal_year": {"gte": 2023}}, "offset": 0, "group_by": ["status"],
                                 "aggregate": [{"fn": "COUNT", "column": "*", "alias": "n"}]}
    bad = await lakehouse.lakehouse_query("s", "awards", filters={"x": {"between": [1, 2]}})
    assert "unknown filter operator" in bad["error"]
    bad = await lakehouse.lakehouse_query("s", "awards", group_by=["status"], aggregate=[{"fn": "count_non_null", "column": "x"}])
    assert "count_non_null" in bad["error"] and "lakehouse_sql" in bad["error"]


@pytest.mark.asyncio
async def test_lakehouse_query_aggregate_without_group_by_is_one_sql_statement(monkeypatch):
    """The skill promises that COUNT on * counts every row; the tool refused an aggregate with no group_by. Now it runs the
    totals as one SELECT through Marina's SQL gateway, the filters as its WHERE, and one row comes back."""
    ran = {}

    async def fake_sql(client, sql, budget_s=None):
        ran["sql"] = sql; return {"columns": ["cnt", "total"], "types": ["bigint", "double"], "rows": [[42, 7.5]], "row_count": 1, "truncated": False, "state": "FINISHED", "elapsed_ms": 3}

    async def no_rest(*a, **k):
        raise AssertionError("/query must not be called for an ungrouped aggregate")

    monkeypatch.setattr(lakehouse, "_sql", fake_sql)
    monkeypatch.setattr(lakehouse, "_call", no_rest)
    out = await lakehouse.lakehouse_query("subaward", "docs", filters={"fiscal_year": {"gte": 2023}, "status": "Active", "title": {"ilike": "%o'brien%"}, "kind": {"in": ["a", "b"]}, "ended": {"is_null": True}},
                                          aggregate=[{"fn": "count", "column": "*", "alias": "cnt"}, {"fn": "SUM", "column": "amount", "alias": "total"}])
    assert out["rows"] == [[42, 7.5]] and out["columns"] == ["cnt", "total"] and out["returned"] == 1 and out["table"] == "docs"
    assert ran["sql"] == ('SELECT COUNT(*) AS "cnt", SUM("amount") AS "total" FROM lakehouse."client_mr-365__subaward"."docs" WHERE '
                          '"fiscal_year" >= 2023 AND "status" = \'Active\' AND lower(CAST("title" AS varchar)) LIKE lower(\'%o\'\'brien%\') AND "kind" IN (\'a\', \'b\') AND "ended" IS NULL')
    assert out["sql_run"] == ran["sql"]
    plain = await lakehouse.lakehouse_query("subaward", "docs", aggregate=[{"fn": "COUNT", "column": "*"}])
    assert ran["sql"] == 'SELECT COUNT(*) AS "count_all" FROM lakehouse."client_mr-365__subaward"."docs"' and plain["returned"] == 1


@pytest.mark.asyncio
async def test_lakehouse_query_aggregate_is_typed_in_the_schema():
    """The aggregate item's keys and the five functions are in the published input schema, not only in the prose:
    a small model sent {function, on, as} and had only the docstring to correct it from."""
    srv, _ = lakehouse.make_server("lakehouse", "mr-365", "AI4RA_MCP_LAKEHOUSE_SECRET")
    tool = [t for t in await srv.list_tools() if t.name == "lakehouse_query"][0]
    item = tool.input_schema["$defs"]["Aggregate"]
    assert set(item["properties"]) == {"fn", "column", "alias"} and item["required"] == ["fn", "column"]
    assert "COUNT, SUM, AVG, MIN, MAX" in item["properties"]["fn"]["description"]



def test_lakehouse_second_client_names():
    """A second configured client is mounted at lakehouse-<id> with its own secret variable (the names need `re`)."""
    assert lakehouse.mount_name(0, "mr-365") == "lakehouse" and lakehouse.key_env(0, "mr-365") == "AI4RA_MCP_LAKEHOUSE_SECRET"
    assert lakehouse.mount_name(1, "OSP Reports") == "lakehouse-osp-reports"
    assert lakehouse.key_env(1, "OSP Reports") == "AI4RA_MCP_LAKEHOUSE_SECRET_OSP_REPORTS"


def test_lakehouse_stream_names_read_marinas_key():
    """Marina lists a querying stream as {stream_name, enabled, table_count}: the overview read only name/stream and came back empty."""
    assert lakehouse._stream_names({"querying": [{"stream_name": "subaward", "enabled": True}, "awards", {"name": "x"}]}) == ["subaward", "awards", "x"]


def test_lakehouse_like_is_sql_like_on_names():
    assert lakehouse._like("%doc%", "veras_sample__post_award_subrecip_doc")
    assert lakehouse._like("doc", "veras_sample__post_award_subrecip_DOC")
    assert lakehouse._like("veras_sample__post_award%", "veras_sample__post_award_subrecip")
    assert not lakehouse._like("veras_sample__post_award%", "veras_sample__a_post_award_subrecip")
    assert not lakehouse._like("%animal%", "veras_sample__post_award_subrecip_doc")


SCHEMA = {"tables": [
    {"name": "veras_sample__post_award_subrecip_doc", "row_count": 1303, "columns": []},
    {"name": "veras_sample__a_animal_document", "row_count": None, "columns": [{"name": "pk_index", "type": "integer"}, {"name": "title", "type": "varchar"}]},
    {"name": "veras_sample__a_animal", "row_count": None, "columns": [{"name": "pk_index", "type": "integer"}]},
    {"name": "_stats", "row_count": None, "columns": []},
]}


def _fake_marina(monkeypatch, calls):
    async def fake_call(client, method, path, params=None, payload=None, raw=False):
        calls.append((method, path, params, payload))
        if path == "/streams":
            return {"client_id": "mr-365", "querying": [{"stream_name": "subaward", "enabled": True, "table_count": 3}], "submitting": []}
        if path == "/query/schema":
            return SCHEMA
        if path == "/query":
            t = payload["tables"][0]["table"]
            return {t: {"columns": ["doc_id", "title", "file_name"], "rows": [{"doc_id": 1, "title": "t", "file_name": "f"}], "rowCount": 1}}
        raise AssertionError(path)
    monkeypatch.setattr(lakehouse, "_call", fake_call)


@pytest.mark.asyncio
async def test_lakehouse_catalog_overview_lists_marinas_streams(monkeypatch):
    calls = []
    _fake_marina(monkeypatch, calls)
    out = await lakehouse.lakehouse_sql_catalog()
    assert [s["stream"] for s in out["streams"]] == ["subaward"]
    st = out["streams"][0]
    assert st["tables"] == 3 and st["measured"] == 1 and st["unmeasured"] == 2
    assert st["rows"] is None and st["rows_measured"] == 1303   # the sum of one measured table is not the stream's size
    assert out["largest_tables"][0]["rows"] == 1303 and "rows_measured" in out["note"] and "_stats" in out["note"]


@pytest.mark.asyncio
async def test_lakehouse_catalog_table_layer_reads_one_row_when_marina_has_no_columns(monkeypatch):
    """The six tables Marina has counted come with no columns; the catalog names them from one row rather than answering with nothing."""
    calls = []
    _fake_marina(monkeypatch, calls)
    out = await lakehouse.lakehouse_sql_catalog("subaward", "veras_sample__post_award_subrecip_doc")
    assert [c["name"] for c in out["columns"]] == ["doc_id", "title", "file_name"]
    assert out["row_count"] == 1303 and out["stats_source"] is None and "not profiled" in out["note"]
    assert calls[-1][1] == "/query" and calls[-1][3] == {"stream": "subaward", "tables": [{"table": "veras_sample__post_award_subrecip_doc", "limit": 1}]}
    # a table Marina did profile is answered from the schema alone
    calls.clear()
    out = await lakehouse.lakehouse_sql_catalog("subaward", "veras_sample__a_animal_document")
    assert [c["name"] for c in out["columns"]] == ["pk_index", "title"] and "note" not in out
    assert all(c[1] != "/query" for c in calls)


@pytest.mark.asyncio
async def test_lakehouse_catalog_stream_layer_narrows_by_like(monkeypatch):
    calls = []
    _fake_marina(monkeypatch, calls)
    out = await lakehouse.lakehouse_sql_catalog("subaward", like="%doc%")
    assert [t["table"] for t in out["tables"]] == ["veras_sample__post_award_subrecip_doc", "veras_sample__a_animal_document"]
    assert out["table_count"] == 2 and out["stream_table_count"] == 3 and out["like"] == "%doc%"
    out = await lakehouse.lakehouse_sql_catalog("subaward")
    assert out["table_count"] == 3 and "like" not in out
