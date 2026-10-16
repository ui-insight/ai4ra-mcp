"""re3data, offline from a list (cut to five) and two repository records captured from the beta API on 2026-10-16: the list
read to ids, DOIs and names; a record read to its fields; a search sending the facets as repeated parameters and
reading the first rows' records; one repository; and bad input."""

from pathlib import Path

import pytest

from ai4ra_mcp.servers.re3data import server as r3

FIX = Path(__file__).parent / "fixtures" / "re3data"
PAGES = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.xml")}


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append((url, list(params) if params else None))
        if url.endswith("/repositories"):
            return PAGES["list"] if ("query", "nothing") not in (params or []) else '<?xml version="1.0"?><list></list>'
        if url.endswith("/repository/r3d100000044"):
            return PAGES["dryad"]
        if url.endswith("/repository/r3d100999999"):
            raise ValueError(f"404 from {url}: nothing at that address")
        return PAGES["complete_genomics"]

    monkeypatch.setattr(r3, "get_text", get_text)
    r3._cache._d.clear()
    return calls


def test_the_list_and_a_record_are_read():
    found = r3.parse_list(PAGES["list"])
    assert len(found) == 5 and found[0] == {"id": "r3d100011709", "name": "Complete Genomics", "doi": "https://doi.org/10.17616/R3NP8M"}
    d = r3.parse_repository(PAGES["dryad"])
    assert d["id"] == "r3d100000044" and d["name"] == "DRYAD" and d["url"] == "https://datadryad.org/" and d["types"] == ["multidisciplinary", "other"]
    assert sorted(d["data_access"]) == ["embargoed", "open"] and d["pid_systems"] == ["DOI"] and d["data_licenses"][0] == {"name": "CC0", "url": "https://creativecommons.org/publicdomain/zero/1.0/"}
    assert d["data_upload"] == ["restricted"] and d["certificates"] == [] and d["apis"][0] == {"type": "REST", "url": "https://datadryad.org/api/v2/docs/"}
    assert d["institutions"][0]["name"] == "California Digital Library" and d["institutions"][0]["country"] == "USA" and "ROR:03yrm5c26" in d["institutions"][0]["identifiers"] and "technical" in d["institutions"][0]["responsibility"]
    assert "2 Life Sciences" in d["subjects"] and "Scientific and statistical data formats" in d["content_types"] and d["size"].startswith("over 70") and d["start_date"] == "2008" and d["versioning"] == "yes"
    assert d["last_update"] == "2026-09-11" and d["link"] == "https://www.re3data.org/repository/r3d100000044" and d["citation_guideline_url"] == "https://datadryad.org/terms"
    g = r3.parse_repository(PAGES["complete_genomics"])
    assert g["name"] == "Complete Genomics" and g["description"].endswith(" …") and len(g["description"]) <= 605 and "20105 General Genetics" in g["subjects"]
    with pytest.raises(ValueError):
        r3.parse_repository("<other/>")


async def test_search_sends_facets_and_reads_the_first_rows(monkeypatch):
    calls = _api(monkeypatch)
    out = await r3.re3data_search(query="genomics", subject="2 Life Sciences", country="usa", data_access="Open", pid_system="DOI", rows=2)
    url, params = calls[0]
    assert url == r3.API + "/repositories" and params == [("query", "genomics"), ("subjects[]", "2 Life Sciences"), ("countries[]", "USA"), ("dataAccesses[]", "open"), ("pidSystems[]", "DOI")]
    assert [c[0] for c in calls[1:]] == [r3.API + "/repository/r3d100011709", r3.API + "/repository/r3d100013743"]
    assert out["total"] == 5 and out["returned"] == 2 and out["repositories"][0]["doi"] == "https://doi.org/10.17616/R3NP8M" and "5 repositories match" in out["note"] and "r3d100012078 SOL Genomics Network" in out["note"]
    assert (await r3.re3data_search(query="nothing"))["total"] == 0
    assert "error" in await r3.re3data_search() and "error" in await r3.re3data_search(query="x", data_access="public")


async def test_one_repository_and_a_missing_one(monkeypatch):
    _api(monkeypatch)
    out = await r3.re3data_repository("r3d100000044")
    assert out["name"] == "DRYAD" and out["pid_systems"] == ["DOI"]
    assert (await r3.re3data_repository("r3d100999999"))["error"] == "no repository r3d100999999 in re3data"
    assert "error" in await r3.re3data_repository("dryad")


async def test_a_body_that_is_not_xml_is_reported(monkeypatch):
    async def get_text(url, params=None, headers=None):
        return "<html>down</html>" if url.endswith("/repositories") else "not xml <"

    monkeypatch.setattr(r3, "get_text", get_text)
    r3._cache._d.clear()
    assert (await r3.re3data_search(query="x"))["total"] == 0  # an HTML page parses as XML with no repository elements
    assert "something other than a repository record" in (await r3.re3data_repository("r3d100000044"))["error"]


async def test_the_index_explains_subjects_and_access():
    out = await r3.re3data_index()
    assert any("DFG classification" in n for n in out["notes"]) and out["limits"]["search"] == "1-25 records a call"
    assert {t.name for t in await r3.mcp.list_tools()} == {"re3data_index", "re3data_search", "re3data_repository"}
