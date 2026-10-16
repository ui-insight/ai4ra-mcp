"""icite, offline from three records captured from the API on 2026-10-16 (citation lists cut): a record slimmed to its
metrics, the summary across a set, the field list each tool asks for, a PMID the API does not hold said to be
missing (the API answers an unknown id by leaving it out or, for an overlong number, with another paper, so records are
matched to the ids asked for), the links of one paper, and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.icite import server as ic

PUBS = json.loads((Path(__file__).parent / "fixtures" / "icite" / "pubs.json").read_text(encoding="utf-8"))


def _api(monkeypatch, calls: list | None = None, answer=None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        if answer is not None:
            return answer
        wanted = set(params["pmids"].split(","))
        return {"data": [r for r in PUBS["data"] if str(r["pmid"]) in wanted]}

    monkeypatch.setattr(ic, "get_json", get_json)
    ic._cache._d.clear()
    return calls


def test_a_record_is_slimmed_to_its_metrics():
    r = ic.slim_metrics(next(r for r in PUBS["data"] if r["pmid"] == 33744490))
    assert r["title"].startswith("Coronavirus entry") and r["year"] == 2021 and r["journal"] == "Curr Opin Virol" and r["first_author"] == "Whittaker, Gary R" and r["author_count"] == 3
    assert r["citation_count"] == 50 and r["citations_per_year"] == 10.0 and r["relative_citation_ratio"] == 2.56 and r["nih_percentile"] == 80.2 and r["provisional"] is False
    assert r["is_research_article"] is False and r["translation"] == {"human": 0.33, "animal": 0.0, "molecular_cellular": 0.67, "apt": 0.25, "cited_by_clinical_article": False}
    assert r["link"] == "https://icite.od.nih.gov/analysis/result/?pmids=33744490"
    one = ic.slim_metrics(next(r for r in PUBS["data"] if r["pmid"] == 1))
    assert one["nih_percentile"] is None and one["relative_citation_ratio"] == 3.07


def test_the_summary_counts_the_set():
    papers = [ic.slim_metrics(r) for r in PUBS["data"]]
    s = ic.summarize(papers)
    assert s["papers"] == 3 and s["with_rcr"] == 3 and s["citations_total"] == 188 and s["rcr_median"] == 2.56 and s["rcr_at_or_above_1"] == 2 and s["provisional"] == 0
    assert ic.summarize([]) == {"papers": 0, "with_rcr": 0, "citations_total": 0}


async def test_metrics_ask_for_the_fields_and_say_what_is_missing(monkeypatch):
    calls = _api(monkeypatch)
    out = await ic.icite_metrics("33744490, 37391585,999999999999")
    url, params = calls[0]
    assert url == ic.API and params["pmids"] == "33744490,37391585,999999999999" and params["fl"].startswith("pmid,doi,title") and "cited_by" not in params["fl"]
    assert out["requested"] == 3 and out["returned"] == 2 and [p["pmid"] for p in out["papers"]] == [33744490, 37391585] and out["not_found"] == ["999999999999"]
    assert out["summary"]["papers"] == 2 and out["link"].endswith("?pmids=33744490,37391585,999999999999")
    await ic.icite_metrics("33744490, 37391585,999999999999")
    assert len(calls) == 1
    assert "error" in await ic.icite_metrics("x") and "error" in await ic.icite_metrics(",".join(["1"] * 101)) and "error" in await ic.icite_metrics("")


async def test_links_list_citing_and_cited_pmids(monkeypatch):
    calls = _api(monkeypatch)
    out = await ic.icite_links("33744490")
    assert calls[0][1] == {"pmids": "33744490", "fl": ic.LINK_FIELDS}
    assert out["cited_by_count"] == 6 and out["cited_by"][:2] == ["38555403", "35678602"] and out["references_count"] == 5 and out["cited_by_clinical_count"] == 0 and "note" not in out
    assert (await ic.icite_links("424242"))["error"].startswith("iCite does not hold")
    assert "error" in await ic.icite_links("PMC1")


async def test_a_body_without_data_is_reported(monkeypatch):
    _api(monkeypatch, answer={"error": "down"})
    out = await ic.icite_metrics("1")
    assert "did not return its data list" in out["error"] and out["upstream"] == ic.API


async def test_the_index_explains_the_ratio():
    out = await ic.icite_index()
    assert out["upstream"].startswith("NIH iCite at https://icite.od.nih.gov/api/pubs") and any("1.0 is the median" in n for n in out["notes"]) and out["limits"]["metrics"] == "100 PMIDs a call"
    assert {t.name for t in await ic.mcp.list_tools()} == {"icite_index", "icite_metrics", "icite_links"}
