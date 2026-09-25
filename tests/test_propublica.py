"""propublica: Nonprofit Explorer's shapes slimmed, the search's parameters, and the not-found answer."""

from ai4ra_mcp.servers.propublica import server as pp

SEARCH_ORG = {"ein": 852713318, "strein": "85-2713318", "name": "Imagine Idaho Foundation", "sub_name": "Imagine Idaho Foundation", "city": "Ketchum", "state": "ID",
              "ntee_code": "W80", "raw_ntee_code": "W80", "subseccd": 3, "has_subseccd": True, "have_filings": None, "score": 64.92153}
SEARCH = {"total_results": 138, "num_pages": 6, "cur_page": 0, "page_offset": 0, "per_page": 25, "search_query": "idaho foundation", "selected_state": "ID",
          "organizations": [SEARCH_ORG], "api_version": 2}
ORG = {"id": 142007220, "ein": 142007220, "name": "Pro Publica Inc", "careofname": None, "address": "155 AVE AMERICA 13 FL", "city": "New York", "state": "NY",
       "zipcode": "10036-2711", "subsection_code": 3, "ruling_date": "2008-02-01", "tax_period": "2024-12-01", "ntee_code": "A20", "data_source": "current_2026_09_16"}
FILING_2023 = {"tax_prd": 202312, "tax_prd_yr": 2023, "formtype": 0, "pdf_url": "https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F142007220_202312_990.pdf",
               "totrevenue": 57970562, "totfuncexpns": 44080009, "totassetsend": 85514123, "totliabend": 10080757, "totnetassetend": 75433366, "totcntrbgfts": 55857720, "subseccd": 3}
FILING_2022 = {**FILING_2023, "tax_prd": 202212, "tax_prd_yr": 2022, "totrevenue": 40000000}
RECORD = {"organization": ORG, "filings_with_data": [FILING_2022, FILING_2023],
          "filings_without_data": [{"tax_prd": 201012, "tax_prd_yr": 2010, "formtype": 0, "formtype_str": "990", "pdf_url": "x"}], "api_version": 2}


def test_slim_search_org():
    o = pp.slim_search_org(SEARCH_ORG)
    assert o["ein"] == 852713318 and o["ein_formatted"] == "85-2713318" and o["subsection"].startswith("501(c)(3)") and o["ntee_code"] == "W80"
    assert o["link"] == "https://projects.propublica.org/nonprofits/organizations/852713318"


def test_slim_organization_and_filing():
    o = pp.slim_organization(ORG)
    assert o["ein_formatted"] == "14-2007220" and o["subsection"] == "501(c)(3) charitable, educational, religious or scientific" and o["ruling_date"] == "2008-02-01"
    assert o["latest_tax_period"] == "2024-12-01" and o["link"].endswith("/142007220")
    f = pp.slim_filing(FILING_2023)
    assert f["tax_year"] == 2023 and f["form"] == "990" and f["total_revenue"] == 57970562 and f["total_expenses"] == 44080009 and f["net_assets_end"] == 75433366
    assert pp._subsection(92).startswith("4947(a)(1)") and pp._subsection(4) == "501(c)(4) social welfare organization" and pp._subsection(None) is None
    assert pp._strein(42103594) == "04-2103594"


async def test_search_sends_bracket_params(monkeypatch):
    pp._cache._d.clear()
    sent = {}

    async def fake_get(url, params=None, headers=None):
        sent.update(url=url, params=params)
        return SEARCH

    monkeypatch.setattr(pp, "get_json", fake_get)
    out = await pp.propublica_nonprofit_search("idaho foundation", state="id", ntee_category="2", subsection="3", page=0)
    assert sent["url"].endswith("/search.json") and sent["params"] == {"q": "idaho foundation", "page": 0, "state[id]": "ID", "ntee[id]": 2, "c_code[id]": 3}
    assert out["total"] == 138 and out["num_pages"] == 6 and out["next_page"] == 1 and out["organizations"][0]["name"] == "Imagine Idaho Foundation"


async def test_search_validates():
    assert "error" in await pp.propublica_nonprofit_search("")
    assert "ntee_category" in (await pp.propublica_nonprofit_search("x", ntee_category="99"))["error"]
    assert "subsection" in (await pp.propublica_nonprofit_search("x", subsection="c3"))["error"]


async def test_organization_newest_first_and_not_found(monkeypatch):
    pp._cache._d.clear()
    sent = {}

    async def fake_get(url, params=None, headers=None):
        sent["url"] = url
        if url.endswith("/123.json"):
            raise ValueError("404 from " + url + ": nothing at that address")
        return RECORD

    monkeypatch.setattr(pp, "get_json", fake_get)
    out = await pp.propublica_nonprofit_organization("14-2007220")
    assert sent["url"].endswith("/organizations/142007220.json")
    assert [f["tax_year"] for f in out["filings"]] == [2023, 2022] and out["filings_with_data_count"] == 2 and out["filings_without_data"] == [2010]
    assert out["name"] == "Pro Publica Inc" and out["note"] is None
    missing = await pp.propublica_nonprofit_organization("123")
    assert "no organization with EIN 123" in missing["error"]
    assert "error" in await pp.propublica_nonprofit_organization("")


async def test_lists_tools():
    assert {t.name for t in await pp.mcp.list_tools()} == {"propublica_nonprofit_index", "propublica_nonprofit_search", "propublica_nonprofit_organization"}
