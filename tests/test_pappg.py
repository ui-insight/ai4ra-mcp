"""pappg, offline from NSF 24-1 pages captured on 2026-10-16 (the site chrome cut): the table of contents read to chapters
and sections with anchors and labels; a chapter read to blocks under its headings with a lettered section's anchor made
from its heading; the landing page's version line; one section by label, anchor or heading words with its subsections;
a search across chapters; and bad input."""

from pathlib import Path

from ai4ra_mcp.servers.pappg import server as pg

FIX = Path(__file__).parent / "fixtures" / "pappg"
PAGES = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}


def _site(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append(url)
        if url == pg.TOC:
            return PAGES["toc"]
        if url == pg.SITE:
            return PAGES["index"]
        if url.endswith("ch-2-proposal-preparation"):
            return PAGES["ch2"]
        if url.endswith("ch-10-allowability-of-costs"):
            return PAGES["ch10"]
        return "<html><body><main></main></body></html>"

    monkeypatch.setattr(pg, "get_text", get_text)
    pg._cache._d.clear()
    return calls


def test_the_table_of_contents_is_read_to_chapters_and_sections():
    chapters = pg.parse_toc(PAGES["toc"])
    assert [c["roman"] for c in chapters] == list(pg.ROMAN) and chapters[1]["title"] == "Proposal Preparation Instructions" and chapters[1]["slug"] == "ch-2-proposal-preparation"
    two = chapters[1]["sections"]
    assert two[0]["anchor"] == "ch2A" and two[0]["label"] == "A" and two[0]["page_anchor"].startswith("a-conformance") and two[0]["title"].startswith("Conformance")
    assert two[1] == {"anchor": "ch2A1", "page_anchor": "ch2A1", "label": "A.1", "title": "Deviations from NSF Proposal Preparation and Submission Requirements"}
    assert any(s["anchor"] == "ch2D2b" and s["label"] == "D.2.b" and s["title"] == "Project Summary" for s in two) and sum(len(c["sections"]) for c in chapters) == 319  # 323 links, four of them repeats
    assert pg.label_of("ch10.A1", 10) == "A.1" and pg.label_of("ch12C3", 12) == "C.3"


def test_a_chapter_is_read_to_blocks_under_its_headings():
    blocks = pg.parse_chapter(PAGES["ch2"], 2)
    assert blocks[0]["level"] == 2 and blocks[0]["anchor"] == "ch2A" and blocks[0]["label"] == "A" and blocks[0]["heading"].startswith("A. Conformance")
    b = next(x for x in blocks if x["anchor"] == "ch2D2b")
    assert b["level"] == 3 and b["label"] == "D.2.b" and b["heading"] == "b. Project Summary" and b["paragraphs"][0].startswith("Each proposal must contain a summary") and len(b["paragraphs"]) == 3
    assert all("<" not in p for x in blocks for p in x["paragraphs"])
    ten = pg.parse_chapter(PAGES["ch10"], 10)
    assert ten[0]["anchor"] == "ch10A" and ten[1]["anchor"] == "ch10.A1" and ten[1]["label"] == "A.1"
    eff = pg.parse_effective(PAGES["index"])
    assert eff["version"] == "24-1" and eff["effective"] == "May 20, 2024" and eff["supplements"][0] == {"supplement": "Supplement 1", "number": "NSF 26-200", "applies_to_awards_on_or_after": "Dec. 8, 2025", "link": pg.SITE + "/26-200"} and len(eff["supplements"]) == 2
    assert pg.parse_effective("<p>nothing</p>") is None


async def test_chapters_outline_and_a_section_by_label_anchor_or_words(monkeypatch):
    calls = _site(monkeypatch)
    ch = await pg.pappg_chapters()
    assert ch["total"] == 12 and ch["chapters"][1] == {"chapter": "II", "number": 2, "title": "Proposal Preparation Instructions", "sections": len(pg.parse_toc(PAGES["toc"])[1]["sections"]), "link": pg.BASE + "ch-2-proposal-preparation"}
    out = await pg.pappg_outline("2")
    assert out["chapter"] == "II" and out["sections"][0]["link"] == pg.BASE + "ch-2-proposal-preparation#" + out["sections"][0]["page_anchor"] and out["sections"][1]["link"].endswith("#ch2A1")
    s = await pg.pappg_section("II", "D.2.b")
    assert s["heading"] == "b. Project Summary" and s["cite"] == "PAPPG Chapter II.D.2.b" and s["link"].endswith("#ch2D2b") and s["subsections"] == []
    assert calls.count(pg.BASE + "ch-2-proposal-preparation") == 1
    s = await pg.pappg_section("ii", "ch2D2b")
    assert s["label"] == "D.2.b" and calls.count(pg.BASE + "ch-2-proposal-preparation") == 1  # cached
    s = await pg.pappg_section("II", "D")
    assert s["heading"].startswith("D. Proposal Contents") and any(x["anchor"] == "ch2D2b" for x in s["subsections"]) and s["cite"] == "PAPPG Chapter II.D" and s["link"].endswith("#d-proposal-contents-171")
    s = await pg.pappg_section("X", "A.1")
    assert s["heading"] == "1. Conflicting Guidelines" and s["cite"] == "PAPPG Chapter X.A.1"
    s = await pg.pappg_section("II", "project summary")
    assert s["anchor"] == "ch2D2b"
    several = await pg.pappg_section("II", "proposal")
    assert "error" in several and len(several["sections"]) > 1
    assert "error" in await pg.pappg_section("II", "zzqx") and "error" in await pg.pappg_section("XIII", "A") and "error" in await pg.pappg_section("II", "")
    assert "error" in await pg.pappg_section("III", "A")  # a chapter whose page came back without text blocks


async def test_search_across_chapters_and_in_one(monkeypatch):
    _site(monkeypatch)
    out = await pg.pappg_search("project summary", chapter="II", rows=3)
    assert out["total"] >= 1 and out["sections"][0]["anchor"] == "ch2D2b" and out["sections"][0]["in_heading"] and "…" in out["sections"][0]["snippet"] or len(out["sections"][0]["snippet"]) <= 300
    out = await pg.pappg_search("intellectual merit broader impacts")
    assert out["total"] >= 1 and all(h["chapter"] in pg.ROMAN for h in out["sections"])
    assert (await pg.pappg_search("zzqx"))["total"] == 0 and "error" in await pg.pappg_search("")


async def test_the_index_reports_the_version(monkeypatch):
    _site(monkeypatch)
    out = await pg.pappg_index()
    assert out["version"]["served"] == "NSF 24-1" and out["version"]["nsf_says_current"]["version"] == "24-1" and "note" not in out and [s["number"] for s in out["supplements"]] == ["NSF 26-200", "NSF 26-202"]
    assert {t.name for t in await pg.mcp.list_tools()} == {"pappg_index", "pappg_chapters", "pappg_outline", "pappg_section", "pappg_search"}
