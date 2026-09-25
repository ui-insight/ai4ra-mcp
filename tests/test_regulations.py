"""regulations: Regulations.gov's JSON:API shapes slimmed, the filters a search sends with the key as a header,
bad input, and the missing-key answer."""

import pytest

from ai4ra_mcp.servers.regulations import server as rg

DOC_ROW = {"type": "documents", "id": "NHTSA-2013-0009-0263",
           "attributes": {"agencyId": "NHTSA", "objectId": "09000064b95b6ab9", "frDocNum": "2026-19403", "documentType": "Rule", "withdrawn": False,
                          "highlightedContent": "", "commentEndDate": None, "commentStartDate": "2026-09-23T04:00:00Z", "lastModifiedDate": "2026-09-23T16:49:11Z",
                          "openForComment": False, "withinCommentPeriod": False, "postedDate": "2026-09-23T04:00:00Z",
                          "title": "Amendment to the Uniform Procedures for State Highway Safety Grant Programs", "docketId": "NHTSA-2013-0009",
                          "subtype": "Final Rule", "allowLateComments": False}}
DOC_FULL = {"id": "OMB-2023-0001-0001", "type": "documents", "links": {"self": "https://api.regulations.gov/v4/documents/OMB-2023-0001-0001"},
            "attributes": {"additionalRins": None, "allowLateComments": False, "cfrPart": None, "commentEndDate": "2023-04-28T03:59:59Z",
                           "commentStartDate": "2023-01-27T05:00:00Z", "effectiveDate": None, "frDocNum": "2023-01635", "agencyId": "OMB",
                           "docAbstract": None, "docketId": "OMB-2023-0001", "documentType": "Notice",
                           "fileFormats": [{"fileUrl": "https://downloads.regulations.gov/OMB-2023-0001-0001/content.pdf", "format": "pdf", "size": 564297},
                                           {"fileUrl": "https://downloads.regulations.gov/OMB-2023-0001-0001/content.htm", "format": "htm", "size": 49836}],
                           "objectId": "09000064856107a5", "modifyDate": "2023-05-06T01:00:51Z", "originalDocumentId": "OMB_FRDOC_0001-0325", "pageCount": 10,
                           "postedDate": "2023-01-27T05:00:00Z", "subtype": None, "title": "Initial Proposals for Updating Race and Ethnicity Statistical Standards",
                           "topics": None, "withdrawn": False, "withinCommentPeriod": False, "openForComment": False}}
DOCKET = {"id": "OMB-2023-0001", "type": "dockets",
          "attributes": {"keywords": None, "modifyDate": "2024-03-28T09:11:23Z", "dkAbstract": "By this Notice, the Office of Management and Budget (OMB) is announcing revisions to Statistical Policy Directive No. 15.",
                         "agencyId": "OMB", "program": None, "title": "Updates to OMB's Race and Ethnicity Statistical Standards", "docketType": "Nonrulemaking",
                         "rin": None, "effectiveDate": None, "objectId": "0b000064855fbcef"}}
COMMENT = {"id": "OMB-2023-0001-9540", "type": "comments",
           "attributes": {"agencyId": "OMB", "objectId": "090000648589dc2a", "documentType": "Public Submission", "withdrawn": False, "highlightedContent": "",
                          "postedDate": "2023-03-31T04:00:00Z", "lastModifiedDate": "2023-03-31T14:45:24Z", "title": "Comment from Hussein Sobh"}}
META = {"hasNextPage": True, "hasPreviousPage": False, "numberOfElements": 1, "pageNumber": 1, "pageSize": 5, "totalElements": 5301, "totalPages": 40}


def test_slim_document_rows():
    d = rg.slim_document(DOC_ROW)
    assert d["document_id"] == "NHTSA-2013-0009-0263" and d["document_type"] == "Rule" and d["fr_doc_num"] == "2026-19403" and d["object_id"] == "09000064b95b6ab9"
    assert d["open_for_comment"] is False and d["docket_id"] == "NHTSA-2013-0009" and d["link"] == "https://www.regulations.gov/document/NHTSA-2013-0009-0263"
    f = rg.slim_document_full(DOC_FULL)
    assert f["page_count"] == 10 and f["comment_end_date"] == "2023-04-28T03:59:59Z" and f["rins"] == [] and f["comment_link"] is None
    assert f["files"] == [{"format": "pdf", "url": "https://downloads.regulations.gov/OMB-2023-0001-0001/content.pdf", "size": 564297},
                          {"format": "htm", "url": "https://downloads.regulations.gov/OMB-2023-0001-0001/content.htm", "size": 49836}]
    assert f["fr_doc_num"] == "2023-01635" and "highlightedContent" not in f


def test_slim_docket_and_comment():
    k = rg.slim_docket(DOCKET)
    assert k["docket_id"] == "OMB-2023-0001" and k["docket_type"] == "Nonrulemaking" and k["agency_id"] == "OMB" and k["rin"] is None
    assert k["link"] == "https://www.regulations.gov/docket/OMB-2023-0001" and k["abstract"].startswith("By this Notice")
    c = rg.slim_comment(COMMENT)
    assert c["comment_id"] == "OMB-2023-0001-9540" and c["title"] == "Comment from Hussein Sobh" and c["posted_date"] == "2023-03-31T04:00:00Z"
    assert c["link"] == "https://www.regulations.gov/comment/OMB-2023-0001-9540"


@pytest.fixture
def upstream(monkeypatch):
    monkeypatch.setenv(rg.KEY_ENV, "test-key")
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"], seen["params"], seen["headers"] = url, params, headers
        if url.endswith("/documents"):
            return {"data": [DOC_ROW], "meta": META}
        if url.endswith("/comments"):
            return {"data": [COMMENT], "meta": {**META, "hasNextPage": False, "totalElements": 1, "totalPages": 1}}
        if "/dockets/" in url:
            return {"data": DOCKET}
        return {"data": DOC_FULL}

    monkeypatch.setattr(rg, "get_json", fake_get_json)
    rg._cache._d.clear()
    return seen


async def test_documents_search_sends_filters_and_the_key_header(upstream):
    out = await rg.regulations_gov_documents_search(term="uniform guidance", document_type="proposed rule", agency="omb", docket_id="OMB-2023-0001",
                                                    posted_from="2024-01-01", posted_to="2026-12-31", comment_open_only=True, page=2, page_size=3)
    p = upstream["params"]
    assert upstream["url"] == "https://api.regulations.gov/v4/documents" and upstream["headers"] == {"X-Api-Key": "test-key"}
    assert p["filter[searchTerm]"] == "uniform guidance" and p["filter[documentType]"] == "Proposed Rule" and p["filter[agencyId]"] == "OMB"
    assert p["filter[docketId]"] == "OMB-2023-0001" and p["filter[postedDate][ge]"] == "2024-01-01" and p["filter[postedDate][le]"] == "2026-12-31"
    assert len(p["filter[commentEndDate][ge]"]) == 10 and p["sort"] == "-postedDate"
    assert p["page[size]"] == "5" and p["page[number]"] == "2"
    assert out["total"] == 5301 and out["next_page"] == 3 and out["returned"] == 1 and out["documents"][0]["document_id"] == "NHTSA-2013-0009-0263"


async def test_comments_search_filters_by_object_id(upstream):
    out = await rg.regulations_gov_comments_search(document_object_id="09000064856107a5", page_size=500)
    p = upstream["params"]
    assert p["filter[commentOnId]"] == "09000064856107a5" and p["page[size]"] == "250" and "filter[docketId]" not in p
    assert out["returned"] == 1 and "next_page" not in out and out["comments"][0]["comment_id"] == "OMB-2023-0001-9540"
    await rg.regulations_gov_comments_search(docket_id="OMB-2023-0001", term="race")
    assert upstream["params"]["filter[docketId]"] == "OMB-2023-0001" and upstream["params"]["filter[searchTerm]"] == "race"


async def test_document_and_docket(upstream):
    d = await rg.regulations_gov_document("OMB-2023-0001-0001")
    assert upstream["url"].endswith("/documents/OMB-2023-0001-0001") and d["fr_doc_num"] == "2023-01635" and d["files"][0]["format"] == "pdf" and "fedreg" in d["note"]
    k = await rg.regulations_gov_docket("OMB-2023-0001")
    assert upstream["url"].endswith("/dockets/OMB-2023-0001") and k["docket_type"] == "Nonrulemaking"


async def test_bad_input(upstream):
    assert "at least one" in (await rg.regulations_gov_documents_search())["error"]
    assert "document_type" in (await rg.regulations_gov_documents_search(term="x", document_type="Final Rule"))["error"]
    assert "YYYY-MM-DD" in (await rg.regulations_gov_documents_search(term="x", posted_from="1/1/2024"))["error"]
    assert "object_id" in (await rg.regulations_gov_comments_search(document_object_id="OMB-2023-0001-0001"))["error"]
    assert "at least one" in (await rg.regulations_gov_comments_search())["error"]
    assert "docket_id" in (await rg.regulations_gov_docket(""))["error"]
    assert "document_id" in (await rg.regulations_gov_document("a b"))["error"]
    assert "url" not in upstream


@pytest.mark.parametrize("tool,args", [
    (rg.regulations_gov_documents_search, {"term": "x"}), (rg.regulations_gov_document, {"document_id": "OMB-2023-0001-0001"}),
    (rg.regulations_gov_docket, {"docket_id": "OMB-2023-0001"}), (rg.regulations_gov_comments_search, {"docket_id": "OMB-2023-0001"}),
])
async def test_without_key_says_so(monkeypatch, tool, args):
    monkeypatch.delenv(rg.KEY_ENV, raising=False)
    rg._cache._d.clear()
    out = await tool(**args)
    assert "no API key" in out["error"]


async def test_index_reports_the_key(monkeypatch):
    monkeypatch.delenv(rg.KEY_ENV, raising=False)
    assert (await rg.regulations_gov_index())["key"]["on_this_request"] is False
    monkeypatch.setenv(rg.KEY_ENV, "k")
    assert (await rg.regulations_gov_index())["key"]["on_this_request"] is True


async def test_lists_tools():
    assert {t.name for t in await rg.mcp.list_tools()} == {"regulations_gov_index", "regulations_gov_documents_search", "regulations_gov_document",
                                                          "regulations_gov_docket", "regulations_gov_comments_search"}
