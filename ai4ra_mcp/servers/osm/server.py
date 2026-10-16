"""osm: OpenStreetMap's public services, places by name (Nominatim) and routes between two points (Valhalla).

Upstreams, both OpenStreetMap data served by the OSM community's public servers under fair-use policies, no key:
Nominatim, https://nominatim.openstreetmap.org/search (one request a second, an identifying User-Agent, results
cached, no autocomplete and no bulk work; data under the ODbL, attribution required), and the FOSSGIS Valhalla
server, https://valhalla1.openstreetmap.de/route (the same fair use as the OSRM and Nominatim demo servers, about one
call a second per user), which routes on foot, by bicycle or by car with turn-by-turn maneuvers that name campus
walkways ('Bear right onto Hello Walk'). Calls here are paced to one a second to each and cached (places a day,
routes an hour). Tested 2026-10-16 on the University of Idaho campus: Nominatim resolved six of ten campus
buildings by name (OSM's own names, with the odd misspelling), so a campus place is better taken from the campusmap
server and only the route asked of this one; Valhalla walked Albertson to the Kibbie Dome in 0.42 miles and eight
minutes along the walkways. Not for heavy or periodic use: a production need is a self-hosted Nominatim or Valhalla.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, HOUR, TTLCache, get_json, post_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
VALHALLA = "https://valhalla1.openstreetmap.de/route"
NOMINATIM_POLICY = "https://operations.osmfoundation.org/policies/nominatim/"
ATTRIBUTION = "Data © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"
MODES = {"walk": "pedestrian", "bike": "bicycle", "drive": "auto"}
# Moscow, Idaho and Pullman, Washington: the box a campus question is biased to.
CAMPUS_VIEWBOX = "-117.20,46.78,-116.95,46.68"
ROWS, MAX_ROWS = 5, 20
_cache = TTLCache()
_pace_lock = asyncio.Lock()
_last_call = 0.0


async def _paced(coro_factory):
    """One call a second to the OSM servers, as their policies ask, whatever the callers do."""
    global _last_call
    async with _pace_lock:
        wait = 1.05 - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await coro_factory()
        finally:
            _last_call = time.monotonic()


mcp = MCPServer(
    "osm",
    instructions="OpenStreetMap's public services: a place by name with its coordinates (osm_geocode) and a walking, cycling or driving route between two points with turn-by-turn directions (osm_route). No key; one call a second, fair use. Read osm_index first.",
)


def slim_place(r: dict) -> dict:
    addr = r.get("address") or {}
    return {"name": r.get("name") or None, "display_name": r.get("display_name"), "kind": r.get("type"), "category": r.get("category"),
            "lat": float(r["lat"]) if r.get("lat") else None, "lon": float(r["lon"]) if r.get("lon") else None,
            "address": {k: addr.get(k) for k in ("house_number", "road", "city", "town", "state", "postcode") if addr.get(k)},
            "link": f"https://www.openstreetmap.org/{r.get('osm_type')}/{r.get('osm_id')}" if r.get("osm_type") and r.get("osm_id") else None}


def slim_route(trip: dict, mode: str) -> dict:
    summary = trip.get("summary") or {}
    legs = trip.get("legs") or [{}]
    steps = []
    for m in legs[0].get("maneuvers") or []:
        step = {"instruction": m.get("instruction"), "miles": round(m.get("length") or 0, 3)}
        if m.get("street_names"):
            step["streets"] = m["street_names"]
        steps.append(step)
    return {"mode": mode, "miles": round(summary.get("length") or 0, 2), "minutes": round((summary.get("time") or 0) / 60, 1), "steps": steps,
            "bounds": {k: summary.get(k) for k in ("min_lat", "min_lon", "max_lat", "max_lon")}}


def _coord(v, lo: float, hi: float, label: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if not lo <= f <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}")
    return f


@mcp.tool(name="osm_index", annotations=_READ_ONLY)
async def osm_index() -> dict:
    """How to use the OpenStreetMap tools. READ THIS FIRST: what each service is, the fair-use terms, the attribution, and when to take a campus place from campusmap instead."""
    return {
        "upstream": f"Nominatim at {NOMINATIM} (places) and the FOSSGIS Valhalla server at {VALHALLA} (routes), OpenStreetMap's public services; no key; one call a second to each, paced here",
        "workflow": ["osm_geocode with a place name and town for its coordinates: an address, a business, a landmark, a campus building OSM happens to name",
                     "osm_route with two points and a mode (walk, bike, drive) for the distance, time and turn-by-turn steps",
                     "for a University of Idaho building, take the point from campusmap_search (the university's own names and every building) and ask only the route here; OSM named six of ten campus buildings when tested, with misspellings"],
        "notes": ["Fair use: these are the OSM community's servers, not a product. One request a second, cached here (places a day, routes an hour), no autocomplete, no bulk or periodic work; a heavy or scheduled need means hosting Nominatim or Valhalla oneself. The policy is at " + NOMINATIM_POLICY + ".",
                  "Attribution is required on anything shown: " + ATTRIBUTION + ". Say it once with the result.",
                  "Routes follow OSM's mapped paths, including campus walkways, and are as current as the map; times are the router's estimates (walking about 3 mph). Steps name a street or walkway where OSM names it ('Hello Walk', 'University Avenue').",
                  "Coordinates are WGS84 latitude and longitude. A route is between points, not names; geocode or use campusmap first.",
                  "Cite a place by its OSM link and a route by its endpoints and mode."],
        "link": "https://www.openstreetmap.org/",
    }


@mcp.tool(name="osm_geocode", annotations=_READ_ONLY)
async def osm_geocode(query: str, near_campus: bool = True, rows: int = ROWS) -> dict:
    """A place by name through Nominatim: coordinates, kind, address and OSM link, biased to Moscow, Idaho and Pullman when near_campus is true.

    Args:
        query: The place as a person would write it, e.g. 'Kibbie Dome, Moscow, Idaho', 'Pullman-Moscow Regional Airport', '875 Perimeter Drive, Moscow ID'.
        near_campus: Prefer results around Moscow and Pullman (default true); false for anywhere.
        rows: Results to return, 1-20. Default 5.
    """
    q = query.strip()
    if len(q) < 3:
        return {"error": "query must be a place name or address"}
    rows = max(1, min(int(rows or ROWS), MAX_ROWS))
    params = {"q": q, "format": "jsonv2", "limit": rows, "addressdetails": 1}
    if near_campus:
        params.update({"viewbox": CAMPUS_VIEWBOX, "bounded": 0})
    key = "geocode:" + repr(sorted(params.items()))
    try:
        body = await _cache.remember(key, DAY, lambda: _paced(lambda: get_json(NOMINATIM, params)))
    except ValueError as e:
        return {"error": str(e), "upstream": NOMINATIM}
    if not isinstance(body, list):
        return {"error": "Nominatim did not return its list of places", "upstream": NOMINATIM}
    places = [slim_place(r) for r in body]
    out = {"query": q, "total": len(places), "places": places, "attribution": ATTRIBUTION}
    if not places:
        out["note"] = "Nothing in OpenStreetMap matches; for a University of Idaho building use campusmap_search, whose names are the university's."
    return out


@mcp.tool(name="osm_route", annotations=_READ_ONLY)
async def osm_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float, mode: str = "walk") -> dict:
    """A route between two points on foot, by bicycle or by car through the FOSSGIS Valhalla server: miles, minutes and turn-by-turn steps.

    Args:
        from_lat: Start latitude, e.g. 46.7256 (from campusmap_search or osm_geocode).
        from_lon: Start longitude, e.g. -117.0117.
        to_lat: End latitude.
        to_lon: End longitude.
        mode: walk (default), bike or drive.
    """
    m = mode.strip().lower()
    if m not in MODES:
        return {"error": "mode must be walk, bike or drive"}
    try:
        a = (_coord(from_lat, -90, 90, "from_lat"), _coord(from_lon, -180, 180, "from_lon"))
        b = (_coord(to_lat, -90, 90, "to_lat"), _coord(to_lon, -180, 180, "to_lon"))
    except ValueError as e:
        return {"error": str(e)}
    payload = {"locations": [{"lat": a[0], "lon": a[1]}, {"lat": b[0], "lon": b[1]}], "costing": MODES[m], "units": "miles", "directions_options": {"units": "miles"}}
    key = f"route:{m}:{a}:{b}"
    try:
        body = await _cache.remember(key, HOUR, lambda: _paced(lambda: post_json(VALHALLA, payload)))
    except ValueError as e:
        return {"error": str(e), "upstream": VALHALLA}
    trip = body.get("trip") if isinstance(body, dict) else None
    if not isinstance(trip, dict):
        detail = (body or {}).get("error") if isinstance(body, dict) else None
        return {"error": "Valhalla returned no route" + (f": {detail}" if detail else " (a point may be off the mapped network; try a nearby street)"), "upstream": VALHALLA}
    return {"from": {"lat": a[0], "lon": a[1]}, "to": {"lat": b[0], "lon": b[1]}, **slim_route(trip, m), "attribution": ATTRIBUTION,
            "link": f"https://www.openstreetmap.org/directions?engine=fossgis_valhalla_{'foot' if m == 'walk' else 'bicycle' if m == 'bike' else 'car'}&route={a[0]}%2C{a[1]}%3B{b[0]}%2C{b[1]}"}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# Points come from the person, from osm_geocode or from campusmap; no identifier here is a list's (#40).
