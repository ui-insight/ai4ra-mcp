"""ecfr: the query a search sends when it is limited to a title and part (the eCFR's hierarchy filter), the scope kept
in the result, the date used when none is given (the latest day the eCFR holds, never the clock's), a long section
as its outline and a part read by its offsets, a long section with no subheadings paged, bad input."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from ai4ra_mcp.servers.ecfr import server as ecfr

HIT = {"type": "Section", "hierarchy": {"title": "2", "subtitle": "A", "chapter": "II", "part": "200", "subpart": "E", "section": "200.430"},
       "headings": {"title": "Federal Financial Assistance", "part": "Uniform Administrative Requirements, Cost Principles, and Audit Requirements for Federal Awards",
                    "subpart": "Cost Principles", "section": "<strong>Compensation</strong>—personal services."},
       "score": 15.88, "starts_on": "2024-10-01", "ends_on": None, "reserved": False, "removed": False, "change_types": ["effective"],
       "full_text_excerpt": "<strong>Compensation</strong> for personal services includes all remuneration"}
META = {"current_page": 1, "total_pages": 3, "total_count": 15, "max_score": 15.88,
        "description": "Changes to sections matching 'compensation' in Title 2 :: Part 200"}


# The eCFR two days behind the calendar, and Title 2 a day behind the rest: what its titles list looks like on such a day.
TITLES = {"titles": [{"number": 1, "name": "General Provisions", "up_to_date_as_of": "2026-09-29", "reserved": False},
                     {"number": 2, "name": "Federal Financial Assistance", "latest_amended_on": "2026-08-17", "up_to_date_as_of": "2026-09-28", "reserved": False},
                     {"number": 35, "name": "Reserved", "up_to_date_as_of": None, "reserved": True}],
          "meta": {"date": "2026-09-29", "import_in_progress": False}}
SECTION = '<DIV8 N="200.431" TYPE="SECTION"><HEAD>§ 200.431 Compensation—fringe benefits.</HEAD><P>(a) <I>General.</I> Fringe benefits are allowances and services.</P></DIV8>'


def _capture(monkeypatch):
    """Stands in for the eCFR: the titles list, a section's XML, one search hit. Records the last call that was not for the titles list."""
    seen: dict = {"calls": []}

    async def fake_api_get(endpoint, params=None, **kwargs):
        seen["calls"].append(endpoint)
        if endpoint == "versioner/v1/titles.json":
            return TITLES
        seen["endpoint"], seen["params"] = endpoint, params
        return SECTION if endpoint.endswith(".xml") else {"results": [HIT], "meta": META}

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    monkeypatch.setattr(ecfr, "_titles_cache", None)
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


async def test_a_search_with_no_date_is_of_the_current_text_and_all_is_every_version(monkeypatch):
    seen = _capture(monkeypatch)
    out = json.loads(await ecfr.ecfr_search(query="compensation", title=2, part="200"))
    assert seen["params"]["date"] == "2026-09-28" and out["date"] == "2026-09-28"   # the title's day
    out = json.loads(await ecfr.ecfr_search(query="compensation"))
    assert seen["params"]["date"] == "2026-09-29" and out["date"] == "2026-09-29"   # no title: the whole eCFR's day
    out = json.loads(await ecfr.ecfr_search(query="compensation", title=2, part="200", date="all"))
    assert "date" not in seen["params"] and out["date"] == "all"
    out = json.loads(await ecfr.ecfr_search(query="compensation", title=2, part="200", date="2024-10-01"))
    assert seen["params"]["date"] == "2024-10-01" and out["date"] == "2024-10-01"
    assert seen["calls"].count("versioner/v1/titles.json") == 1   # read once, then kept


async def test_a_fetch_with_no_date_reads_the_latest_day_the_ecfr_holds(monkeypatch):
    seen = _capture(monkeypatch)
    out = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.431"))
    assert seen["endpoint"] == "versioner/v1/full/2026-09-28/title-2.xml" and seen["params"] == {"part": "200", "section": "200.431"}
    assert out["date"] == "2026-09-28" and "Fringe benefits are allowances" in out["text"]
    out = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.431", date="2023-03-10"))
    assert seen["endpoint"] == "versioner/v1/full/2023-03-10/title-2.xml" and out["date"] == "2023-03-10"
    out = json.loads(await ecfr.ecfr_compare_regulations(date_1="2024-09-30", title=2, part="200", section="200.431"))
    assert out["date_1"] == "2024-09-30" and out["date_2"] == "2026-09-28" and out["identical"]
    out = json.loads(await ecfr.ecfr_get_title_structure(title=1, depth=1))
    assert seen["endpoint"] == "versioner/v1/structure/2026-09-29/title-1.json" and out["date"] == "2026-09-29"


async def test_a_date_past_the_latest_day_or_malformed_is_refused_in_words_a_client_receives(monkeypatch):
    seen = _capture(monkeypatch)
    for call in (ecfr.ecfr_get_regulation(title=2, part="200", section="200.431", date="2026-09-29"),
                 ecfr.ecfr_search(query="compensation", title=2, part="200", date="2026-10-01"),
                 ecfr.ecfr_compare_regulations(date_1="2024-09-30", date_2="2026-10-01", title=2, part="200", section="200.431")):
        with pytest.raises(ToolError, match=r"past the latest day the eCFR holds for Title 2 \(2026-09-28\)"):
            await call
    with pytest.raises(ToolError, match="date must be YYYY-MM-DD"):
        await ecfr.ecfr_get_regulation(title=2, part="200", section="200.431", date="10/01/2024")
    assert set(seen["calls"]) == {"versioner/v1/titles.json"}   # nothing was asked of the eCFR but its latest day
    # A ToolError's message is what a client is sent; any other exception arrives as "Error executing tool" alone.
    with pytest.raises(ToolError, match="Omit date for the current text") as refused:
        await ecfr.mcp.call_tool("ecfr_get_regulation", {"title": 2, "part": "200", "section": "200.431", "date": "2026-10-01"})
    assert not isinstance(refused.value, UnexpectedToolError)


def _section(number, paragraphs):
    return f'<DIV8 N="{number}" TYPE="SECTION"><HEAD>§ {number} A long section.</HEAD>' + "".join(f"<P>{p}</P>" for p in paragraphs) + "</DIV8>"


FILL = "Costs must be necessary and reasonable for the performance of the Federal award. " * 9   # 729 characters
LONG = {   # sections longer than one window: one with the regulation's own subheadings, one with none, and an appendix
    "200.1": _section("200.1", ["The following definitions apply:"] + [f"<I>{term}</I> means {FILL}" for term in ("Acquisition cost", "Budget", "Modified Total Direct Cost (MTDC)", "Subaward")]
                      + [f"(1) {FILL}"] + [f"<I>Term {n}</I> means {FILL}" for n in range(14)]),
    "50.605": _section("50.605", [f"({letter}) {FILL}" for letter in "abcdefghijklmnopqrst"]),
}


async def test_a_long_section_comes_back_as_its_outline_and_a_part_is_read_by_its_offsets(monkeypatch):
    async def fake_api_get(endpoint, params=None, **kwargs):
        return TITLES if endpoint == "versioner/v1/titles.json" else LONG.get((params or {}).get("section"), SECTION)

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    monkeypatch.setattr(ecfr, "_titles_cache", None)
    first = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1"))
    assert first["truncated"] and first["total_chars"] > 12000 and first["text"].endswith("The following definitions apply:")   # only what comes before the first subheading
    headings = [entry.split(": ", 1) for entry in first["outline"]]
    assert [h for _, h in headings][:4] == ["Acquisition cost", "Budget", "Modified Total Direct Cost (MTDC)", "Subaward"] and len(headings) == 18
    start, stop = int(headings[2][0]), int(headings[3][0])
    part = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1", offset=start, end_offset=stop))
    assert part["text"].startswith("Modified Total Direct Cost (MTDC) means Costs must be") and part["text"].endswith("Federal award.")
    assert part["returned_chars"] == len(part["text"]) < 800 and part["next_offset"] == stop and "outline" not in part
    # a subheading's part runs to the heading the caller names, so one with paragraphs under it is read whole
    sub = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1", offset=stop, end_offset=int(headings[4][0])))
    assert sub["text"].startswith("Subaward means") and "\n\n(1) Costs must be" in sub["text"]
    assert "past offset" in json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1", offset=stop, end_offset=start))["error"]["message"]


async def test_a_long_section_with_no_subheadings_is_paged_and_a_short_one_comes_whole(monkeypatch):
    async def fake_api_get(endpoint, params=None, **kwargs):
        return TITLES if endpoint == "versioner/v1/titles.json" else LONG.get((params or {}).get("section"), SECTION)

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    monkeypatch.setattr(ecfr, "_titles_cache", None)
    whole = json.loads(await ecfr.ecfr_get_regulation(title=42, part="50", section="50.605", max_chars=40000))
    assert not whole["truncated"] and "outline" not in whole and whole["returned_chars"] == whole["total_chars"] > 12000
    pages, offset = [], 0
    while True:
        page = json.loads(await ecfr.ecfr_get_regulation(title=42, part="50", section="50.605", offset=offset))
        assert "outline" not in page and page["returned_chars"] <= 12000 and page["offset"] == offset
        pages.append(page["text"])
        if not page["truncated"]:
            break
        offset = page["next_offset"]
    assert len(pages) == 2 and "\n\n".join(pages) == whole["text"] and pages[0].endswith("Federal award.")   # cut on a paragraph break
    short = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.431"))
    assert not short["truncated"] and "outline" not in short and "next_offset" not in short and short["offset"] == 0


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
    assert 'title=2, part="200"' in tool.description and "With no date= the search is of the current text" in tool.description
    assert "date" not in tool.input_schema.get("required", [])
    fetch = next(t for t in await ecfr.mcp.list_tools() if t.name == "ecfr_get_regulation")
    assert "date" not in fetch.input_schema.get("required", []) and "ecfr_get_title_versions first" not in fetch.description
    assert "office-of-management-and-budget" not in tool.description + json.dumps(props)
