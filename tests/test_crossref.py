"""crossref: the API's shapes slimmed, the filter string a search builds, the JATS stripped from an abstract."""

from ai4ra_mcp.servers.crossref import server as cr

WORK = {"DOI": "10.1371/journal.pone.0266781", "type": "journal-article", "publisher": "Public Library of Science (PLoS)", "volume": "17", "issue": "4", "page": "e0266781",
        "is-referenced-by-count": 6, "title": ["6 month serologic response to the Pfizer-BioNTech COVID-19 vaccine among healthcare workers"], "container-title": ["PLOS ONE"],
        "URL": "https://doi.org/10.1371/journal.pone.0266781", "published": {"date-parts": [[2022, 4, 18]]}, "references-count": 9, "ISSN": ["1932-6203"],
        "author": [{"ORCID": "https://orcid.org/0000-0002-4748-3930", "authenticated-orcid": True, "given": "Jason", "family": "Cham", "sequence": "first", "affiliation": []},
                   {"given": "Sandeep", "family": "Pandey", "sequence": "additional", "affiliation": [{"name": "Scripps Research Institute"}]}],
        "funder": [{"DOI": "10.13039/100006108", "name": "National Center for Advancing Translational Sciences", "doi-asserted-by": "publisher", "award": ["UL1TR002550"]}],
        "license": [{"start": {"date-parts": [[2022, 4, 18]]}, "content-version": "vor", "URL": "http://creativecommons.org/licenses/by/4.0/"}],
        "abstract": "<jats:sec id=\"sec001\">\n<jats:title>Aim</jats:title>\n<jats:p>Healthcare workers (HCWs) were among the first group vaccinated.</jats:p></jats:sec>"}
FUNDER = {"id": "100000001", "location": "United States", "name": "National Science Foundation", "alt-names": ["NSF", "US NSF", "USNSF", "U.S. NSF", "US National Science Foundation", "Sixth"],
          "uri": "https://doi.org/10.13039/100000001", "replaces": [], "replaced-by": [], "tokens": ["national", "science", "foundation"]}


def test_slim_work_flattens_title_dates_authors_and_funders():
    w = cr.slim_work(WORK)
    assert w["title"].startswith("6 month") and w["container"] == "PLOS ONE" and w["year"] == 2022 and w["cited_by"] == 6
    assert w["authors"][0] == {"given": "Jason", "family": "Cham", "sequence": "first", "orcid": "https://orcid.org/0000-0002-4748-3930"}
    assert w["authors"][1]["affiliations"] == ["Scripps Research Institute"] and "orcid" not in w["authors"][1] and w["author_count"] == 2
    assert w["funders"] == [{"name": "National Center for Advancing Translational Sciences", "doi": "10.13039/100006108", "awards": ["UL1TR002550"]}]
    assert w["link"] == "https://doi.org/10.1371/journal.pone.0266781" and w["volume"] == "17" and w["page"] == "e0266781"


def test_year_falls_back_to_issued():
    assert cr._year({"issued": {"date-parts": [[2004]]}}) == 2004 and cr._year({"published": {"date-parts": [[None]]}}) is None


def test_slim_funder_has_registry_link_and_five_alt_names():
    f = cr.slim_funder(FUNDER)
    assert f["id"] == "100000001" and f["link"] == "https://doi.org/10.13039/100000001" and len(f["alt_names"]) == 5 and f["location"] == "United States"


async def test_works_search_builds_the_request(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        seen.update(params or {})
        return {"status": "ok", "message": {"total-results": 100, "items": [WORK] * 20}}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_works_search(query="wildfire smoke", author="Sheneman", funder_id="100000001", from_year="2020", to_year="2024", type="journal-article")
    assert seen["url"].endswith("/works") and seen["query"] == "wildfire smoke" and seen["query.author"] == "Sheneman" and seen["mailto"]
    assert seen["filter"] == "funder:100000001,from-pub-date:2020,until-pub-date:2024,type:journal-article" and seen["select"].startswith("DOI,title,author")
    assert seen["rows"] == 20 and seen["offset"] == 0 and out["returned"] == 20 and out["total"] == 100 and out["next_offset"] == 20
    cr._cache._d.clear()
    seen.clear()
    await cr.crossref_works_search(funder_id="https://doi.org/10.13039/100000001", rows=500)
    assert seen["filter"] == "funder:100000001" and seen["rows"] == 50 and "query" not in seen


async def test_work_strips_jats_and_validates_doi(monkeypatch):
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        return {"status": "ok", "message": WORK}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_work("https://doi.org/10.1371/journal.pone.0266781")
    assert seen["url"].endswith("/works/10.1371/journal.pone.0266781")
    assert out["abstract"] == "Aim Healthcare workers (HCWs) were among the first group vaccinated." and out["licenses"] == ["http://creativecommons.org/licenses/by/4.0/"]
    assert out["references_count"] == 9 and out["issn"] == ["1932-6203"]
    assert "error" in await cr.crossref_work("journal.pone.0266781")
    assert "error" in await cr.crossref_works_search(from_year="2020")
    assert "error" in await cr.crossref_works_search(query="x", funder_id="NSF")
    assert "error" in await cr.crossref_funders_search("")


async def test_funders_search(monkeypatch):
    async def fake_get_json(url, params=None, headers=None):
        assert url.endswith("/funders") and params["query"] == "National Science Foundation"
        return {"status": "ok", "message": {"total-results": 61, "items": [FUNDER]}}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_funders_search("National Science Foundation")
    assert out["total"] == 61 and out["funders"][0]["name"] == "National Science Foundation"


async def test_lists_tools():
    assert {t.name for t in await cr.mcp.list_tools()} == {"crossref_index", "crossref_works_search", "crossref_work", "crossref_updates", "crossref_funders_search"}


async def test_updates_join_the_record_with_the_notices_that_name_it(monkeypatch):
    """The Wakefield paper as Crossref holds it (2026-10-16): a 2004 correction and the 2010 retraction, both from Retraction Watch."""
    import json
    from pathlib import Path

    fix = Path(__file__).parent / "fixtures" / "crossref"
    work = json.loads((fix / "retracted_work.json").read_text(encoding="utf-8"))
    found = json.loads((fix / "updates_filter.json").read_text(encoding="utf-8"))
    seen = []

    async def fake_get_json(url, params=None, headers=None):
        seen.append((url, dict(params or {})))
        if url.endswith("/works"):
            return found
        return work if "11096" in url else {"status": "ok", "message": WORK}

    monkeypatch.setattr(cr, "get_json", fake_get_json)
    cr._cache._d.clear()
    out = await cr.crossref_updates("https://doi.org/10.1016/S0140-6736(97)11096-0")
    assert out["retracted"] and out["status"] == "retracted" and seen[1][1]["filter"] == "updates:10.1016/S0140-6736(97)11096-0"
    assert [(n["type"], n["date"], n["doi"], n["source"]) for n in out["notices"]] == [("correction", "2004-03-06", "10.1016/s0140-6736(04)15715-2", "retraction-watch"),
                                                                                        ("retraction", "2010-02-06", "10.1016/s0140-6736(10)60175-4", "retraction-watch")]
    assert out["this_work_updates"] == [] and "not a clean bill" in out["note"]
    # The same notices found only by the filter are not listed twice; one found only by the filter is added with its title.
    clean = await cr.crossref_updates(WORK["DOI"])
    assert not clean["retracted"] and clean["status"].startswith("no retraction") and clean["notices"] == []
    cr._cache._d.clear()
    found["message"]["items"][1]["DOI"] = "10.9999/other-notice"
    found["message"]["items"][1]["update-to"][0]["DOI"] = WORK["DOI"]
    found["message"]["items"][1]["update-to"][0]["type"] = "expression_of_concern"
    out = await cr.crossref_updates(WORK["DOI"])
    assert out["status"] == "has an expression of concern" and out["notices"][0]["doi"] == "10.9999/other-notice" and out["notices"][0]["title"].startswith("Retraction")
    assert "error" in await cr.crossref_updates("not a doi")
    w = cr.slim_updates(work["message"])
    assert w["retracted"] and len(w["updated_by"]) == 2 and (await cr.crossref_work("10.1016/S0140-6736(97)11096-0"))["retracted"]
    cr._cache._d.clear()
    retraction = dict(work["message"]["updated-by"][1], DOI="10.1016/s0140-6736(97)11096-0")  # update-to names the paper, not the notice
    notice = dict(work["message"], DOI="10.1016/s0140-6736(10)60175-4", title=["Retraction"], **{"update-to": [retraction]})
    notice.pop("updated-by")

    async def notice_json(url, params=None, headers=None):
        return {"status": "ok", "message": {"items": []}} if url.endswith("/works") else {"status": "ok", "message": notice}

    monkeypatch.setattr(cr, "get_json", notice_json)
    out = await cr.crossref_updates("10.1016/s0140-6736(10)60175-4")
    assert out["status"] == "this is itself a retraction notice for 10.1016/s0140-6736(97)11096-0" and not out["retracted"]
