"""campusmap: the University of Idaho campus map, the places the university's own map marks, with their coordinates.

Upstream: the university's campus map is Concept3D map 2155 (map.concept3d.com/?id=2155, embedded at uidaho.edu).
Concept3D's JSON API, https://api.concept3d.com/locations?map=2155 and /categories?map=2155, answers with the key the
map page itself sends from its public script, a client key served to every visitor of the map and good for reading
the map's points; it is Concept3D's, not the person's, is held here as the map page holds it, and when Concept3D
rotates it the osm server's geocoding stands in (decided 2026-10-16, #45). About 3,600 points in 130 categories:
323 buildings in the alphabetical categories (A, B - D ... T - Z), each with its building number; building
addresses; departments and colleges; accessible entrances, automatic doors and card-swipe doors; restrooms,
elevators and nursing rooms; parking by kind, bike racks, EV charging and transit stops; dining, athletics, health,
study spots, memorials, trees. The map editors' working categories (QC, drafts, labels, traces) are not shown. The
map carries no routing of its own; its directions run on Mapbox under Concept3D's keys, so a route between two
places here is the osm server's osm_route, given two points from this one. Points are cached a day.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.given import given
from ai4ra_mcp.common.http import DAY, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
MAP_ID = 2155
API = "https://api.concept3d.com"
SITE = f"https://map.concept3d.com/?id={MAP_ID}"
# The map page's own client key, read from https://map.concept3d.com/js/index.js on 2026-10-16; it reads the map's points and nothing else here.
MAP_KEY = "0001085cc708b9cef47080f064612ca5"
BUILDING_CATEGORIES = {"A", "B - D", "E - G", "H - K", "L - M", "N - R", "S", "T - Z"}
_HIDDEN = re.compile(r"QC|Draft|Archive|Render Boundary|Missing Models|Round #|Completed|Edits|Updates|Labels|Interior Data|Interior Icons|Lot Traces|Preview|Overlay|3D Structure", re.I)
ROWS, MAX_ROWS = 20, 200
_cache = TTLCache()

mcp = MCPServer(
    "campusmap",
    instructions="The University of Idaho campus map (Concept3D): places by name or category with coordinates and building numbers (campusmap_search), what is near a point (campusmap_near), one place with its accessible entrances and parking (campusmap_place), the categories (campusmap_categories). A route between two places is the osm server's osm_route with the points from here. No key of the person's. Read campusmap_index first.",
)


async def _data() -> dict:
    """{'categories': {id: name}, 'places': [...]} from the map's two lists, cached a day."""
    async def make():
        cats, locs = await get_json(f"{API}/categories", {"map": MAP_ID, "key": MAP_KEY}), await get_json(f"{API}/locations", {"map": MAP_ID, "key": MAP_KEY})
        if not isinstance(cats, list) or not isinstance(locs, list):
            raise ValueError("Concept3D did not return the map's categories and locations (the key may have been rotated; the osm server's osm_geocode stands in)")
        names = {c.get("catId"): (c.get("name") or "").strip() for c in cats}
        places = []
        for l in locs:
            cat = names.get(l.get("catId"), "")
            if not cat or _HIDDEN.search(cat):
                continue
            try:
                lat, lng = float(l.get("lat")), float(l.get("lng"))
            except (TypeError, ValueError):
                continue
            ref = l.get("reference")
            if isinstance(ref, str):
                ref = [r for r in re.findall(r"[A-Za-z0-9-]+", ref)]
            places.append({"id": l.get("id"), "name": (l.get("name") or "").strip(), "category": cat, "kind": "building" if cat in BUILDING_CATEGORIES else cat.lower(),
                           "lat": lat, "lng": lng, "building_number": (ref[0] if isinstance(ref, list) and ref else None) if cat in BUILDING_CATEGORIES else None,
                           "level": l.get("level") if isinstance(l.get("level"), list) and l.get("level") != [0] else None,
                           "link": f"{SITE}#!m/{l.get('mrkId')}" if l.get("mrkId") else SITE})
        if not places:
            raise ValueError("the map's locations came back empty")
        return {"categories": names, "places": places}
    return await _cache.remember("map", DAY, make)


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def collapse(places: list[dict]) -> list[dict]:
    """One row per name at one point: the map lists a building under several categories (its letter, Athletics, Historic
    Buildings, Building Addresses) at the same coordinates, which is one place with several categories, not several places."""
    out: dict[tuple, dict] = {}
    for p in places:
        key = (p["name"].lower(), round(p["lat"], 5), round(p["lng"], 5))
        if key in out:
            row = out[key]
            if p["category"] not in row["categories"]:
                row["categories"].append(p["category"])
            if p["kind"] == "building" and row["kind"] != "building":
                row.update({"kind": "building", "building_number": p["building_number"], "id": p["id"], "link": p["link"]})
        else:
            out[key] = {**p, "categories": [p["category"]]}
    return list(out.values())


def _matches(place: dict, words: list[str], category: str) -> bool:
    hay = place["name"].lower()
    return all(w in hay for w in words) and (not category or category in place["category"].lower())


@mcp.tool(name="campusmap_index", annotations=_READ_ONLY)
async def campusmap_index() -> dict:
    """How to use the campus map tools. READ THIS FIRST: what the map marks, how a building is named, how to get a route."""
    try:
        data = await _data()
        counts: dict[str, int] = {}
        for p in data["places"]:
            counts[p["category"]] = counts.get(p["category"], 0) + 1
        buildings = sum(1 for p in data["places"] if p["kind"] == "building")
    except ValueError:
        counts, buildings = {}, 0
    return {
        "upstream": f"The University of Idaho campus map, Concept3D map {MAP_ID} at {SITE}, read through Concept3D's locations and categories API with the map page's own client key; no key of the person's",
        "points": len(sum(([c] * n for c, n in counts.items()), [])) or None, "buildings": buildings or None,
        "workflow": ["campusmap_search with words of a building's or place's name ('Albertson', 'Memorial Gym', 'Pitman'), or a category ('Accessible Entrance', 'Commuter Parking', 'Dining'): name, category, coordinates, building number, map link",
                     "campusmap_near with a point for what is around it: the nearest accessible entrances, restrooms, parking, bike racks, dining, within a radius",
                     "campusmap_place with a place's id for the place and its nearest accessible entrances and parking",
                     "a route between two places: take their coordinates from here and call the osm server's osm_route (walk, bike or drive); this map has no routing of its own"],
        "notes": ["Buildings are named as the map names them, surname first with the given name in parentheses ('Albertson (J.A.)', 'Pitman Center (Bruce M.)', 'Brink Hall (Carol Ryrie)'), with the building number the university assigns (Administration Building is 1). Search by a word, not the full form.",
                  "An accessible entrance is named for its building and side ('Administration Building S, east end'); campusmap_near or campusmap_place finds the ones at a building.",
                  "Coordinates are WGS84 latitude and longitude; distances here are straight-line metres, not walking distance. osm_route gives the walking distance and time.",
                  "The map is the university's; a point is as current as its editors left it, and construction changes entrances. The map's own link opens the place on the map.",
                  "Cite a place by its map name with its map link."],
        "categories_sample": sorted(counts, key=lambda c: -counts[c])[:20],
        "link": SITE,
    }


@mcp.tool(name="campusmap_categories", annotations=_READ_ONLY)
async def campusmap_categories() -> dict:
    """The campus map's categories with how many points each holds: the names a category argument is matched against."""
    try:
        data = await _data()
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    counts: dict[str, int] = {}
    for p in data["places"]:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    cats = [{"category": c, "points": n, "kind": "building" if c in BUILDING_CATEGORIES else None} for c, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"total": len(cats), "categories": cats, "link": SITE}


@mcp.tool(name="campusmap_search", annotations=_READ_ONLY)
async def campusmap_search(query: str = "", category: str = "", rows: int = ROWS) -> dict:
    """Places on the University of Idaho campus map by words of their name or by category: name, category, coordinates, building number, map link.

    Args:
        query: Words in the place's name, e.g. 'Albertson', 'Memorial Gym', 'Library'. Empty with a category lists the category.
        category: A category or part of its name, e.g. 'Accessible Entrance', 'Commuter Parking', 'Dining', 'Department'; 'building' for the buildings.
        rows: Places to return, 1-200. Default 20.
    """
    words = query.lower().split()
    cat = category.strip().lower()
    if not words and not cat:
        return {"error": "give words of a name, a category, or both"}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    try:
        data = await _data()
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    if cat == "building":
        found = [p for p in data["places"] if p["kind"] == "building" and all(w in p["name"].lower() for w in words)]
    else:
        found = collapse([p for p in data["places"] if _matches(p, words, cat)])
    found.sort(key=lambda p: (p["kind"] != "building", p["name"]))
    out = {"query": {k: v for k, v in (("query", query.strip()), ("category", category.strip())) if v}, "total": len(found), "returned": min(rows, len(found)), "places": found[:rows], "link": SITE}
    if len(found) > rows:
        out["note"] = f"{len(found)} places match; the first {rows} are here, buildings first. Add a word or a category."
    if not found:
        out["note"] = "No place on the map matches. Names are the map's own (surname first, given name in parentheses); try one word, or the category alone."
    return out


@mcp.tool(name="campusmap_near", annotations=_READ_ONLY)
async def campusmap_near(lat: float, lng: float, category: str = "", radius_m: int = 200, rows: int = ROWS) -> dict:
    """What the campus map marks near a point, nearest first: accessible entrances, restrooms, parking, bike racks, dining, buildings, within a radius.

    Args:
        lat: Latitude of the point, e.g. 46.7256 (from campusmap_search or osm_geocode).
        lng: Longitude, e.g. -117.0117.
        category: A category or part of its name to keep ('Accessible', 'Parking', 'Restroom', 'Dining'); empty for everything.
        radius_m: Straight-line radius in metres, 10-2000. Default 200.
        rows: Places to return, 1-200. Default 20.
    """
    try:
        la, ln = float(lat), float(lng)
    except (TypeError, ValueError):
        return {"error": "lat and lng must be numbers"}
    if not (-90 <= la <= 90 and -180 <= ln <= 180):
        return {"error": "lat must be -90 to 90 and lng -180 to 180"}
    radius = max(10, min(int(radius_m or 200), 2000))
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    cat = category.strip().lower()
    try:
        data = await _data()
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    near = []
    for p in data["places"]:
        if cat and cat not in p["category"].lower() and not (cat == "building" and p["kind"] == "building"):
            continue
        d = distance_m(la, ln, p["lat"], p["lng"])
        if d <= radius:
            near.append({**p, "distance_m": round(d)})
    near.sort(key=lambda p: p["distance_m"])
    return {"point": {"lat": la, "lng": ln}, "radius_m": radius, "total": len(near), "returned": min(rows, len(near)), "places": near[:rows], "link": SITE,
            "note": "distance_m is straight-line; for the walk, osm_route."}


@mcp.tool(name="campusmap_place", annotations=_READ_ONLY)
async def campusmap_place(id: str) -> dict:
    """One place on the campus map with its nearest accessible entrances and parking: for a building, how to get in and where to park.

    Args:
        id: The place's id, from campusmap_search.
    """
    pid = str(id).strip()
    try:
        data = await _data()
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    place = next((p for p in data["places"] if str(p["id"]) == pid), None)
    if place is None:
        return {"error": f"no place {pid} on the map; take the id from campusmap_search"}

    def nearest(word: str, n: int, within: int) -> list[dict]:
        hits = [{**p, "distance_m": round(distance_m(place["lat"], place["lng"], p["lat"], p["lng"]))} for p in data["places"] if word in p["category"].lower() and p["id"] != place["id"]]
        return sorted((h for h in hits if h["distance_m"] <= within), key=lambda h: h["distance_m"])[:n]

    return {**place, "accessible_entrances": nearest("accessible entrance", 4, 150), "parking": nearest("parking", 3, 400), "restrooms": nearest("restroom", 3, 150),
            "note": "Entrances, parking and restrooms are the map's points within a short straight-line distance of this one, nearest first; for the walk between two places, osm_route with the coordinates."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A place id and a category the model names wait on the lists that carry them (#40); a point a person gives passes as given.
given(mcp, {"campusmap_place": {"id": "campusmap_search"}, "campusmap_search": {"category": "campusmap_categories"}, "campusmap_near": {"category": "campusmap_categories"}})
