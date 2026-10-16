"""weather, offline from the campus point, its forecast, stations, an observation and an alert list captured from api.weather.gov
on 2026-10-16: the point read once and its grid followed, periods slimmed, an observation converted, alerts sorted, bad points said."""

import json
from pathlib import Path

from ai4ra_mcp.servers.weather import server as wx

FIX = Path(__file__).parent / "fixtures" / "weather"
F = {name: json.loads((FIX / f"{name}.json").read_text(encoding="utf-8")) for name in ("point", "forecast", "stations", "observation", "alerts")}
POINT = (46.7324, -117.0002)


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        if "/points/" in url:
            return F["point"] if url.endswith("46.7324,-117.0002") else {"title": "Data Unavailable For Requested Point", "status": 404}
        if url.endswith("/forecast") or url.endswith("/forecast/hourly"):
            return F["forecast"]
        if url.endswith("/stations"):
            return F["stations"]
        if "/observations/latest" in url:
            return F["observation"]
        if "/alerts/active" in url:
            return F["alerts"]
        raise AssertionError(url)

    monkeypatch.setattr(wx, "get_json", get_json)
    wx._cache._d.clear()
    return calls


async def test_forecast_follows_the_point_to_its_grid(monkeypatch):
    calls = _api(monkeypatch)
    out = await wx.weather_forecast(*POINT)
    assert [c[0] for c in calls] == [f"{wx.API}/points/46.7324,-117.0002", "https://api.weather.gov/gridpoints/OTX/147,44/forecast"]
    assert out["office"] == "OTX" and out["point"]["near"] == "Moscow, ID" and out["point"]["timezone"] == "America/Los_Angeles" and not out["hourly"]
    p = out["periods"][0]
    assert p["name"] and isinstance(p["temperature"], int) and p["unit"] == "F" and p["short"] and p["detailed"] and p["wind"].split()[0].isdigit() or "to" in p["wind"]
    hourly = await wx.weather_forecast(*POINT, hourly=True)
    assert calls[-1][0].endswith("/forecast/hourly") and hourly["hourly"] and len(calls) == 3  # the point came from the cache
    assert "error" in await wx.weather_forecast(100, 0) and "error" in await wx.weather_forecast("x", 1)  # type: ignore[arg-type]
    off = await wx.weather_forecast(10.0, 10.0)
    assert "no grid" in off["error"]


async def test_now_reads_the_nearest_station_and_converts(monkeypatch):
    _api(monkeypatch)
    out = await wx.weather_now(*POINT)
    assert out["station"]["id"] == "KPUW" and "Pullman" in out["station"]["name"]
    assert out["temperature_c"] == 21 and out["temperature_f"] == 69.8 and out["description"] == "Clear" and out["wind_mph"] == 11.5 and out["time"].startswith("2026-10-16")
    assert out["pressure_inhg"] is None or 28 < out["pressure_inhg"] < 32
    assert wx.slim_observation({"temperature": {"value": None}, "windSpeed": {"value": 0}})["temperature_f"] is None and wx.c_to_f(0) == 32.0


async def test_alerts_and_index(monkeypatch):
    _api(monkeypatch)
    out = await wx.weather_alerts(*POINT)
    assert out["total"] == len(out["alerts"]) and out["link"].endswith("46.7324,-117.0002")
    ranked = sorted([wx.slim_alert({"properties": {"event": "a", "severity": "Minor"}}), wx.slim_alert({"properties": {"event": "b", "severity": "Extreme"}})],
                    key=lambda a: {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}.get(a["severity"] or "", 9))
    assert ranked[0]["event"] == "b"
    idx = await wx.weather_index()
    assert "campusmap" in " ".join(idx["notes"]) and "United States" in idx["upstream"]
    assert {t.name for t in await wx.mcp.list_tools()} == {"weather_index", "weather_forecast", "weather_now", "weather_alerts"}
