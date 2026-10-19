"""library, offline from the University of Idaho Primo responses captured 2026-10-19 in tests/fixtures/library/: a search of local
physical items with their locations, a mixed local-and-central search, a shelf-available search, an article search, a search with no
hits, a local record and a central one in full, an unknown record; the request each tool builds; a catalog down said."""

import json
from pathlib import Path

from ai4ra_mcp.servers.library import server as lib

FIX = Path(__file__).parent / "fixtures" / "library"
F = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}


def _catalog(monkeypatch, calls=None, down=False):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        if down:
            raise ValueError("503 from alliance-uidaho.primo.exlibrisgroup.com: down")
        if url.endswith("/pnxs"):
            q = params["q"]
            if "bicentennial" in q:
                return F["search_physical"]
            if "critique" in q:
                return F["search_mixed"]
            if params.get("qInclude") == "facet_tlevel,exact,available_p":
                return F["search_available"]
            if params.get("qInclude") == "facet_rtype,exact,articles":
                return F["search_articles"]
            return F["search_none"]
        if url.endswith("/L/alma9921606601851"):
            return F["record_physical"]
        if url.endswith("/PC/cdi_gutenberg_primary_43572"):
            return F["record_pc"]
        return F["record_bad"]

    monkeypatch.setattr(lib, "get_json", get_json)
    lib._cache._d.clear()
    return calls


def test_slim_doc_physical_and_article():
    hit = lib.slim_doc(F["search_physical"]["docs"][0])
    assert hit["id"] == "alma9921606601851" and hit["context"] == "L" and hit["title"] == "Idaho : a bicentennial history" and hit["creators"] == ["Peterson, F. Ross (Frank Ross), 1941- author."]
    assert hit["type"] == "pbooks" and hit["year"] == "©1976" and hit["publisher"] == "New York : Norton" and hit["isbn"] == ["0393056007", "9780393056006"]
    assert hit["availability"] == "available_in_library" and hit["availability_means"].startswith("a physical copy is on the shelf")
    assert hit["location"] == {"library": "Main Library", "location": "Main Stacks (4th Floor)", "call_number": "F746.P47", "status": "available"}
    assert hit["link"] == "https://alliance-uidaho.primo.exlibrisgroup.com/discovery/fulldisplay?docid=alma9921606601851&context=L&vid=01ALLIANCE_UID:UID"
    special = lib.slim_doc(F["search_physical"]["docs"][1])
    assert special["location"]["location"].startswith("UI Library Special Collections") and special["subjects"]
    art = lib.slim_doc(F["search_articles"]["docs"][0])
    assert art["context"] == "PC" and art["type"] == "article" and art["doi"] == "10.1111/tpj.16190" and art["jtitle"].startswith("The Plant journal") and art["volume"] == "114" and art["spage"] == "1475"
    assert art["part_of"].startswith("The Plant journal") and art["availability"] == "fulltext" and "openurl" not in art and art["location"] is None and len(art["subjects"]) <= 8
    assert lib.AVAILABILITY["ResourceSharingRequest"].startswith("the library's copy is out on loan")
    mixed = [lib.slim_doc(d) for d in F["search_mixed"]["docs"]]
    assert mixed[0]["availability"] == "no_inventory" and mixed[0]["record_owner"] == "01ALLIANCE_NETWORK" and "no copy is held here" in mixed[0]["availability_means"]
    assert mixed[3]["availability"] == "available_in_library" and mixed[3]["location"]["call_number"]
    pc = lib.slim_doc(F["record_pc"])
    assert pc["context"] == "PC" and pc["id"] == "cdi_gutenberg_primary_43572" and pc["availability"] == "fulltext_linktorsrc" and pc["link"].endswith("context=PC&vid=01ALLIANCE_UID:UID")


async def test_search_builds_the_request_and_slims(monkeypatch):
    calls = _catalog(monkeypatch)
    out = await lib.library_search("Idaho a bicentennial history", rows=5)
    url, params, headers = calls[0]
    assert url == lib.PNXS and params["q"] == "any,contains,idaho a bicentennial history" and out["query"] == "Idaho a bicentennial history" and params["vid"] == "01ALLIANCE_UID:UID" and params["tab"] == "Everything" and params["scope"] == "DN_and_CI"
    assert params["inst"] == "01ALLIANCE_UID" and params["limit"] == 5 and params["offset"] == 0 and params["pcAvailability"] == "false" and params["sort"] == "rank" and "qInclude" not in params
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert out["total_local"] == F["search_physical"]["info"]["totalResultsLocal"] and out["total_central"] == F["search_physical"]["info"]["totalResultsPC"]
    assert out["returned"] == 5 and out["hits"][0]["id"] == "alma9921606601851" and out["next_offset"] == 5 and out["link"].startswith("https://alliance-uidaho.primo.exlibrisgroup.com/discovery/search?vid=")
    # The same search within the hour, whatever its spacing or case, is one request upstream.
    await lib.library_search("idaho  A Bicentennial   HISTORY", rows=5)
    assert len(calls) == 1
    out = await lib.library_search("wheat breeding", available=True, rows=3)
    assert calls[-1][1]["qInclude"] == "facet_tlevel,exact,available_p" and out["available"] is True and all(h["availability"] == "available_in_library" for h in out["hits"]) and out["total_central"] == 0
    out = await lib.library_search("wheat breeding", field="title", type="articles", rows=3)
    assert calls[-1][1]["q"] == "title,exact,wheat breeding" and calls[-1][1]["qInclude"] == "facet_rtype,exact,articles" and "multiFacets" not in calls[-1][1] and out["hits"][0]["doi"] == "10.1111/tpj.16190" and out["total_local"] == 0
    assert all("openurl" not in h for h in out["hits"])
    await lib.library_search("9780393056006", field="isbn", type="books", available=True, scope="special", sort="date")
    p = calls[-1][1]
    assert p["q"] == "isbn,exact,9780393056006" and p["multiFacets"] == "facet_rtype,include,books|,|facet_rtype,include,pbooks" and p["qInclude"] == "facet_tlevel,exact,available_p" and p["tab"] == "SPECAW_Slot" and p["scope"] == "SPECAW" and p["sort"] == "date"
    await lib.library_search("x", type="pbooks")
    assert calls[-1][1]["qInclude"] == "facet_rtype,exact,pbooks" and "multiFacets" not in calls[-1][1]
    await lib.library_search("x", type="ebooks")
    assert calls[-1][1]["qInclude"] == "facet_rtype,exact,books"
    out = await lib.library_search("zzqxv florp")
    assert out["returned"] == 0 and out["total"] == 0 and "One more search" in out["note"] and "ask the person" in out["note"] and "next_offset" not in out


async def test_record(monkeypatch):
    calls = _catalog(monkeypatch)
    rec = await lib.library_record("alma9921606601851")
    assert calls[0][0] == lib.PNXS + "/L/alma9921606601851" and calls[0][1] == {"vid": "01ALLIANCE_UID:UID", "lang": "en", "search_scope": "DN_and_CI", "adaptor": "Local Search Engine"}
    assert rec["title"] == "Idaho : a bicentennial history" and rec["contents"].startswith("Table of contents: Invitation to the reader") and rec["summary"].startswith("A native historian")
    assert rec["series"] == "Series statement: The States and the Nation series" and rec["subjects"] == ["Idaho -- History"] and len(rec["holdings"]) == 2 and rec["holdings"][0]["call_number"] == "F746.P47"
    assert rec["location"]["status"] == "available" and rec["source"] == "Alma" and rec["read_from"] == rec["link"] and "openurl" in rec
    pc = await lib.library_record("cdi_gutenberg_primary_43572")
    assert calls[-1][0].endswith("/PC/cdi_gutenberg_primary_43572") and calls[-1][1]["adaptor"] == "Primo Central" and pc["title"].startswith("A commentary to Kant") and pc["availability"] == "fulltext_linktorsrc"
    assert "openurl" in pc
    bad = await lib.library_record("alma0000000000")
    assert bad["error"].startswith("no record alma0000000000 in context L") and "library_search" in bad["error"]
    assert "id is required" in (await lib.library_record(""))["error"] and "context must be" in (await lib.library_record("alma1", context="X"))["error"]


async def test_arguments_and_down(monkeypatch):
    _catalog(monkeypatch)
    assert "query is required" in (await lib.library_search(" "))["error"]
    assert "field must be" in (await lib.library_search("x", field="publisher"))["error"]
    assert "scope must be" in (await lib.library_search("x", scope="all"))["error"]
    assert "sort must be" in (await lib.library_search("x", sort="newest"))["error"]
    assert "type must be" in (await lib.library_search("x", type="comics"))["error"]
    _catalog(monkeypatch, down=True)
    out = await lib.library_search("wheat")
    assert out["error"].startswith("503 from") and out["link"] == lib.SEARCH_PAGE
    assert (await lib.library_record("alma9921606601851"))["error"].startswith("503 from")
    idx = await lib.library_index()
    assert set(idx["scopes"]) == {"everything", "reserves", "special"} and idx["availability"]["no_inventory"] and any("Verso" in n for n in idx["notes"]) and any("never replaced by a guessed title" in n for n in idx["notes"]) and idx["workflow"][0].startswith("library_search once")
