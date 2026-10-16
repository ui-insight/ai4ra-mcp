"""idstat, offline from pages captured at legislature.idaho.gov and its search engine on 2026-10-16 (the WordPress chrome
cut, the statute and result markup kept): the title index, a title's chapters, a chapter's sections, two sections'
text and history, a search with hits and one with none, the citation grammar, the parameters each tool sends (and the
search's User-Agent), the day-long cache, and what a missing page or a changed one says."""

from pathlib import Path

import pytest

from ai4ra_mcp.servers.idstat import idstat
from ai4ra_mcp.servers.idstat import server as st

FIX = Path(__file__).parent / "fixtures" / "idstat"
PAGES = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}


def _site(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        if url == idstat.SEARCH:
            return PAGES["search_none" if params["IW_FIELD_WEB_STYLE"] == "zzqx" else "search_regents"]
        if url == idstat.CURRENCY:
            return "<p>Idaho Statutes and Constitutions are current through the 2026 Legislative Session.</p>"
        if url == idstat.BASE:
            return PAGES["titles"]
        if url.endswith("/Title67/"):
            return PAGES["title67"]
        if url.endswith("/T67CH53/"):
            return PAGES["t67ch53"]
        if url.endswith("/SECT67-5301/"):
            return PAGES["sect67-5301"]
        if url.endswith("/SECT33-2901/"):
            return PAGES["sect33-2901"]
        if "SECT" in url:
            raise ValueError(f"404 from {url}: nothing at that address")
        return "<html><body>a page without statutes</body></html>"

    monkeypatch.setattr(idstat, "get_text", get_text)
    st._cache._d.clear()
    return calls


def test_the_title_index_chapters_and_sections_are_read_from_the_tables():
    titles = idstat.parse_titles(PAGES["titles"])
    assert len(titles) == 74 and titles[0] == {"title": 1, "name": "COURTS AND COURT OFFICIALS", "link": "https://legislature.idaho.gov/statutesrules/idstat/Title1"}
    assert next(t for t in titles if t["title"] == 67)["name"] == "STATE GOVERNMENT AND STATE AFFAIRS"
    ch = idstat.parse_chapters(PAGES["title67"])
    assert ch["heading"] == "TITLE 67 STATE GOVERNMENT AND STATE AFFAIRS" and len(ch["chapters"]) == 91
    assert next(c for c in ch["chapters"] if c["chapter"] == 53) == {"chapter": 53, "name": "PERSONNEL SYSTEM", "link": "https://legislature.idaho.gov/statutesrules/idstat/Title67/T67CH53",
                                                                     "pdf": "https://legislature.idaho.gov/wp-content/uploads/statutesrules/idstat/Title67/T67CH53.pdf"}
    se = idstat.parse_sections(PAGES["t67ch53"])
    assert se["title_heading"] == "TITLE 67 STATE GOVERNMENT AND STATE AFFAIRS" and se["chapter_heading"] == "CHAPTER 53 PERSONNEL SYSTEM" and len(se["sections"]) == 33
    assert se["sections"][0] == {"section": "67-5301", "heading": "ESTABLISHMENT OF DIVISION OF HUMAN RESOURCES AND DECLARATION OF POLICY", "link": "https://legislature.idaho.gov/statutesrules/idstat/Title67/T67CH53/SECT67-5301"}
    assert [s["section"] for s in se["sections"] if not s["section"][-1].isdigit()] == ["67-5309A", "67-5309B", "67-5309C", "67-5309D", "67-5333A", "67-5342A"]
    assert se["pdf"].endswith("/Title67/T67CH53.pdf")


def test_a_section_page_is_read_to_heading_text_and_history():
    s = idstat.parse_section(PAGES["sect67-5301"])
    assert s["title_heading"] == "TITLE 67 STATE GOVERNMENT AND STATE AFFAIRS" and s["chapter_heading"] == "CHAPTER 53 PERSONNEL SYSTEM"
    assert s["section"] == "67-5301" and s["heading"] == "Establishment of division of human resources and declaration of policy"
    assert len(s["text"]) == 1 and s["text"][0].startswith("There is hereby established the division of human resources") and s["text"][0].endswith("under the powers of the state.")
    assert s["history"].startswith("[67-5301, added 1965, ch. 289") and s["history"].endswith("am. 2022, ch. 112, sec. 2, p. 401.]")
    s = idstat.parse_section(PAGES["sect33-2901"])
    assert s["chapter_heading"] == "CHAPTER 29 UNIVERSITY OF IDAHO — FEDERAL EDUCATIONAL AID" and s["heading"] == "Assent to Morrill acts" and "Morrill" not in s["text"][0][:10]
    with pytest.raises(idstat.StatuteError):
        idstat.parse_section("<html><body>no statute here</body></html>")


def test_a_search_page_is_read_to_sections_hits_and_snippets():
    r = idstat.parse_search(PAGES["search_regents"])
    assert (r["from"], r["to"], r["sections"], r["hits"]) == (1, 10, 30, 45) and len(r["results"]) == 10
    first = r["results"][0]
    assert first["kind"] == "section" and first["section"] == "22-2905" and first["hits"] == 4 and first["link"] == "https://legislature.idaho.gov/statutesrules/idstat/Title22/T22CH29/SECT22-2905/"
    assert first["snippet"].startswith("... The **regents** of the University of Idaho — Powers and duties.") and "<" not in first["snippet"]
    last = r["results"][-1]
    assert last["kind"] == "chapter" and last["section"] is None and last["page"] == "Chapter 15" and last["link"].endswith("/Title22/T22CH15/")
    assert idstat.parse_search(PAGES["search_none"]) == {"from": 0, "to": 0, "sections": 0, "hits": 0, "results": []}
    with pytest.raises(idstat.StatuteError):
        idstat.parse_search("<html><body>Something else entirely</body></html>")


def test_citations_name_their_page():
    assert idstat.parse_citation("33-2901") == (33, 29, "33-2901") and idstat.parse_citation("67-5309a") == (67, 53, "67-5309A") and idstat.parse_citation(" 33-107C ") == (33, 1, "33-107C")
    assert idstat.section_url("22-2905") == "https://legislature.idaho.gov/statutesrules/idstat/Title22/T22CH29/SECT22-2905/"
    for bad in ("33", "33-29", "section 33-2901", "33-2901-2", "idaho code"):
        with pytest.raises(ValueError):
            idstat.parse_citation(bad)
    assert idstat.parse_currency("<p>Idaho Statutes and Constitutions are current through the 2026 Legislative Session.</p>") == "current through the 2026 Legislative Session"
    assert idstat.parse_currency("<p>nothing</p>") is None


async def test_the_outline_tools_fetch_each_page_once_a_day(monkeypatch):
    calls = _site(monkeypatch)
    t = await st.idstat_titles()
    assert t["total"] == 74 and calls[-1][0] == idstat.BASE and calls[-1][2] == idstat.HEADERS
    c = await st.idstat_chapters(67)
    assert c["total"] == 91 and c["heading"].startswith("TITLE 67") and calls[-1][0] == idstat.title_url(67)
    s = await st.idstat_sections(67, 53)
    assert s["total"] == 33 and s["chapter_heading"] == "CHAPTER 53 PERSONNEL SYSTEM" and s["pdf"].endswith("T67CH53.pdf")
    n = len(calls)
    await st.idstat_titles()
    await st.idstat_chapters(67)
    await st.idstat_sections(67, 53)
    assert len(calls) == n
    assert "error" in await st.idstat_chapters("x") and "error" in await st.idstat_chapters(0)
    out = await st.idstat_chapters(99)
    assert "no chapters" in out["error"] and out["link"] == idstat.title_url(99)


async def test_a_section_by_citation_and_one_that_is_not_there(monkeypatch):
    calls = _site(monkeypatch)
    out = await st.idstat_section("67-5301")
    assert out["citation"] == "67-5301" and out["heading"].startswith("Establishment") and out["history"] and out["link"] == idstat.section_url("67-5301")
    assert calls[-1][0] == "https://legislature.idaho.gov/statutesrules/idstat/Title67/T67CH53/SECT67-5301/"
    out = await st.idstat_section("33-2901")
    assert out["chapter_heading"].startswith("CHAPTER 29 UNIVERSITY OF IDAHO")
    out = await st.idstat_section("33-9999")
    assert "404" in out["error"] and out["link"].endswith("/Title33/T33CH99/SECT33-9999/")
    assert "error" in await st.idstat_section("Idaho Code 33")


async def test_search_sends_the_engine_its_fields_and_the_compatible_agent(monkeypatch):
    calls = _site(monkeypatch)
    out = await st.idstat_search("regents", rows=10)
    url, params, headers = calls[-1]
    assert url == idstat.SEARCH and params == {"IW_FIELD_WEB_STYLE": "regents", "IW_DATABASE": "Idaho Statutes", "IW_BATCHSIZE": 10}
    assert headers["User-Agent"].startswith("Mozilla/5.0 (compatible; ai4ra-mcp/") and "ai4ra-mcp" in headers["User-Agent"]
    assert out["sections_matched"] == 30 and out["hits"] == 45 and out["returned"] == 10 and out["results"][0]["section"] == "22-2905" and "30 sections matched" in out["note"]
    assert out["link"].startswith(idstat.SEARCH + "?IW_FIELD_WEB_STYLE=regents")
    none = await st.idstat_search("zzqx")
    assert none["sections_matched"] == 0 and none["results"] == [] and "note" not in none
    assert (await st.idstat_search("  "))["error"] == "query is required"
    await st.idstat_search("Regents", rows=99)
    assert calls[-1][1]["IW_BATCHSIZE"] == 50


async def test_the_index_reports_how_current_the_code_is(monkeypatch):
    _site(monkeypatch)
    out = await st.idstat_index()
    assert out["current"] == "current through the 2026 Legislative Session" and out["caveats"] == st.CAVEATS and out["upstream"].startswith("The Idaho Statutes")
