"""fedreg: the Federal Register's shapes slimmed, the query a search sends (repeated keys as pairs), bad input."""

from ai4ra_mcp.servers.fedreg import server as fr

OMB = {"raw_name": "OFFICE OF MANAGEMENT AND BUDGET", "name": "Management and Budget Office", "id": 280,
       "url": "https://www.federalregister.gov/agencies/management-and-budget-office", "parent_id": None, "slug": "management-and-budget-office"}
ROW = {"title": "Guidance for Federal Financial Assistance; Corrections", "document_number": "2024-22520", "type": "Rule", "subtype": None,
       "publication_date": "2024-10-01", "agencies": [OMB],
       "abstract": "The Office of Management and Budget (OMB) is correcting the final guidance that appeared in the Federal Register on April 22, 2024.",
       "html_url": "https://www.federalregister.gov/documents/2024/10/01/2024-22520/guidance-for-federal-financial-assistance-corrections",
       "pdf_url": "https://www.govinfo.gov/content/pkg/FR-2024-10-01/pdf/2024-22520.pdf", "comments_close_on": None, "effective_on": "2024-10-01",
       "docket_ids": [], "regulation_id_numbers": [],
       "cfr_references": [{"chapter": None, "citation_url": None, "part": "170", "title": 2}, {"chapter": None, "citation_url": None, "part": "200", "title": 2}],
       "action": "Final rule; correction and correcting amendments."}
NOFO = {"title": "FAA Contract Tower Competitive Grant Program; Fiscal Year (FY) 2027 Funding Opportunity", "document_number": "2026-19328", "type": "Notice",
        "subtype": None, "publication_date": "2026-09-22", "agencies": [{"name": "Federal Aviation Administration", "slug": "federal-aviation-administration"}],
        "html_url": "https://www.federalregister.gov/documents/2026/09/22/2026-19328/faa-contract-tower", "comments_close_on": "2026-10-19",
        "action": "Notice of funding opportunity.", "docket_ids": ["Docket # FAA-2026-6240"], "cfr_references": []}
DOC = {**ROW, "document_number": "2024-07496", "title": "Guidance for Federal Financial Assistance", "publication_date": "2024-04-22", "citation": "89 FR 30046",
       "dates": "The effective date for the final guidance is October 1, 2024.", "page_length": 163, "significant": None, "comment_url": None,
       "body_html_url": "https://www.federalregister.gov/documents/full_text/html/2024/04/22/2024-07496.html",
       "full_text_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2024/04/22/2024-07496.xml",
       "raw_text_url": "https://www.federalregister.gov/documents/full_text/text/2024/04/22/2024-07496.txt",
       "regulations_dot_gov_info": {"supporting_documents": [], "comments_count": 0, "agency_id": "OMB", "docket_id": "OMB_FRDOC_0001",
                                    "document_id": "OMB_FRDOC_0001-0366", "regulation_id_number": None},
       "topics": ["Administrative practice and procedure", "Colleges and universities", "Grant programs"], "images": {"ER22AP24.805": {}}}
AGENCIES = [OMB | {"short_name": "OMB", "child_ids": [184], "description": "long"},
            {"name": "National Science Foundation", "short_name": "NSF", "slug": "national-science-foundation", "url": "https://www.federalregister.gov/agencies/national-science-foundation", "parent_id": None, "id": 1},
            {"name": "Science and Technology Policy Office", "short_name": "OSTP", "slug": "science-and-technology-policy-office", "url": "", "parent_id": None, "id": 2}]


def test_slim_row_reads_cfr_agencies_and_link():
    r = fr._slim(ROW)
    assert r["document_number"] == "2024-22520" and r["type"] == "Rule" and r["effective_on"] == "2024-10-01" and r["comments_close_on"] is None
    assert r["cfr_references"] == ["2 CFR 170", "2 CFR 200"] and r["agencies"] == [{"name": "Management and Budget Office", "slug": "management-and-budget-office"}]
    assert r["link"] == ROW["html_url"] and r["pdf_url"].endswith("2024-22520.pdf") and r["rins"] == [] and r["docket_ids"] == []
    n = fr._slim(NOFO)
    assert n["comments_close_on"] == "2026-10-19" and n["action"] == "Notice of funding opportunity." and n["docket_ids"] == ["Docket # FAA-2026-6240"]


def test_slim_document_carries_text_links_pages_and_the_regulations_gov_docket():
    d = fr._slim_document(DOC)
    assert d["page_count"] == 163 and d["citation"] == "89 FR 30046" and d["full_text_xml_url"].endswith("2024-07496.xml") and d["body_html_url"].endswith(".html")
    assert d["regulations_gov"] == {"docket_id": "OMB_FRDOC_0001", "document_id": "OMB_FRDOC_0001-0366", "comments_count": 0, "comment_url": None}
    assert d["topics"][1] == "Colleges and universities" and "images" not in d and "abstract" in d


def test_slim_agency():
    a = fr._slim_agency(AGENCIES[0])
    assert a == {"slug": "management-and-budget-office", "name": "Management and Budget Office", "short_name": "OMB",
                 "url": "https://www.federalregister.gov/agencies/management-and-budget-office", "parent_id": None}


async def test_search_sends_repeated_keys_as_pairs(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"], seen["params"] = url, params
        return {"count": 38, "total_pages": 19, "next_page_url": "https://www.federalregister.gov/api/v1/documents?page=2", "results": [ROW]}

    monkeypatch.setattr(fr, "get_json", fake_get_json)
    fr._cache._d.clear()
    out = await fr.federal_register_search(term="uniform guidance", document_types="rule,PRORULE", agencies="management-and-budget-office",
                                           cfr_title="2", cfr_part="200", date_from="2024-01-01", date_to="2024-12-31", significant="1", page=1, per_page=2)
    assert seen["url"].endswith("/documents.json") and isinstance(seen["params"], list)
    p = seen["params"]
    assert ("conditions[term]", "uniform guidance") in p and ("conditions[type][]", "RULE") in p and ("conditions[type][]", "PRORULE") in p
    assert ("conditions[agencies][]", "management-and-budget-office") in p and ("conditions[cfr][title]", "2") in p and ("conditions[cfr][part]", "200") in p
    assert ("conditions[publication_date][gte]", "2024-01-01") in p and ("conditions[publication_date][lte]", "2024-12-31") in p
    assert ("conditions[significant]", "1") in p and ("order", "newest") in p and ("per_page", "2") in p and ("page", "1") in p
    assert [v for k, v in p if k == "fields[]"] == fr.LIST_FIELDS
    assert out["total"] == 38 and out["total_pages"] == 19 and out["next_page"] == 2 and out["returned"] == 1 and out["documents"][0]["document_number"] == "2024-22520"


async def test_search_rejects_bad_input(monkeypatch):
    async def fake_get_json(url, params=None, headers=None):
        raise AssertionError("no request should be made")

    monkeypatch.setattr(fr, "get_json", fake_get_json)
    fr._cache._d.clear()
    assert "at least one" in (await fr.federal_register_search())["error"]
    assert "document_types" in (await fr.federal_register_search(term="x", document_types="FINAL"))["error"]
    assert "cfr_title" in (await fr.federal_register_search(cfr_part="200"))["error"]
    assert "YYYY-MM-DD" in (await fr.federal_register_search(term="x", date_from="01/01/2024"))["error"]
    assert "significant" in (await fr.federal_register_search(term="x", significant="yes"))["error"]
    assert "document_number" in (await fr.federal_register_document("not a number"))["error"]


async def test_document_and_agencies(monkeypatch):
    async def fake_get_json(url, params=None, headers=None):
        return DOC if url.endswith("/documents/2024-07496.json") else AGENCIES

    monkeypatch.setattr(fr, "get_json", fake_get_json)
    fr._cache._d.clear()
    d = await fr.federal_register_document("2024-07496")
    assert d["document_number"] == "2024-07496" and d["page_count"] == 163 and "fetch_document" in d["note"] and "body" not in d
    a = await fr.federal_register_agencies("budget")
    assert [x["slug"] for x in a["agencies"]] == ["management-and-budget-office"]
    a = await fr.federal_register_agencies("nsf")
    assert a["returned"] == 1 and a["agencies"][0]["short_name"] == "NSF"
    assert (await fr.federal_register_agencies())["returned"] == 3


async def test_lists_tools():
    assert {t.name for t in await fr.mcp.list_tools()} == {"federal_register_index", "federal_register_search", "federal_register_document", "federal_register_agencies"}
