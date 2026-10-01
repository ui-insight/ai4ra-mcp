"""ecfr: the query a search sends when it is limited to a title and part (the eCFR's hierarchy filter), the scope kept
in the result, the date used when none is given (the latest day the eCFR holds, never the clock's), a long section
as its outline and a part read to its end by its offset, a long section with no subheadings paged, bad input."""

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
    hit = out["results"][0]
    assert hit["citation"] == "2 CFR § 200.430" and "full_text_excerpt" not in hit
    # a hit is what a caller needs to choose it and read it, without the eCFR's headings repeated in every one (#22)
    assert hit == {"citation": "2 CFR § 200.430", "heading": "Compensation—personal services.", "title": 2, "part": "200", "section": "200.430",
                   "source_url": "https://www.ecfr.gov/current/title-2/section-200.430"}
    marked = json.loads(await ecfr.ecfr_search(query="compensation", title=2, part="200", date="all", include_excerpts=True))["results"][0]
    assert marked["starts_on"] == "2024-10-01" and marked["ends_on"] is None and marked["full_text_excerpt"].startswith("Compensation for personal services")
    assert ecfr._make_citation(title=2, part="200", appendix="Appendix III to Part 200") == "2 CFR Appendix III to Part 200"


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
LONG = {   # texts longer than one window: definitions, a section of lettered paragraphs, one with no subheadings, an appendix
    "200.1": _section("200.1", ["The following definitions apply:"] + [f"<I>{term}</I> means {FILL}" for term in ("Acquisition cost", "Budget", "Modified Total Direct Cost (MTDC)", "Subaward")]
                      + [f"(1) {FILL}"] + [f"<I>Term {n}</I> means {FILL}" for n in range(26)]),
    "200.430": _section("200.430", [f"({letter}) <I>Heading {letter}.</I> {FILL}" for letter in "abcdefg"] + [f"(1) {FILL}", f"(i) {FILL}", f"(2) {FILL}"]
                        + [f"(h) <I>Nonprofits.</I> {FILL}", f"(i) <I>Institutions.</I> {FILL}"] + [f"({n}) <I>Item {n}.</I> {FILL}" for n in range(1, 16)]),
    "50.605": _section("50.605", [f"({letter}) {FILL}" for letter in "abcdefghijklmnopqrstuvwxyz"] + [FILL] * 6),
    "Appendix III to Part 200": '<DIV9 N="Appendix III to Part 200" TYPE="APPENDIX"><HEAD>Appendix III to Part 200</HEAD><HD1>A. General</HD1>' + f"<P>{FILL}</P>" * 3
                                + f"<HD2>1. Major functions</HD2><P>{FILL}</P><HD2>2. Criteria</HD2>" + f"<P>{FILL}</P>" * 12 + f"<HD1>B. Identification</HD1>" + f"<P>{FILL}</P>" * 14 + "</DIV9>",
}


def _long_texts(monkeypatch):
    async def fake_api_get(endpoint, params=None, **kwargs):
        params = params or {}
        return TITLES if endpoint == "versioner/v1/titles.json" else LONG.get(params.get("section") or params.get("appendix"), SECTION)

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    monkeypatch.setattr(ecfr, "_titles_cache", None)


def _outline(result):
    return {heading: int(at) for at, heading in (entry.split(": ", 1) for entry in result["outline"])}


async def test_a_long_section_comes_back_as_its_outline_and_a_part_is_read_by_its_offset(monkeypatch):
    _long_texts(monkeypatch)
    first = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1"))
    assert first["truncated"] and first["total_chars"] > 12000 and first["text"].endswith("The following definitions apply:")   # only what comes before the first subheading
    assert "next_offset" not in first and list(_outline(first))[:4] == ["Acquisition cost", "Budget", "Modified Total Direct Cost (MTDC)", "Subaward"] and len(first["outline"]) == 30
    at = _outline(first)
    part = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1", offset=at["Modified Total Direct Cost (MTDC)"]))
    assert part["text"].startswith("Modified Total Direct Cost (MTDC) means Costs must be") and part["text"].endswith("Federal award.")
    assert part["returned_chars"] == len(part["text"]) < 800 and not part["truncated"] and "next_offset" not in part and "outline" not in part
    assert part["pinpoint"] == "2 CFR 200.1 Modified Total Direct Cost (MTDC)" and "pin" not in part and "pinpoint" not in first   # a defined term is cited by name
    # a part runs to the next subheading of its level, so a definition comes with the numbered item under it
    sub = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.1", offset=at["Subaward"]))
    assert sub["text"].startswith("Subaward means") and "\n\n(1) Costs must be" in sub["text"] and "Term 0" not in sub["text"] and not sub["truncated"]


async def test_a_part_ends_where_the_next_subheading_of_its_level_begins(monkeypatch):
    _long_texts(monkeypatch)
    at = _outline(json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.430")))
    g = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.430", offset=at["(g) Heading g."]))["text"]
    assert g.startswith("(g) Heading g.") and "\n\n(1) Costs" in g and "\n\n(i) Costs" in g and "\n\n(2) Costs" in g and "(h) Nonprofits." not in g   # the numeral (i) under (g)(1) stays in (g)
    h = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.430", offset=at["(h) Nonprofits."]))["text"]
    assert h.startswith("(h) Nonprofits.") and "Institutions." not in h   # the letter (i) that follows (h) is the next part, not something under (h)
    i = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.430", offset=at["(i) Institutions."]))
    assert "(1) Item 1." in i["text"] and i["text"].count("Item ") == 15 and not i["truncated"]   # its numbered items are under it, to the end of the section
    one = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.430", offset=at["(5) Item 5."]))
    assert one["text"].startswith("(5) Item 5.") and "Item 6." not in one["text"]
    # a part read says which paragraph it is, from the labels of the headings it sits under, so a finding cites what it quotes (#23)
    assert one["pinpoint"] == "2 CFR 200.430(i)(5)" and i["pinpoint"] == "2 CFR 200.430(i)"
    assert json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.430", offset=at["(g) Heading g."]))["pinpoint"] == "2 CFR 200.430(g)"
    app = _outline(json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", appendix="Appendix III to Part 200")))
    a = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", appendix="Appendix III to Part 200", offset=app["A. General"]))["text"]
    assert "--- 1. Major functions ---" in a and "--- 2. Criteria ---" in a and "B. Identification" not in a   # a heading takes the lower headings under it
    one = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", appendix="Appendix III to Part 200", offset=app["1. Major functions"]))
    assert one["text"].startswith("--- 1. Major functions ---") and "2. Criteria" not in one["text"] and one["pinpoint"] == "2 CFR Appendix III to Part 200, A.1"


async def test_a_long_section_with_no_subheadings_is_paged_and_a_shorter_one_comes_whole(monkeypatch):
    _long_texts(monkeypatch)
    whole = ecfr._xml_to_text(LONG["50.605"])
    pages, offset = [], 0
    while True:
        page = json.loads(await ecfr.ecfr_get_regulation(title=42, part="50", section="50.605", offset=offset))
        assert "outline" not in page and page["returned_chars"] <= 12000 and page["offset"] == offset and page["total_chars"] == len(whole)
        pages.append(page["text"])
        if not page["truncated"]:
            break
        offset = page["next_offset"]
    assert len(pages) == 2 and "\n\n".join(pages) == whole and pages[0].endswith("Federal award.")   # cut on a paragraph break
    short = json.loads(await ecfr.ecfr_get_regulation(title=2, part="200", section="200.431"))
    assert not short["truncated"] and "outline" not in short and "next_offset" not in short and short["offset"] == 0


async def test_the_size_of_a_read_is_the_server_s_and_a_size_a_caller_sends_is_ignored(monkeypatch):
    from ai4ra_mcp.common import text

    mid = _section("200.413", [f"({letter}) <I>Heading {letter}.</I> {FILL}" for letter in "abcde"])   # about 3,800 characters, with subheadings

    async def fake_api_get(endpoint, params=None, **kwargs):
        return TITLES if endpoint == "versioner/v1/titles.json" else mid

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    monkeypatch.setattr(ecfr, "_titles_cache", None)
    assert text.WHOLE_CHARS == 12000
    tool = next(t for t in await ecfr.mcp.list_tools() if t.name == "ecfr_get_regulation")
    assert "max_chars" not in tool.input_schema["properties"] and "end_offset" not in tool.input_schema["properties"]
    # a model asked for 3,000 of a 3,777-character section and got an outline, then was refused for asking for 400 (#22)
    for sent in ({}, {"max_chars": 3000}, {"max_chars": 400}):
        result = await ecfr.mcp.call_tool("ecfr_get_regulation", {"title": 2, "part": "200", "section": "200.413", **sent})
        content = result[0] if isinstance(result, tuple) else result
        blocks = content.content if hasattr(content, "content") else content
        out = json.loads(blocks[0].text)
        assert not out["truncated"] and "outline" not in out and out["returned_chars"] == out["total_chars"] > 3000


async def test_a_long_query_that_finds_nothing_is_told_to_use_fewer_words(monkeypatch):
    async def fake_api_get(endpoint, params=None, **kwargs):
        return TITLES if endpoint == "versioner/v1/titles.json" else {"results": [], "meta": {"total_count": 0, "total_pages": 0, "current_page": 1}}

    monkeypatch.setattr(ecfr, "api_get", fake_api_get)
    monkeypatch.setattr(ecfr, "_titles_cache", None)
    out = json.loads(await ecfr.ecfr_search(query="compensation salary rate academic summer", title=2, part="200"))
    assert "two or three" in out["warnings"][0]
    assert "warnings" not in json.loads(await ecfr.ecfr_search(query="summer salary", title=2, part="200"))


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
