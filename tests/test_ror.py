"""ror: a ROR v2 record slimmed, the search's query and filter, the affiliation match's shape, and id handling."""

from ai4ra_mcp.servers.ror import server as ror

UI = {"admin": {"created": {"date": "2018-11-14"}, "last_modified": {"date": "2024-12-11", "schema_version": "2.1"}},
      "domains": ["uidaho.edu"], "established": 1889,
      "external_ids": [{"all": ["100012326"], "preferred": "100012326", "type": "fundref"}, {"all": ["grid.266456.5"], "preferred": "grid.266456.5", "type": "grid"},
                       {"all": ["0000 0001 2284 9900"], "preferred": None, "type": "isni"}, {"all": ["Q1854488"], "preferred": None, "type": "wikidata"}],
      "id": "https://ror.org/03hbp5t65",
      "links": [{"type": "website", "value": "https://uidaho.edu"}, {"type": "wikipedia", "value": "http://en.wikipedia.org/wiki/University_of_Idaho"}],
      "locations": [{"geonames_details": {"continent_code": "NA", "country_code": "US", "country_name": "United States", "country_subdivision_code": "ID",
                                          "country_subdivision_name": "Idaho", "lat": 46.73239, "lng": -117.00017, "name": "Moscow"}, "geonames_id": 5601538}],
      "names": [{"lang": None, "types": ["acronym"], "value": "UI"}, {"lang": "es", "types": ["label"], "value": "Universidad de Idaho"},
                {"lang": "en", "types": ["ror_display", "label"], "value": "University of Idaho"}],
      "relationships": [{"label": "Idaho Space Grant Consortium", "type": "child", "id": "https://ror.org/05b1jpg49"},
                        {"label": "Rocky Mountain Advanced Computing Consortium", "type": "related", "id": "https://ror.org/019q0z051"}],
      "status": "active", "types": ["education", "funder"]}
SEARCH = {"number_of_results": 46, "time_taken": 18, "items": [UI], "meta": {"types": [], "countries": [], "continents": [], "statuses": []}}
AFFILIATION = {"number_of_results": 2, "items": [{"organization": UI, "score": 1.0, "chosen": True, "substring": "Dept of Biology, University of Idaho, Moscow ID", "matching_type": "EXACT"},
                                                  {"organization": {**UI, "id": "https://ror.org/04zn7jb34"}, "score": 0.75, "chosen": False, "matching_type": "COMMON TERMS"}]}


def test_slim_organization():
    o = ror.slim_organization(UI)
    assert o["id"] == "https://ror.org/03hbp5t65" and o["name"] == "University of Idaho" and o["acronyms"] == ["UI"] and o["labels"] == ["Universidad de Idaho"]
    assert o["country"] == "US" and o["region"] == "Idaho" and o["city"] == "Moscow" and o["established"] == 1889 and o["types"] == ["education", "funder"]
    assert o["external_ids"]["fundref"]["preferred"] == "100012326" and o["external_ids"]["isni"]["preferred"] == "0000 0001 2284 9900"
    assert o["website"] == "https://uidaho.edu" and o["relationships"][0] == {"type": "child", "name": "Idaho Space Grant Consortium", "id": "https://ror.org/05b1jpg49"}
    assert o["status"] == "active" and o["last_modified"] == "2024-12-11" and o["link"] == o["id"]


async def test_search_sends_query_and_filter(monkeypatch):
    ror._cache._d.clear()
    sent = {}

    async def fake_get(url, params=None, headers=None):
        sent.update(url=url, params=params)
        return SEARCH

    monkeypatch.setattr(ror, "get_json", fake_get)
    out = await ror.ror_search("University of Idaho", country="us", type="Education", page=2)
    assert sent["url"] == ror.BASE and sent["params"] == {"query": "University of Idaho", "filter": "country.country_code:US,types:education", "page": 2}
    assert out["total"] == 46 and out["page"] == 2 and out["next_page"] == 3 and out["organizations"][0]["name"] == "University of Idaho"


async def test_affiliation_match(monkeypatch):
    ror._cache._d.clear()
    sent = {}

    async def fake_get(url, params=None, headers=None):
        sent.update(params=params)
        return AFFILIATION

    monkeypatch.setattr(ror, "get_json", fake_get)
    out = await ror.ror_search("Dept of Biology, University of Idaho, Moscow ID", affiliation=True, country="US")
    assert sent["params"] == {"affiliation": "Dept of Biology, University of Idaho, Moscow ID"}
    assert out["chosen"] == "https://ror.org/03hbp5t65" and out["matches"][0]["chosen"] is True and out["matches"][1]["score"] == 0.75 and out["note"] is None


async def test_search_validates():
    assert "error" in await ror.ror_search("")
    assert "type must" in (await ror.ror_search("x", type="school"))["error"]


async def test_organization_accepts_url_or_bare_id(monkeypatch):
    ror._cache._d.clear()
    urls = []

    async def fake_get(url, params=None, headers=None):
        urls.append(url)
        return UI

    monkeypatch.setattr(ror, "get_json", fake_get)
    assert (await ror.ror_organization("https://ror.org/03hbp5t65"))["name"] == "University of Idaho"
    assert (await ror.ror_organization("03HBP5T65"))["name"] == "University of Idaho"
    assert urls == [ror.BASE + "/03hbp5t65"] and len(urls) == 1
    assert "error" in await ror.ror_organization("00000zzzz") and "error" in await ror.ror_organization("")


async def test_lists_tools():
    assert {t.name for t in await ror.mcp.list_tools()} == {"ror_index", "ror_search", "ror_organization"}
