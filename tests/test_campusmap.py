"""campusmap, offline from the map's categories and a cut of its locations captured through Concept3D's API on 2026-10-16: the
working categories hidden, a building's number and kind, a search by words and by category, what is near a point, one place
with its entrances and parking, the categories counted, the key sent as the map page sends it, and a changed answer said."""

import json
from pathlib import Path

from ai4ra_mcp.servers.campusmap import server as cm

FIX = Path(__file__).parent / "fixtures" / "campusmap"
CATS = json.loads((FIX / "categories.json").read_text(encoding="utf-8"))
LOCS = json.loads((FIX / "locations.json").read_text(encoding="utf-8"))


def _api(monkeypatch, calls: list | None = None, broken: bool = False):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        if broken:
            return {"error": "Unauthorized"}
        return CATS if url.endswith("/categories") else LOCS

    monkeypatch.setattr(cm, "get_json", get_json)
    cm._cache._d.clear()
    return calls


async def test_the_map_is_read_once_with_its_key_and_working_categories_hidden(monkeypatch):
    calls = _api(monkeypatch)
    data = await cm._data()
    assert [c[0] for c in calls] == [cm.API + "/categories", cm.API + "/locations"] and all(c[1] == {"map": 2155, "key": cm.MAP_KEY} for c in calls)
    cats = {p["category"] for p in data["places"]}
    assert "QC Draft" not in cats and "Archive" not in cats and "A" in cats and "Accessible Entrance" in cats
    admin = next(p for p in data["places"] if p["name"] == "Administration Building")
    assert admin["kind"] == "building" and admin["building_number"] == "1" and admin["lat"] == 46.725624 and admin["link"].startswith(cm.SITE + "#!m/")
    await cm._data()
    assert len(calls) == 2


async def test_search_by_words_and_category(monkeypatch):
    _api(monkeypatch)
    out = await cm.campusmap_search("memorial gym")
    assert out["total"] == 1 and out["places"][0]["name"] == "Memorial Gym" and "Activity & Events Locations" in out["places"][0]["categories"]  # one building, several categories, one row
    two = cm.collapse([{"id": 1, "name": "Gym", "category": "Athletics", "kind": "athletics", "lat": 46.1, "lng": -117.1, "building_number": None, "link": "x"},
                       {"id": 2, "name": "Gym", "category": "L - M", "kind": "building", "lat": 46.1, "lng": -117.1, "building_number": "7", "link": "y"},
                       {"id": 3, "name": "Gym N", "category": "Door Information", "kind": "door information", "lat": 46.1001, "lng": -117.1, "building_number": None, "link": "z"}])
    assert len(two) == 2 and two[0]["kind"] == "building" and two[0]["id"] == 2 and two[0]["building_number"] == "7" and sorted(two[0]["categories"]) == ["Athletics", "L - M"]
    out = await cm.campusmap_search("pitman")
    assert out["places"][0]["name"] == "Pitman Center (Bruce M.)"
    out = await cm.campusmap_search(category="building", rows=5)
    assert out["total"] > 20 and len(out["places"]) == 5 and all(p["kind"] == "building" for p in out["places"]) and "buildings first" in out["note"]
    out = await cm.campusmap_search("administration", category="accessible")
    assert out["total"] >= 1 and all(p["category"] == "Accessible Entrance" for p in out["places"])
    assert (await cm.campusmap_search("zzqx"))["total"] == 0 and "error" in await cm.campusmap_search()


async def test_near_and_place(monkeypatch):
    _api(monkeypatch)
    near = await cm.campusmap_near(46.725624, -117.010979, category="accessible", radius_m=100)
    assert near["total"] >= 1 and near["places"][0]["category"] == "Accessible Entrance" and near["places"][0]["distance_m"] < 100 and near["places"] == sorted(near["places"], key=lambda p: p["distance_m"])
    everything = await cm.campusmap_near(46.725624, -117.010979, radius_m=50)
    assert any(p["name"] == "Administration Building" for p in everything["places"])
    assert "error" in await cm.campusmap_near(100, 0) and "error" in await cm.campusmap_near("x", "y")
    admin = (await cm.campusmap_search("administration building", category="building"))["places"][0]
    place = await cm.campusmap_place(admin["id"])
    assert place["name"] == "Administration Building" and place["accessible_entrances"] and all(e["distance_m"] <= 150 for e in place["accessible_entrances"])
    assert "error" in await cm.campusmap_place("000")
    assert round(cm.distance_m(46.725624, -117.010979, 46.725624, -117.010979)) == 0 and 100 < cm.distance_m(46.7256, -117.0110, 46.7266, -117.0110) < 120


async def test_categories_and_a_broken_key(monkeypatch):
    _api(monkeypatch)
    cats = await cm.campusmap_categories()
    assert cats["total"] >= 10 and any(c["category"] == "A" and c["kind"] == "building" for c in cats["categories"]) and not any("QC" in c["category"] for c in cats["categories"])
    _api(monkeypatch, broken=True)
    out = await cm.campusmap_search("library")
    assert "rotated" in out["error"] and "osm_geocode" in out["error"]
    idx = await cm.campusmap_index()
    assert idx["buildings"] is None and "osm_route" in " ".join(idx["workflow"])
    assert {t.name for t in await cm.mcp.list_tools()} == {"campusmap_index", "campusmap_categories", "campusmap_search", "campusmap_near", "campusmap_place"}
