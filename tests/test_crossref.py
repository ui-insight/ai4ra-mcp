"""crossref: the API's shapes slimmed, the filter string a search builds, the JATS stripped from an abstract."""

from ai4ra_mcp.servers.crossref import server as cr

WORK = {"DOI": "10.1371/journal.pone.0266781", "type": "journal-article", "publisher": "Public Library of Science (PLoS)", "volume": "17", "issue": "4", "page": "e0266781",
        "is-referenced-by-count": 6, "title": ["6 month serologic response to the Pfizer-BioNTech COVID-19 vaccine among healthcare workers"], "container-title": ["PLOS ONE"],
        "URL": "https://doi.org/10.1371/journal.pone.0266781", "published": {"date-parts": [[2022, 4, 18]]}, "references-count": 9, "ISSN": ["1932-6203"],
        "author": [{"ORCID": "https://orcid.org/0000-0002-4748-3930", "authenticated-orcid": True, "given": "Jason", "family": "Cham", "sequence": "first", "affiliation": []},
                   {"given": "Sandeep", "family": "Pandey", "sequence": "additional", "affiliation": [{"name": "Scripps Research Institute"}]}],
        "funder": [{"DOI": "10.13039/100006108", "name": "National Center for Advancing Translational Sciences", "doi-asserted-by": "publisher", "award": ["UL1TR002550"]}],
        "license": [{"start": {"date-parts": [[2022, 4, 18]]}, "content-version": "vor", "URL": "http://creativecommons.org/licenses/by/4.0/"}],
        "abstract": "<jats:sec id=\"sec001\">\n<jats:title>Aim</jats:title>\n<jats:p>Healthcare workers (HCWs) were among the first group vaccinated.</jats:p></jats:sec>"}
FUNDER = {"id": "100000001", "location": "United States", "name": "National Science Foundation", "alt-names": ["NSF", "US NSF", "USNSF", "U.S. NSF", "US National Science Foundation", "Sixth"],
          "uri": "https://doi.org/10.13039/100000001", "replaces": [], "replaced-by": [], "tokens": ["national", "science", "foundation"]}


def test_slim_work_flattens_title_dates_authors_and_funders():
    w = cr.slim_work(WORK)
    assert w["title"].startswith("6 month") and w["container"] == "PLOS ONE" and w["year"] == 2022 and w["cited_by"] == 6
    assert w["authors"][0] == {"given": "Jason", "family": "Cham", "sequence": "first", "orcid": "https://orcid.org/0000-0002-4748-3930"}
    assert w["authors"][1]["affiliations"] == ["Scripps Research Institute"] and "orcid" not in w["authors"][1] and w["author_count"] == 2
    assert w["funders"] == [{"name": "National Center for Advancing Translational Sciences", "doi": "10.13039/100006108", "awards": ["UL1TR002550"]}]
    assert w["link"] == "https://doi.org/10.1371/journal.pone.0266781" and w["volume"] == "17" and w["page"] == "e0266781"


def test_year_falls_back_to_issued():
    assert cr._year({"issued": {"date-parts": [[2004]]}}) == 2004 and cr._year({"published": {"date-parts": [[None]]}}) is None


def test_slim_funder_has_registry_link_and_five_alt_names():
    f = cr.slim_funder(FUNDER)
    assert f["id"] == "100000001" and f["link"] == "https://doi.org/10.13039/100000001" and len(f["alt_names"]) == 5 and f["location"] == "United States"


async def test_works_search_builds_the_request(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        seen.update(params or {})
        return {"status": "ok", "message": {"total-results": 100, "items": [WORK] * 20}}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_works_search(query="wildfire smoke", author="Sheneman", funder_id="100000001", from_year="2020", to_year="2024", type="journal-article")
    assert seen["url"].endswith("/works") and seen["query"] == "wildfire smoke" and seen["query.author"] == "Sheneman" and seen["mailto"]
    assert seen["filter"] == "funder:100000001,from-pub-date:2020,until-pub-date:2024,type:journal-article" and seen["select"].startswith("DOI,title,author")
    assert seen["rows"] == 20 and seen["offset"] == 0 and out["returned"] == 20 and out["total"] == 100 and out["next_offset"] == 20
    cr._cache._d.clear()
    seen.clear()
    await cr.crossref_works_search(funder_id="https://doi.org/10.13039/100000001", rows=500)
    assert seen["filter"] == "funder:100000001" and seen["rows"] == 50 and "query" not in seen


async def test_work_strips_jats_and_validates_doi(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        return {"status": "ok", "message": WORK}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_work("https://doi.org/10.1371/journal.pone.0266781")
    assert seen["url"].endswith("/works/10.1371/journal.pone.0266781")
    assert out["abstract"] == "Aim Healthcare workers (HCWs) were among the first group vaccinated." and out["licenses"] == ["http://creativecommons.org/licenses/by/4.0/"]
    assert out["references_count"] == 9 and out["issn"] == ["1932-6203"]
    assert "error" in await cr.crossref_work("journal.pone.0266781")
    assert "error" in await cr.crossref_works_search(from_year="2020")
    assert "error" in await cr.crossref_works_search(query="x", funder_id="NSF")
    assert "error" in await cr.crossref_funders_search("")


async def test_funders_search(monkeypatch):
    async def fake_get_json(url, params=None, headers=None):
        assert url.endswith("/funders") and params["query"] == "National Science Foundation"
        return {"status": "ok", "message": {"total-results": 61, "items": [FUNDER]}}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_funders_search("National Science Foundation")
    assert out["total"] == 61 and out["funders"][0]["name"] == "National Science Foundation"


async def test_lists_tools():
    assert {t.name for t in await cr.mcp.list_tools()} == {"crossref_index", "crossref_works_search", "crossref_work", "crossref_funders_search"}
