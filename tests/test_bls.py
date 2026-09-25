"""bls: the series shape slimmed newest first, the body sent to v1 without a key and v2 with one, the message list
passed through, and the input checks."""

from ai4ra_mcp.servers.bls import server as b

CPI = {"seriesID": "CUUR0000SA0", "data": [
    {"year": "2026", "period": "M08", "periodName": "August", "latest": "true", "value": "334.980", "footnotes": [{}]},
    {"year": "2026", "period": "M07", "periodName": "July", "value": "333.918", "footnotes": [{}]},
    {"year": "2025", "period": "M13", "periodName": "Annual", "value": "321.943", "footnotes": [{}]},
    {"year": "2025", "period": "M08", "periodName": "August", "value": "323.976", "footnotes": [{}]},
]}
ECI = {"seriesID": "CIU1010000000000A", "catalog": {"series_title": "Total compensation for All Civilian workers, 12-month percent change"}, "data": [
    {"year": "2026", "period": "Q02", "periodName": "2nd Quarter", "latest": "true", "value": "3.4", "footnotes": [{}]},
    {"year": "2026", "period": "Q01", "periodName": "1st Quarter", "value": "3.4", "footnotes": [{}]},
]}
OK_BODY = {"status": "REQUEST_SUCCEEDED", "responseTime": 91, "message": [], "Results": {"series": [CPI, ECI]}}
MISSING_BODY = {"status": "REQUEST_SUCCEEDED", "responseTime": 80, "message": ["Series does not exist for Series PCU5417--5417--"],
                "Results": {"series": [{"seriesID": "PCU5417--5417--", "data": []}]}}
FAILED_BODY = {"status": "REQUEST_NOT_PROCESSED", "responseTime": 10, "message": ["Daily threshold reached"], "Results": {}}


def test_series_slims_newest_first_with_floats_and_link():
    s = b.slim_series(CPI)
    assert s["id"] == "CUUR0000SA0" and s["title"] is None and s["returned"] == 4 and s["link"].endswith("/timeseries/CUUR0000SA0")
    assert [(x["year"], x["period"]) for x in s["data"]] == [("2026", "M08"), ("2026", "M07"), ("2025", "M13"), ("2025", "M08")]
    assert s["data"][0] == {"year": "2026", "period": "M08", "period_name": "August", "value": 334.98, "latest": True}
    assert s["data"][1]["latest"] is False
    e = b.slim_series(ECI)
    assert e["title"].startswith("Total compensation") and e["data"][0]["value"] == 3.4
    assert "note" in b.slim_series({"seriesID": "X", "data": []})


def test_common_series_carry_links_and_no_ppi():
    ids = [s["id"] for s in b.COMMON_SERIES]
    assert "CUUR0000SA0" in ids and "CIU1010000000000A" in ids and "CUUR0400SA0" in ids and "PCU5417--5417--" not in ids
    assert len(ids) == len(set(ids))


async def test_without_a_key_v1_is_used_and_no_key_is_sent(monkeypatch):
    monkeypatch.delenv(b.KEY_ENV, raising=False)
    seen = {}

    async def fake_post_json(url, payload, headers=None):
        seen["url"], seen["payload"] = url, payload
        return OK_BODY

    monkeypatch.setattr(b, "post_json", fake_post_json)
    b._cache._d.clear()
    out = await b.bls_series("cuur0000sa0, CIU1010000000000A", "2025", "2026", annual_average=True)
    assert seen["url"] == "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    assert seen["payload"] == {"seriesid": ["CUUR0000SA0", "CIU1010000000000A"], "startyear": "2025", "endyear": "2026", "annualaverage": True}
    assert out["api_version"] == "v1" and out["returned"] == 2 and "message" not in out and "error" not in out
    idx = await b.bls_index()
    assert idx["in_use"]["version"] == "v1" and idx["in_use"]["queries_a_day"] == 25 and idx["key"]["on_this_request"] is False


async def test_with_a_key_v2_is_used_with_the_key_in_the_body(monkeypatch):
    monkeypatch.setenv(b.KEY_ENV, "reg-key")
    seen = {}

    async def fake_post_json(url, payload, headers=None):
        seen["url"], seen["payload"] = url, payload
        return OK_BODY

    monkeypatch.setattr(b, "post_json", fake_post_json)
    b._cache._d.clear()
    out = await b.bls_series("CUUR0000SA0")
    assert seen["url"] == "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    assert seen["payload"] == {"seriesid": ["CUUR0000SA0"], "catalog": True, "registrationkey": "reg-key"}
    assert out["api_version"] == "v2"
    assert "reg-key" not in repr(list(b._cache._d))
    idx = await b.bls_index()
    assert idx["in_use"]["version"] == "v2" and idx["key"]["on_this_request"] is True


async def test_message_list_passes_through_and_a_failed_status_is_an_error(monkeypatch):
    monkeypatch.delenv(b.KEY_ENV, raising=False)
    bodies = [MISSING_BODY, FAILED_BODY]

    async def fake_post_json(url, payload, headers=None):
        return bodies.pop(0)

    monkeypatch.setattr(b, "post_json", fake_post_json)
    b._cache._d.clear()
    out = await b.bls_series("PCU5417--5417--")
    assert out["message"] == ["Series does not exist for Series PCU5417--5417--"] and out["series"][0]["returned"] == 0 and "error" not in out
    b._cache._d.clear()
    out = await b.bls_series("CUUR0000SA0")
    assert "Daily threshold" in out["error"] and out["message"] == ["Daily threshold reached"] and not b._cache._d


async def test_bad_input(monkeypatch):
    monkeypatch.delenv(b.KEY_ENV, raising=False)
    assert "error" in await b.bls_series("")
    assert "error" in await b.bls_series("CUUR0000SA0", "2020")
    assert "error" in await b.bls_series("CUUR0000SA0", "2010", "2026")
    assert "error" in await b.bls_series("CUUR0000SA0", "2026", "2025")
    assert "error" in await b.bls_series("CUUR0000SA0", "twenty", "2026")
    assert "error" in await b.bls_series(",".join(f"S{i}" for i in range(26)))


async def test_common_series_tool_and_lists_tools():
    out = await b.bls_common_series()
    assert out["returned"] == len(b.COMMON_SERIES) and all(s["link"].startswith("https://data.bls.gov/timeseries/") for s in out["series"])
    assert {t.name for t in await b.mcp.list_tools()} == {"bls_index", "bls_series", "bls_common_series"}
