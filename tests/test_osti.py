"""osti: the record shape slimmed, the search parameters and the X-Total-Count header, and bad input."""

from ai4ra_mcp.servers.osti import server as o

RECORD = {"language": "English", "entry_date": "2026-08-21T14:41:02Z", "report_number": "INL/JOU-24-76155-Rev000", "identifier": "AC07-05ID14517; EE0008256; EE0008910",
          "journal_issue": "50", "nondoe_contract_number": "IN1016152", "country_publication": "United States", "publisher": "American Chemical Society (ACS)",
          "journal_type": "AM", "doi": "10.1021/acssuschemeng.3c04222", "description": "Aqueous extractives are minor and non-structural compounds in biomass...",
          "title": "Understanding the Influence of Water-Soluble Compounds from Unpretreated Corn Stover Pellets on Enzymatic Hydrolysis of Cellulose",
          "contract_number": "AC07-05ID14517; EE0008256; EE0008910", "publication_date": "2023-12-04T00:00:00Z", "journal_volume": "11", "osti_id": "2282731",
          "journal_name": "ACS Sustainable Chemistry & Engineering", "product_type": "Journal Article",
          "authors": [f"Author {i} [Purdue University, West Lafayette, IN (United States)]" for i in range(12)],
          "subjects": ["09 BIOMASS FUELS", "Cellulose", "Corn Stover"], "article_type": "Accepted Manuscript", "format": "p. 17616-17624",
          "doe_contract_number": "AC07-05ID14517; EE0008256; EE0008910", "doe_funded_flag": True,
          "sponsor_orgs": ["USDA", "USDOE Office of Energy Efficiency and Renewable Energy (EERE)"],
          "research_orgs": ["Idaho National Laboratory (INL), Idaho Falls, ID (United States)", "Purdue University, West Lafayette, IN (United States)"],
          "links": [{"rel": "citation", "href": "https://www.osti.gov/biblio/2282731"}, {"rel": "fulltext", "href": "https://www.osti.gov/servlets/purl/2282731"},
                    {"rel": "citation_doe_pages", "href": "https://www.osti.gov/pages/biblio/2282731"}]}
REPORT = {"osti_id": "1914346", "title": "A report", "authors": ["Lee, A"], "publication_date": "2023-01-20T00:00:00Z", "product_type": "Technical Report",
          "doe_contract_number": "SC0019327", "links": [{"rel": "citation", "href": "https://www.osti.gov/biblio/1914346"}]}


def test_record_slims_contracts_links_and_journal():
    r = o._slim_record(RECORD)
    assert r["osti_id"] == "2282731" and r["publication_date"] == "2023-12-04" and r["doi"] == "10.1021/acssuschemeng.3c04222"
    assert r["doe_contract_numbers"] == ["AC07-05ID14517", "EE0008256", "EE0008910"] and r["other_contract_numbers"] == ["IN1016152"]
    assert len(r["authors"]) == 10 and r["author_count"] == 12 and r["article_type"] == "Accepted Manuscript"
    assert r["journal"] == {"name": "ACS Sustainable Chemistry & Engineering", "volume": "11", "issue": "50", "pages": "p. 17616-17624"}
    assert r["links"] == {"citation": "https://www.osti.gov/biblio/2282731", "fulltext": "https://www.osti.gov/servlets/purl/2282731"}
    assert r["link"] == "https://www.osti.gov/biblio/2282731" and "description" not in r
    t = o._slim_record(REPORT)
    assert t["journal"] is None and t["links"]["fulltext"] is None and t["doe_contract_numbers"] == ["SC0019327"]


async def test_search_sends_osti_params_and_reads_the_count_header(monkeypatch):
    seen = {}

    async def fake_get(path, params):
        seen["path"], seen["params"] = path, dict(params)
        return [RECORD, REPORT], {"x-total-count": "26", "content-type": "application/json"}

    monkeypatch.setattr(o, "_get", fake_get)
    o._cache._d.clear()
    out = await o.osti_search(doe_contract="DE-SC0019327", research_org="University of Idaho", from_date="01/01/2020", product_type="Journal Article", page=2, rows=500)
    assert seen["path"] == "/records"
    assert seen["params"] == {"doe_contract_number": "SC0019327", "research_org": "University of Idaho", "publication_date_start": "01/01/2020",
                              "product_type": "Journal Article", "page": 2, "rows": 50}
    assert out["total"] == 26 and out["returned"] == 2 and out["page"] == 2 and "next_page" not in out
    o._cache._d.clear()
    out = await o.osti_search(query="soil carbon", rows=2)
    assert seen["params"]["q"] == "soil carbon" and out["next_page"] == 2


async def test_record_takes_a_list_or_a_dict(monkeypatch):
    async def fake_get(path, params):
        assert path == "/records/2282731"
        return [RECORD], {}

    monkeypatch.setattr(o, "_get", fake_get)
    o._cache._d.clear()
    r = await o.osti_record("2282731")
    assert r["abstract"].startswith("Aqueous") and r["subjects"] == ["09 BIOMASS FUELS", "Cellulose", "Corn Stover"] and r["availability"] is None
    assert r["entry_date"] == "2026-08-21" and r["link"] == "https://www.osti.gov/biblio/2282731"

    async def fake_dict(path, params):
        return RECORD, {}

    monkeypatch.setattr(o, "_get", fake_dict)
    o._cache._d.clear()
    assert (await o.osti_record("2282731"))["osti_id"] == "2282731"


async def test_upstream_errors_and_bad_input(monkeypatch):
    async def dropped(path, params):
        raise ValueError("www.osti.gov dropped the connection (RemoteProtocolError); OSTI rate-limits aggressively, wait a minute before retrying")

    monkeypatch.setattr(o, "_get", dropped)
    o._cache._d.clear()
    assert "wait a minute" in (await o.osti_search(query="x"))["error"]
    assert "error" in await o.osti_search()
    assert "error" in await o.osti_search(from_date="2020-01-01")
    assert "MM/DD/YYYY" in (await o.osti_search(query="x", to_date="2020-01-01"))["error"]
    assert "error" in await o.osti_record("abc")


async def test_lists_tools():
    assert {t.name for t in await o.mcp.list_tools()} == {"osti_index", "osti_search", "osti_record"}
