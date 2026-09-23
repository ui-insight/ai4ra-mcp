"""web_search: the SearXNG answer slimmed to what a model needs, and a clear error when the backend is down."""

import pytest

from ai4ra_mcp.servers.general import server as ai4ra

SEARX = {"query": "deep soil ecotron", "number_of_results": 2,
         "results": [{"title": "Deep Soil Ecotron", "url": "https://www.uidaho.edu/x/ecotron", "content": "A facility...", "engines": ["google", "bing"], "publishedDate": None},
                     {"title": "Award 2131837", "url": "https://www.nsf.gov/awardsearch/showAward?AWD_ID=2131837", "content": "Mid-scale RI-1", "engine": "duckduckgo"}],
         "unresponsive_engines": [["startpage", "CAPTCHA"]], "suggestions": ["ecotron idaho"]}


async def test_web_search_slims_results(monkeypatch):
    async def fake_get_json(url, params=None, headers=None):
        assert url.endswith("/search") and params["format"] == "json" and params["q"] == "deep soil ecotron"
        return SEARX
    monkeypatch.setattr(ai4ra, "get_json", fake_get_json)
    ai4ra._cache._d.clear()
    out = await ai4ra.web_search("deep soil ecotron", count=5)
    assert out["returned"] == 2 and out["results"][0]["url"].endswith("/ecotron")
    assert out["results"][0]["engines"] == ["google", "bing"] and out["results"][1]["engines"] == ["duckduckgo"]
    assert out["engines_not_answering"] == [["startpage", "CAPTCHA"]] and out["suggestions"] == ["ecotron idaho"]


async def test_web_search_reports_backend_down(monkeypatch):
    async def down(url, params=None, headers=None):
        raise ConnectionError("refused")
    monkeypatch.setattr(ai4ra, "get_json", down)
    ai4ra._cache._d.clear()
    out = await ai4ra.web_search("anything")
    assert "unreachable" in out["error"] and "fetch_document" in out["error"]


async def test_web_search_pins_safe_search_and_drops_unsuitable(monkeypatch):
    seen = {}
    async def fake_get_json(url, params=None, headers=None):
        seen.update(params)
        return {"results": [{"title": "Essex County soils", "url": "https://essex.example/soil", "content": "ok", "engines": ["google"]},
                            {"title": "free casino bonus", "url": "https://casino.example/", "content": "x", "engines": ["bing"]},
                            {"title": "fine", "url": "https://example.edu/xxx-tools", "content": "y", "engines": ["bing"]}]}
    monkeypatch.setattr(ai4ra, "get_json", fake_get_json)
    ai4ra._cache._d.clear()
    out = await ai4ra.web_search("essex soils")
    assert seen["safesearch"] == "2"
    assert [r["title"] for r in out["results"]] == ["Essex County soils"] and out["dropped_as_unsuitable"] == 2


async def test_web_search_refuses_a_blocked_query():
    out = await ai4ra.web_search("best casino near campus")
    assert "error" in out


@pytest.mark.parametrize("q,cat", [("", "general"), ("x", "images"), ("x", "recipes")])
async def test_web_search_validates(q, cat):
    out = await ai4ra.web_search(q, category=cat)
    assert "error" in out
