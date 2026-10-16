"""scorecard, offline from the University of Idaho's record and an Idaho search captured on 2026-10-16: a row and a
record slimmed with codes named and shares as percentages, the parameters a search sends, the key as a header, a
missing key, and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.scorecard import server as sc

FIX = Path(__file__).parent / "fixtures" / "scorecard"
PAGES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        if params.get("id") == 142285:
            return PAGES["school"]
        if params.get("id"):
            return {"metadata": {"total": 0}, "results": []}
        return PAGES["search"]

    monkeypatch.setattr(sc, "get_json", get_json)
    monkeypatch.setenv(sc.KEY_ENV, "k-scorecard")
    sc._cache._d.clear()
    return calls


def test_a_record_is_slimmed_with_codes_named():
    r = sc.slim_school(PAGES["school"]["results"][0])
    assert r["id"] == 142285 and r["name"] == "University of Idaho" and r["control"] == "public" and r["predominant_degree"] == "bachelor's" and r["highest_degree"] == "graduate"
    assert r["carnegie_codes"] == {"basic": 16, "undergraduate": 13, "size_setting": 13} and r["locale_code"] == 32 and r["accreditor"].startswith("Northwest Commission")
    assert r["minority_serving"]["historically_black"] is False and r["minority_serving"]["tribal"] is False and r["minority_serving"]["hispanic"] is None
    assert r["students"]["undergraduates"] == 7747 and r["students"]["graduate_students"] == 2712 and r["students"]["race_ethnicity_pct"]["hispanic"] == 10.1 and r["aid"]["pell_grant_rate_pct"] == 27.9
    assert r["admission_rate_pct"] == 75.5 and r["cost"]["tuition_in_state"] == 9400 and r["cost"]["avg_net_price"] == 15321 and r["outcomes"]["median_earnings_10_years_after_entry"] == 58095
    assert r["link"] == "https://collegescorecard.ed.gov/school/?142285"


async def test_search_sends_filters_and_the_key_as_a_header(monkeypatch):
    calls = _api(monkeypatch)
    out = await sc.scorecard_search(name="Idaho", state="id", control="public", predominant_degree="bachelor's", rows=10)
    url, p, h = calls[-1]
    assert url == sc.BASE and h == {"X-Api-Key": "k-scorecard"} and p["school.name"] == "Idaho" and p["school.state"] == "ID" and p["school.ownership"] == 1 and p["school.degrees_awarded.predominant"] == 3 and p["per_page"] == 10 and p["fields"] == sc.LIST_FIELDS
    assert out["total"] == 10 and any(i["name"] == "University of Idaho" and i["control"] == "public" for i in out["institutions"]) and "next_page" not in out
    assert "k-scorecard" not in repr(list(sc._cache._d.keys()))
    assert "error" in await sc.scorecard_search() and "error" in await sc.scorecard_search(name="x", control="state") and "error" in await sc.scorecard_search(name="x", predominant_degree="doctorate")


async def test_one_school_and_a_missing_one(monkeypatch):
    _api(monkeypatch)
    out = await sc.scorecard_school(142285)
    assert out["name"] == "University of Idaho" and out["dictionary"] == sc.DICTIONARY
    assert (await sc.scorecard_school(1))["error"] == "no institution 1 in the College Scorecard" and "error" in await sc.scorecard_school("x")


async def test_a_missing_key_is_refused(monkeypatch):
    _api(monkeypatch)
    monkeypatch.delenv(sc.KEY_ENV, raising=False)
    assert (await sc.scorecard_search(name="Idaho"))["error"].startswith("no API key on this request") and (await sc.scorecard_school(142285))["error"].startswith("no API key")
    idx = await sc.scorecard_index()
    assert idx["key"]["required"] is True and any("null for every institution" in n for n in idx["notes"])
    assert {t.name for t in await sc.mcp.list_tools()} == {"scorecard_index", "scorecard_search", "scorecard_school"}
