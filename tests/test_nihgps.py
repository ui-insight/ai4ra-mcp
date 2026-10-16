"""nihgps, offline from the web edition's table-of-contents data files and three pages captured on 2026-10-16 (the site
chrome cut): the contents read in order with each section's number; a section page read to heading, paragraphs, the
Exhibit 5 table and the revision line, glossary popups dropped; a chapter's placeholder page; one section by number or
title with its subsections; a search within a chapter; and bad input."""

from pathlib import Path

from ai4ra_mcp.servers.nihgps import server as gp

FIX = Path(__file__).parent / "fixtures" / "nihgps"
TOC_JS = (FIX / "TOC_Web.js").read_text(encoding="utf-8")
CHUNKS = [(FIX / f"TOC_Web_Chunk{i}.js").read_text(encoding="utf-8") for i in range(3)]
PAGES = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}


def _site(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append(url)
        if url == gp.TOC:
            return TOC_JS
        if "TOC_Web_Chunk" in url:
            return CHUNKS[int(url[-4])]
        if url.endswith("7.9_allowability_of_costs_activities.htm"):
            return PAGES["7_9"]
        if url.endswith("7_cost_consideration.htm"):
            return PAGES["7"]
        if url.endswith("introduction.htm"):
            return PAGES["introduction"]
        return "<html><body><div class=\"body-container\"><div data-mc-content-body=\"True\"><h2>x</h2><p>A page with no words of its own.</p></div></div></body></html>"

    monkeypatch.setattr(gp, "get_text", get_text)
    gp._cache._d.clear()
    return calls


def test_the_contents_are_read_in_order_with_numbers():
    assert gp.chunk_names(TOC_JS) == ["Data/Tocs/TOC_Web_Chunk0.js", "Data/Tocs/TOC_Web_Chunk1.js", "Data/Tocs/TOC_Web_Chunk2.js"]
    toc = gp.parse_toc(TOC_JS, CHUNKS)
    assert len(toc) > 276 and toc[0]["path"] == "introduction.htm" and toc[0]["number"] is None
    seven = [e for e in toc if e["number"] == "7.9"]
    assert seven == [{"order": seven[0]["order"], "number": "7.9", "title": "7.9 Allowability of Costs/Activities", "path": "section_7/7.9_allowability_of_costs_activities.htm", "anchor": None, "url": gp.BASE + "section_7/7.9_allowability_of_costs_activities.htm"}]
    sub = next(e for e in toc if e["number"] == "7.9.1")
    assert sub["path"] == seven[0]["path"] and sub["anchor"] == "#Selected" and sub["url"].endswith(".htm#Selected")  # the same page, at its anchor
    assert [e["number"] for e in toc if e["path"].startswith("section_7/")][:4] == ["7", "7.1", "7.2", "7.3"]
    assert not any(e["path"].startswith("toc_") for e in toc)


def test_a_section_page_is_read_to_text_tables_and_revision():
    s = gp.parse_section(PAGES["7_9"])
    assert s["heading"] == "7.9 Allowability of Costs/Activities" and s["subheadings"] == ["7.9.1 Selected Items of Cost"] and s["revised"].startswith("REVISED MARCH 2026")
    assert s["paragraphs"][0].startswith("The governing cost principles address selected items of cost") and "The government-wide principles" not in s["paragraphs"][0]  # the popup is dropped
    assert len(s["tables"]) == 1 and s["tables"][0]["header"] == ["Items", "Explanation of Allowable Costs"] and len(s["tables"][0]["rows"]) > 90
    assert s["tables"][0]["rows"][1][0] == "Alcoholic Beverages" and s["tables"][0]["rows"][1][1].startswith("Unallowable as an entertainment expense")
    assert not any("You are here" in p or p.startswith("REVISED") for p in s["paragraphs"])
    placeholder = gp.parse_section(PAGES["7"])
    assert placeholder["heading"] == "7 Cost Consideration" and placeholder["paragraphs"] == [] and placeholder["tables"] == []
    intro = gp.parse_section(PAGES["introduction"])
    assert intro["heading"] == "1 Introduction" and intro["paragraphs"] and "<" not in " ".join(intro["paragraphs"])


async def test_toc_section_and_subsections(monkeypatch):
    calls = _site(monkeypatch)
    toc = await gp.nihgps_toc(query="allowability")
    assert toc["total"] >= 1 and any(s["number"] == "7.9" for s in toc["sections"]) and calls.count(gp.TOC) == 1 and len([c for c in calls if "Chunk" in c]) == 3
    seven = await gp.nihgps_toc(chapter="7")
    assert seven["sections"][0]["number"] == "7" and all(s["number"].startswith("7") for s in seven["sections"])
    s = await gp.nihgps_section("7.9")
    assert s["cite"] == "NIH GPS 7.9" and s["heading"].startswith("7.9 ") and s["tables"][0]["header"][0] == "Items" and [x["number"] for x in s["subsections"]] == ["7.9.1"] and s["subsections"][0]["link"].startswith(gp.BASE + "section_7/7.9")
    s2 = await gp.nihgps_section("Allowability of Costs/Activities")
    assert s2["number"] == "7.9" and calls.count(gp.BASE + "section_7/7.9_allowability_of_costs_activities.htm") == 1
    ch = await gp.nihgps_section("7")
    assert ch["paragraphs"] == [] and "chapter heading" in ch["note"] and len(ch["subsections"]) >= 9 and ch["subsections"][0]["number"] == "7.1"
    several = await gp.nihgps_section("costs")
    assert "error" in several and len(several["sections"]) > 1
    assert "error" in await gp.nihgps_section("99.99") and "error" in await gp.nihgps_section("")


async def test_search_within_a_chapter(monkeypatch):
    calls = _site(monkeypatch)
    out = await gp.nihgps_search("alcoholic beverages", "7")
    assert out["sections_read"] >= 9 and out["total"] == 2 and out["sections"][0]["number"] == "7.9" and "Alcoholic Beverages" in out["sections"][0]["snippet"]  # 7.9 and 7.9.1 share the page
    assert "error" in await gp.nihgps_search("x", "") and "error" in await gp.nihgps_search("x", "99")
    assert (await gp.nihgps_search("zzqx", "7"))["total"] == 0


async def test_the_index_reports_the_revision(monkeypatch):
    _site(monkeypatch)
    out = await gp.nihgps_index()
    assert out["revision"].startswith("REVISED MARCH 2026") and out["sections"] > 276
    assert {t.name for t in await gp.mcp.list_tools()} == {"nihgps_index", "nihgps_toc", "nihgps_section", "nihgps_search"}
