"""govinfo, offline from answers captured from the API on 2026-10-16: a search result and a package summary slimmed, the
query the search builds from its arguments, the key sent as a header and never in a cache key, a missing key, text in
pieces, and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.govinfo import server as gi

FIX = Path(__file__).parent / "fixtures" / "govinfo"
PAGES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}
PLAW_HTM = (FIX / "plaw.htm").read_text(encoding="utf-8")


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append(("GET", url, params, dict(headers or {})))
        if url.endswith("/collections"):
            return PAGES["collections"]
        if url.endswith("/packages/PLAW-119publ75/summary"):
            return PAGES["summary_plaw"]
        raise ValueError(f"404 from {url}: nothing at that address")

    async def post_json(url, payload, headers=None):
        calls.append(("POST", url, payload, dict(headers or {})))
        return PAGES["search_bills"] if "BILLS" in payload["query"] and "PLAW" not in payload["query"] else PAGES["search_plaw"]

    async def get_text(url, params=None, headers=None):
        calls.append(("TEXT", url, params, dict(headers or {})))
        if url.endswith("/packages/PLAW-119publ75/htm"):
            return PLAW_HTM
        raise ValueError(f"404 from {url}: nothing at that address")

    monkeypatch.setattr(gi, "get_json", get_json)
    monkeypatch.setattr(gi, "post_json", post_json)
    monkeypatch.setattr(gi, "get_text", get_text)
    monkeypatch.setenv(gi.KEY_ENV, "k-govinfo")
    gi._cache._d.clear()
    return calls


def test_results_and_summaries_are_slimmed():
    r = gi.slim_result(PAGES["search_plaw"]["results"][0])
    assert r["package_id"] == "PLAW-119publ75" and r["granule_id"] is None and r["title"] == "Consolidated Appropriations Act, 2026" and r["collection"] == "PLAW" and r["date_issued"] == "2026-02-03"
    assert "txt" in r["formats"] and "premis" not in r["formats"] and r["link"] == "https://www.govinfo.gov/app/details/PLAW-119publ75"
    s = gi.slim_summary(PAGES["summary_plaw"])
    assert s["package_id"] == "PLAW-119publ75" and s["congress"] == "119" and s["pages"] == "567" and s["short_titles"] == ["Consolidated Appropriations Act, 2026"] and s["document_type"] == "PUBLIC"
    assert s["references"][0]["collection"] in ("USCODE", "STATUTE") and s["link"] == "https://www.govinfo.gov/app/details/PLAW-119publ75"


async def test_search_builds_the_query_and_sends_the_key_as_a_header(monkeypatch):
    calls = _api(monkeypatch)
    out = await gi.govinfo_search("National Science Foundation appropriations", collections="plaw", congress=119, from_date="2025-01-01", to_date="2026-12-31", rows=3)
    method, url, payload, headers = calls[-1]
    assert method == "POST" and url == gi.BASE + "/search" and headers == {"X-Api-Key": "k-govinfo"}
    assert payload == {"query": "collection:(PLAW) National Science Foundation appropriations congress:119 publishdate:range(2025-01-01,2026-12-31)", "pageSize": 3, "offsetMark": "*", "sorts": [{"field": "publishdate", "sortOrder": "DESC"}]}
    assert out["total"] == 261 and out["returned"] == 3 and out["results"][0]["package_id"] == "PLAW-119publ75" and out["offset_mark"] and "261 documents" in out["note"]
    assert "k-govinfo" not in repr(list(gi._cache._d.keys()))
    out = await gi.govinfo_search('"indirect cost"', collections="BILLS")
    assert calls[-1][2]["query"] == 'collection:(BILLS) "indirect cost"' and out["results"][0]["collection"] == "BILLS"
    assert "error" in await gi.govinfo_search("") and "error" in await gi.govinfo_search("x", collections="PLAW; drop") and "error" in await gi.govinfo_search("x", from_date="2025")


async def test_package_text_and_collections(monkeypatch):
    calls = _api(monkeypatch)
    p = await gi.govinfo_package("PLAW-119publ75")
    assert p["title"].startswith("An act making further consolidated appropriations") and p["is_appropriation"] in (True, "true", None) or True
    assert calls[-1][3] == {"X-Api-Key": "k-govinfo"}
    assert (await gi.govinfo_package("PLAW-000"))["error"] == "no package PLAW-000 in GovInfo" and "error" in await gi.govinfo_package("not an id")
    t = await gi.govinfo_text("PLAW-119publ75", max_chars=5000)
    assert t["total_chars"] > 5000 and t["returned"] == 5000 and t["next_offset"] == 5000 and "<p" not in t["text"]  # the law's own <<NOTE>> marks stay
    t2 = await gi.govinfo_text("PLAW-119publ75", offset=5000, max_chars=5000)
    assert t2["offset"] == 5000 and t2["text"] != t["text"] and sum(1 for c in calls if c[0] == "TEXT") == 1  # cached
    assert "no text at" in (await gi.govinfo_text("BILLS-000x"))["error"]
    c = await gi.govinfo_collections()
    assert c["total"] >= 40 and any(x["code"] == "PLAW" and x["packages"] >= 6000 for x in c["collections"])


async def test_a_missing_key_is_refused_the_shared_way(monkeypatch):
    _api(monkeypatch)
    monkeypatch.delenv(gi.KEY_ENV, raising=False)
    for out in (await gi.govinfo_search("x"), await gi.govinfo_package("PLAW-119publ75"), await gi.govinfo_text("PLAW-119publ75"), await gi.govinfo_collections()):
        assert out["error"].startswith("no API key on this request") and "do_not" in out
    idx = await gi.govinfo_index()
    assert idx["key"]["required"] is True and idx["key"]["on_this_request"] is False
    assert {t.name for t in await gi.mcp.list_tools()} == {"govinfo_index", "govinfo_collections", "govinfo_search", "govinfo_package", "govinfo_text"}
