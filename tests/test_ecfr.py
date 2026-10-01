"""ecfr: the query a search sends when it is limited to a title and part (the eCFR's hierarchy filter), the scope kept in the result, bad input."""

import json

from ai4ra_mcp.servers.ecfr import server as ecfr

HIT = {"type": "Section", "hierarchy": {"title": "2", "subtitle": "A", "chapter": "II", "part": "200", "subpart": "E", "section": "200.430"},
       "headings": {"title": "Federal Financial Assistance", "part": "Uniform Administrative Requirements, Cost Principles, and Audit Requirements for Federal Awards",
                    "subpart": "Cost Principles", "section": "<strong>Compensation</strong>—personal services."},
       "score": 15.88, "starts_on": "2024-10-01", "ends_on": None, "reserved": False, "removed": False, "change_types": ["effective"],
       "full_text_excerpt": "<strong>Compensation</strong> for personal services includes all remuneration"}
META = {"current_page": 1, "total_pages": 3, "total_count": 15, "max_score": 15.88,
        "description": "Changes to sections matching 'compensation' in Title 2 :: Part 200"}


def _capture(monkeypatch):
    seen = {}

    async def fake_api_get(endpoint, params=None, **kwargs):
        seen["endpoint"], seen["params"] = endpoint, params
        return {"results": [HIT], "meta": META}

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    return seen


async def test_search_limited_to_a_title_and_part_sends_the_hierarchy_filter(monkeypatch):
    seen = _capture(monkeypatch)
    out = json.loads(await ecfr.ecfr_search(query="compensation", title=2, part="200", date="2024-10-01"))
    p = seen["params"]
    assert seen["endpoint"] == "search/v1/results.json" and p["query"] == "compensation" and p["date"] == "2024-10-01"
    assert p["hierarchy[title]"] == 2 and p["hierarchy[part]"] == "200"
    assert "hierarchy[subpart]" not in p and "hierarchy[section]" not in p and "agency_slugs[]" not in p
    assert out["meta"]["description"].endswith("in Title 2 :: Part 200") and out["meta"]["total_count"] == 15
    assert out["results"][0]["citation"] == "2 CFR § 200.430" and "full_text_excerpt" not in out["results"][0]


async def test_search_takes_subpart_and_section_and_keeps_the_agency_filter(monkeypatch):
    seen = _capture(monkeypatch)
    await ecfr.ecfr_search(query="compensation", title=2, part="200", subpart="E")
    assert seen["params"]["hierarchy[subpart]"] == "E" and "hierarchy[section]" not in seen["params"]
    await ecfr.ecfr_search(query="fringe", title=2, section="200.431")
    assert seen["params"]["hierarchy[section]"] == "200.431" and "hierarchy[part]" not in seen["params"]
    await ecfr.ecfr_search(query="period of performance", agency_slugs=["management-and-budget-office"])
    assert seen["params"]["agency_slugs[]"] == ["management-and-budget-office"]
    assert not [k for k in seen["params"] if k.startswith("hierarchy[")]


async def test_search_rejects_a_part_without_a_title_and_a_subpart_without_a_part(monkeypatch):
    async def fake_api_get(endpoint, params=None, **kwargs):
        raise AssertionError("no request should be made")

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    for kwargs in ({"part": "200"}, {"subpart": "E"}, {"section": "200.430"}):
        assert "require title" in json.loads(await ecfr.ecfr_search(query="compensation", **kwargs))["error"]["message"]
    assert json.loads(await ecfr.ecfr_search(query="compensation", title=2, subpart="E"))["error"]["message"] == "subpart requires part"


async def test_search_description_names_the_title_and_part_for_the_uniform_guidance_not_an_agency_slug():
    tool = next(t for t in await ecfr.mcp.list_tools() if t.name == "ecfr_search")
    props = tool.input_schema["properties"]
    assert {"title", "part", "subpart", "section"} <= set(props)
    assert 'title=2, part="200"' in tool.description and "rule in force needs date" in tool.description
    assert "office-of-management-and-budget" not in tool.description + json.dumps(props)
