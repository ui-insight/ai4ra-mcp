"""osm, offline from a Nominatim answer and a Valhalla walking route captured on 2026-10-16: a place and a route slimmed, the
parameters each call sends (the campus viewbox, the costing for each mode), the pacing between calls, a route the router
could not find, the attribution on every answer, and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.osm import server as om

FIX = Path(__file__).parent / "fixtures" / "osm"
GEOCODE = json.loads((FIX / "geocode.json").read_text(encoding="utf-8"))
ROUTE = json.loads((FIX / "route_walk.json").read_text(encoding="utf-8"))


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append(("GET", url, dict(params or {})))
        return GEOCODE if params["q"] != "nothing here" else []

    async def post_json(url, payload, headers=None):
        calls.append(("POST", url, payload))
        return ROUTE if payload["locations"][1]["lat"] != 0 else {"error": "No path could be found for input", "error_code": 442}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(om, "get_json", get_json)
    monkeypatch.setattr(om, "post_json", post_json)
    monkeypatch.setattr(om.asyncio, "sleep", no_sleep)
    om._cache._d.clear()
    return calls


def test_a_place_and_a_route_are_slimmed():
    p = om.slim_place(GEOCODE[0])
    assert p["name"] == "Kibbie Dome" and p["kind"] == "stadium" and p["lat"] == 46.7262411 and p["lon"] == -117.0174374 and p["address"]["road"] == "Stadium Drive" and p["link"] == "https://www.openstreetmap.org/way/245242112"
    r = om.slim_route(ROUTE["trip"], "walk")
    assert r["miles"] == 0.42 and r["minutes"] == 8.5 and len(r["steps"]) == 13 and r["steps"][0] == {"instruction": "Walk west on the walkway.", "miles": 0.027} and r["bounds"]["min_lat"] == 46.725502


async def test_geocode_sends_the_viewbox_and_says_when_nothing_matches(monkeypatch):
    calls = _api(monkeypatch)
    out = await om.osm_geocode("Kibbie Dome, Moscow, Idaho", rows=3)
    _, url, p = calls[-1]
    assert url == om.NOMINATIM and p == {"q": "Kibbie Dome, Moscow, Idaho", "format": "jsonv2", "limit": 3, "addressdetails": 1, "viewbox": om.CAMPUS_VIEWBOX, "bounded": 0}
    assert out["total"] == 1 and out["places"][0]["name"] == "Kibbie Dome" and out["attribution"].startswith("Data © OpenStreetMap")
    await om.osm_geocode("Eiffel Tower", near_campus=False)
    assert "viewbox" not in calls[-1][2]
    none = await om.osm_geocode("nothing here")
    assert none["total"] == 0 and "campusmap_search" in none["note"]
    assert "error" in await om.osm_geocode("ab")
    await om.osm_geocode("Kibbie Dome, Moscow, Idaho", rows=3)
    assert len(calls) == 3  # cached


async def test_route_sends_the_costing_and_reads_the_trip(monkeypatch):
    calls = _api(monkeypatch)
    out = await om.osm_route(46.72561, -117.0117, 46.72624, -117.0174)
    _, url, payload = calls[-1]
    assert url == om.VALHALLA and payload["costing"] == "pedestrian" and payload["units"] == "miles" and payload["locations"] == [{"lat": 46.72561, "lon": -117.0117}, {"lat": 46.72624, "lon": -117.0174}]
    assert out["mode"] == "walk" and out["miles"] == 0.42 and out["minutes"] == 8.5 and out["steps"][2]["instruction"] == "Turn left onto the walkway." and "fossgis_valhalla_foot" in out["link"]
    await om.osm_route(46.72561, -117.0117, 46.72624, -117.0174, mode="bike")
    assert calls[-1][2]["costing"] == "bicycle"
    await om.osm_route(46.72561, -117.0117, 46.72624, -117.0174, mode="drive")
    assert calls[-1][2]["costing"] == "auto"
    lost = await om.osm_route(46.72561, -117.0117, 0, 0)
    assert "No path could be found" in lost["error"]
    assert "error" in await om.osm_route(46.7, -117.0, 46.7, -117.0, mode="fly") and "error" in await om.osm_route("x", 1, 2, 3) and "error" in await om.osm_route(91, 0, 0, 0)


async def test_calls_are_paced_a_second_apart(monkeypatch):
    calls = _api(monkeypatch)
    waits = []

    async def sleep(s):
        waits.append(s)

    monkeypatch.setattr(om.asyncio, "sleep", sleep)
    om._last_call = om.time.monotonic()
    await om.osm_geocode("Kibbie Dome, Moscow, Idaho")
    assert waits and 0.9 < waits[0] <= 1.05


async def test_the_index_states_the_terms():
    out = await om.osm_index()
    assert any("One request a second" in n for n in out["notes"]) and any("Attribution is required" in n for n in out["notes"]) and any("campusmap_search" in w for w in out["workflow"])
    assert {t.name for t in await om.mcp.list_tools()} == {"osm_index", "osm_geocode", "osm_route"}
