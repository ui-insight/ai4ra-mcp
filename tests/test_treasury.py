"""treasury, offline from the 2026-09-30 quarter's table and two currencies' series captured from Fiscal Data on 2026-10-16:
a row slimmed with its rate as a number; a currency resolved against the quarter's names (exact, one partial, several,
none); the filters each tool sends; a conversion at the rate in effect on a date, dollars = amount / rate; and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.treasury import server as tr

FIX = Path(__file__).parent / "fixtures" / "treasury"
QUARTER = json.loads((FIX / "quarter.json").read_text(encoding="utf-8"))
SERIES = json.loads((FIX / "series.json").read_text(encoding="utf-8"))


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        p = dict(params or {})
        calls.append((url, p))
        f = p.get("filter", "")
        if p.get("fields") == "record_date":
            return {"data": [{"record_date": "2026-09-30"}], "meta": {"count": 1, "total-count": 11}}
        if f == "record_date:eq:2026-09-30":
            return QUARTER
        rows = SERIES["data"]
        if "country_currency_desc:eq:" in f:
            name = f.split("country_currency_desc:eq:")[1].split(",")[0]
            rows = [r for r in rows if r["country_currency_desc"] == name]
        for clause in f.split(","):
            if clause.startswith("effective_date:lte:"):
                rows = [r for r in rows if r["effective_date"] <= clause.split(":")[-1]]
            if clause.startswith("record_date:gte:"):
                rows = [r for r in rows if r["record_date"] >= clause.split(":")[-1]]
            if clause.startswith("record_date:lte:"):
                rows = [r for r in rows if r["record_date"] <= clause.split(":")[-1]]
        rows = sorted(rows, key=lambda r: r["record_date"], reverse=True)
        size = int(p.get("page[size]", 100))
        return {"data": rows[:size], "meta": {"count": min(size, len(rows)), "total-count": len(rows)}}

    monkeypatch.setattr(tr, "get_json", get_json)
    tr._cache._d.clear()
    return calls


def test_a_row_is_slimmed_with_its_rate_as_a_number():
    r = tr.slim(QUARTER["data"][0])
    assert r == {"currency": "Afghanistan-Afghani", "country": "Afghanistan", "unit": "Afghani", "record_date": "2026-09-30", "effective_date": "2026-09-30", "rate": 65.15}
    assert tr.slim({"exchange_rate": "n/a"})["rate"] is None


async def test_currencies_list_the_latest_quarter_and_match_words(monkeypatch):
    calls = _api(monkeypatch)
    out = await tr.treasury_currencies()
    assert out["record_date"] == "2026-09-30" and out["total"] == 168 and out["currencies"][0]["currency"] == "Afghanistan-Afghani"
    assert calls[0][1] == {"sort": "-record_date", "page[size]": 1, "fields": "record_date"} and calls[1][1]["filter"] == "record_date:eq:2026-09-30"
    out = await tr.treasury_currencies("euro")
    assert [c["currency"] for c in out["currencies"]] == ["Euro Zone-Euro"] and out["currencies"][0]["rate"] == 0.881
    assert (await tr.treasury_currencies("dollar"))["total"] > 5
    assert len(calls) == 2  # the quarter is cached


async def test_rates_resolve_the_currency_and_send_the_filters(monkeypatch):
    calls = _api(monkeypatch)
    out = await tr.treasury_rates(currency="canada", from_date="2025-01-01", rows=4)
    assert out["query"] == {"currency": "Canada-Dollar", "from_date": "2025-01-01"} and calls[-1][1]["filter"] == "country_currency_desc:eq:Canada-Dollar,record_date:gte:2025-01-01"
    assert calls[-1][1]["sort"] == "-record_date,country_currency_desc" and calls[-1][1]["page[size]"] == 4
    assert [r["record_date"] for r in out["rates"]] == ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31"] and out["total"] == 7 and "newest 4" in out["note"]
    out = await tr.treasury_rates(record_date="2026-09-30")
    assert calls[-1][1]["filter"] == "record_date:eq:2026-09-30"
    out = await tr.treasury_rates(currency="dollar")
    assert out["total"] == 0 and len(out["currencies_matched"]) > 5 and "pass one name in full" in out["error"]
    out = await tr.treasury_rates(currency="zzqx")
    assert out["currencies_matched"] == [] and "no currency matching" in out["error"]
    assert "error" in await tr.treasury_rates() and "error" in await tr.treasury_rates(currency="canada", from_date="last year")


async def test_convert_uses_the_rate_in_effect_on_the_date(monkeypatch):
    calls = _api(monkeypatch)
    out = await tr.treasury_convert(12500, "Euro Zone-Euro", "2026-05-15")
    assert calls[-1][1]["filter"] == "country_currency_desc:eq:Euro Zone-Euro,effective_date:lte:2026-05-15" and calls[-1][1]["sort"] == "-effective_date"
    assert out["rate"] == 0.87 and out["rate_record_date"] == "2026-03-31" and out["usd"] == round(12500 / 0.87, 2) and "12,500.00 Euro / 0.87 Euro per USD" in out["method"]
    out = await tr.treasury_convert("1000", "canada", "2026-10-01")
    assert out["currency"] == "Canada-Dollar" and out["rate"] == 1.418 and out["usd"] == 705.22
    assert "error" in await tr.treasury_convert("x", "canada") and "error" in await tr.treasury_convert(1, "dollar") and "error" in await tr.treasury_convert(1, "canada", "2026/10/01")
    out = await tr.treasury_convert(1, "canada", "2001-01-01")
    assert "no Treasury rate" in out["error"]


async def test_a_body_without_data_is_reported(monkeypatch):
    async def get_json(url, params=None, headers=None):
        return {"message": "down"}

    monkeypatch.setattr(tr, "get_json", get_json)
    tr._cache._d.clear()
    out = await tr.treasury_currencies()
    assert "did not return its data list" in out["error"] and out["upstream"] == tr.API


async def test_the_index_names_the_latest_quarter(monkeypatch):
    _api(monkeypatch)
    out = await tr.treasury_index()
    assert out["latest_quarter"] == "2026-09-30" and any("amount / rate" in n for n in out["notes"])
    assert {t.name for t in await tr.mcp.list_tools()} == {"treasury_index", "treasury_currencies", "treasury_rates", "treasury_convert"}
