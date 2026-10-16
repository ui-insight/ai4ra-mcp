"""datacite, offline from records captured from the API on 2026-10-16 (descriptions and lists cut): a record slimmed with
its creators' affiliations, funding references and related identifiers; the parameters each search sends (the ROR
filter, the funder filter, the award number as a query clause, the type, the year range, the sort when no words are
given); one DOI in full; a Crossref or missing DOI said; and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.datacite import server as dc

FIX = Path(__file__).parent / "fixtures" / "datacite"
PAGES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        p = dict(params or {})
        calls.append((url, p))
        if url.endswith("/dois/10.3886/e249735v1"):
            return PAGES["one"]
        if url.endswith("/dois/10.1038/nothing"):
            raise ValueError(f"404 from {url}: nothing at that address")
        if "funder-id" in p:
            return PAGES["funder"]
        if "query" in p and "awardNumber" not in p["query"]:
            return PAGES["query"]
        return PAGES["ror"]

    monkeypatch.setattr(dc, "get_json", get_json)
    dc._cache._d.clear()
    return calls


def test_a_record_is_slimmed_with_people_funding_and_relations():
    r = dc.slim(PAGES["ror"]["data"][0])
    assert r["doi"] == "10.60841/000000328" and r["publisher"] == "University of Idaho" and r["year"] == 2026 and r["resource_type"] == "Other"
    assert r["creators"][0]["name"] == "Kamyabi, Mostafa" and r["creators"][0]["affiliations"] == ["University of Idaho (United States, Moscow) - UI"] and r["creator_count"] >= 1
    assert r["related"] == [{"relation": "IsSupplementTo", "id": "10.3168/jds.2026-29100", "type": "DOI"}] and "cc-by-4.0" in r["rights"]
    assert r["url"].startswith("https://verso.uidaho.edu/") and r["link"] == "https://doi.org/10.60841/000000328" and r["description"].endswith(" …") or len(r["description"]) <= 400
    f = dc.slim(PAGES["funder"]["data"][0])
    assert f["funding"][0] == {"funder": "National Science Foundation", "funder_id": "https://doi.org/10.13039/100000001", "award_number": "2315760", "award_title": None}
    one = dc.slim(PAGES["one"]["data"], full=True)
    assert one["resource_type"] == "Dataset" and one["resource_type_detail"].startswith("geographic information system") and "Oregon" in one["geolocations"] and one["counts"] == {"citations": 0, "views": 0, "downloads": 0}
    assert "subjects" in one and "formats" in one and "subjects" not in dc.slim(PAGES["one"]["data"])


async def test_search_sends_the_filters_and_the_award_as_a_query_clause(monkeypatch):
    calls = _api(monkeypatch)
    out = await dc.datacite_search(affiliation_ror="03hbp5t65", resource_type="Dataset", from_year="2024", to_year="2025", per_page=3)
    url, p = calls[-1]
    assert url == dc.API and p == {"affiliation-id": "https://ror.org/03hbp5t65", "affiliation": "true", "resource-type-id": "dataset", "published": "2024,2025", "sort": "-created", "page[size]": 3, "page[number]": 1}
    assert out["total"] == 933 and out["returned"] == 3 and out["next_page"] == 2 and out["query"] == {"affiliation_ror": "https://ror.org/03hbp5t65", "resource_type": "dataset", "years": "2024,2025"}
    await dc.datacite_search(query="wildfire smoke", award_number="1754803", funder_id="https://doi.org/10.13039/100000001", page=2)
    p = calls[-1][1]
    assert p["query"] == '(wildfire smoke) AND fundingReferences.awardNumber:"1754803"' and p["funder-id"] == "10.13039/100000001" and "sort" not in p and p["page[number]"] == 2
    await dc.datacite_search(award_number="1754803")
    assert calls[-1][1]["query"] == 'fundingReferences.awardNumber:"1754803"' and "affiliation-id" not in calls[-1][1]
    assert "error" in await dc.datacite_search() and "error" in await dc.datacite_search(from_year="2020")
    assert "error" in await dc.datacite_search(affiliation_ror="University of Idaho") and "error" in await dc.datacite_search(funder_id="NSF")
    assert "error" in await dc.datacite_search(query="x", resource_type="spreadsheet") and "error" in await dc.datacite_search(query="x", from_year="recent")


async def test_one_doi_in_full_and_the_ones_that_are_not_there(monkeypatch):
    calls = _api(monkeypatch)
    out = await dc.datacite_doi("https://doi.org/10.3886/e249735v1")
    assert calls[-1][0] == dc.API + "/10.3886/e249735v1" and out["resource_type"] == "Dataset" and out["publisher"].startswith("ICPSR") and out["url"].startswith("https://www.datalumos.org/")
    out = await dc.datacite_doi("doi:10.1038/nothing")
    assert out["error"].startswith("no DataCite record for 10.1038/nothing") and "crossref" in out["error"]
    assert "error" in await dc.datacite_doi("not a doi")


async def test_a_body_without_data_is_reported(monkeypatch):
    async def get_json(url, params=None, headers=None):
        return {"errors": [{"status": "500"}]}

    monkeypatch.setattr(dc, "get_json", get_json)
    dc._cache._d.clear()
    assert "did not return its data list" in (await dc.datacite_search(query="x"))["error"]
    assert "did not return a record" in (await dc.datacite_doi("10.1234/x"))["error"]
    assert dc._person({"name": "Old, Deposit", "affiliation": ["University of Idaho", ""]}) == {"name": "Old, Deposit", "orcid": None, "affiliations": ["University of Idaho"]}


async def test_the_index_says_what_datacite_holds():
    out = await dc.datacite_index()
    assert out["upstream"].startswith("DataCite at https://api.datacite.org/dois") and any("Crossref DOIs" in n for n in out["notes"])
    assert {t.name for t in await dc.mcp.list_tools()} == {"datacite_index", "datacite_search", "datacite_doi"}
