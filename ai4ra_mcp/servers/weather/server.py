"""weather: the National Weather Service's forecasts, alerts and observations for a point in the United States.

Upstream: https://api.weather.gov/ (JSON, no key; an identifying User-Agent, which every call here carries). A point
(/points/{lat},{lon}) names its forecast office and grid and links the forecasts: /gridpoints/{office}/{x},{y}/forecast
(twelve-hour periods for seven days), /forecast/hourly, and the observation stations near it, whose latest observation
is /stations/{id}/observations/latest; the office itself (/offices/{id}) gives its name, address and the county zones it
is responsible for, which /zones?type=county&id=... names in one call. Active alerts for a point are /alerts/active?point=lat,lon. The service covers
the United States and its territories and nothing else. Points are cached a day, forecasts half an hour, observations
ten minutes, alerts five.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, get_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
API = "https://api.weather.gov"
SITE = "https://www.weather.gov/"
HALF_HOUR, TEN_MINUTES, FIVE_MINUTES = 1800, 600, 300
_cache = TTLCache()

mcp = MCPServer(
    "weather",
    instructions="The National Weather Service: the forecast for a point (weather_forecast, by half-day or by hour), the latest observation near it (weather_now), active alerts (weather_alerts) and the forecast office behind them with the counties it covers (weather_office). United States only, no key. Read weather_index first.",
)


def _coords(lat, lon) -> tuple[float, float]:
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("lat and lon must be numbers") from None
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        raise ValueError("lat must be -90 to 90 and lon -180 to 180")
    return round(la, 4), round(lo, 4)


async def _point(la: float, lo: float) -> dict:
    no_grid = "the Weather Service has no grid for this point (outside the United States, or over water)"
    try:
        body = await _cache.remember(f"point:{la},{lo}", DAY, lambda: get_json(f"{API}/points/{la},{lo}"))
    except ValueError as e:
        # A point outside the grids is a 404 on land abroad and, tested 2026-10-16, a 500 over the open ocean.
        if str(e)[:3] in ("404", "500") and "api.weather.gov" in str(e):
            raise ValueError(no_grid) from None
        raise
    props = (body.get("properties") if isinstance(body, dict) else None) or {}
    if not props.get("forecast"):
        raise ValueError(no_grid)
    return props


async def _office(point: dict) -> dict:
    """The forecast office responsible for a point, by id and name (OTX is Spokane, WA); the name read from the office's own record, cached a day."""
    oid, url = point.get("cwa") or point.get("gridId"), point.get("forecastOffice")
    name = None
    if url:
        try:
            body = await _cache.remember(f"office:{url}", DAY, lambda: get_json(url))
            name = body.get("name") if isinstance(body, dict) else None
        except ValueError:
            name = None  # the forecast stands without the office's name; the id is still the Service's own
    return {"id": oid, "name": name, "link": url}


def _f(v) -> float | None:
    """A measured value out of the Service's {unitCode, value, qualityControl} triple; None when not observed."""
    v = v.get("value") if isinstance(v, dict) else v
    return v if isinstance(v, (int, float)) else None


def _scale(v, factor: float, places: int) -> float | None:
    return round(v * factor, places) if v is not None else None


def slim_period(p: dict) -> dict:
    pop = p.get("probabilityOfPrecipitation") or {}
    return {"name": p.get("name") or None, "start": p.get("startTime"), "end": p.get("endTime"), "is_daytime": p.get("isDaytime"),
            "temperature": p.get("temperature"), "unit": p.get("temperatureUnit"), "precipitation_chance_pct": pop.get("value"),
            "wind": f"{p.get('windSpeed')} {p.get('windDirection')}".strip(), "short": p.get("shortForecast"), "detailed": p.get("detailedForecast") or None}


def c_to_f(c: float | None) -> float | None:
    return round(c * 9 / 5 + 32, 1) if c is not None else None


def slim_observation(o: dict) -> dict:
    """An observation in the units a reader here expects; the Service reports Celsius, km/h, metres and pascals."""
    temp, dew, hum = _f(o.get("temperature")), _f(o.get("dewpoint")), _f(o.get("relativeHumidity"))
    return {"time": o.get("timestamp"), "description": o.get("textDescription") or None, "temperature_f": c_to_f(temp), "temperature_c": _scale(temp, 1, 1),
            "dewpoint_f": c_to_f(dew), "humidity_pct": _scale(hum, 1, 0), "wind_mph": _scale(_f(o.get("windSpeed")), 0.621371, 1),
            "wind_gust_mph": _scale(_f(o.get("windGust")), 0.621371, 1), "wind_direction_deg": _f(o.get("windDirection")),
            "visibility_miles": _scale(_f(o.get("visibility")), 1 / 1609.344, 1), "pressure_inhg": _scale(_f(o.get("barometricPressure")), 1 / 3386.39, 2)}


def slim_alert(a: dict) -> dict:
    p = a.get("properties") or {}
    return {"event": p.get("event"), "severity": p.get("severity"), "urgency": p.get("urgency"), "certainty": p.get("certainty"), "headline": p.get("headline"),
            "areas": p.get("areaDesc"), "onset": p.get("onset"), "ends": p.get("ends") or p.get("expires"), "sender": p.get("senderName"),
            "description": p.get("description"), "instruction": p.get("instruction"), "link": p.get("@id") or a.get("id")}


@mcp.tool(name="weather_index", annotations=_READ_ONLY)
async def weather_index() -> dict:
    """How to use the Weather Service tools. READ THIS FIRST: what a point gives, the units, the coverage, where a campus point comes from."""
    return {
        "upstream": f"The National Weather Service API at {API}; no key; United States and territories only",
        "workflow": ["weather_forecast with a latitude and longitude: seven days in half-day periods, or 48 hours by the hour, as the forecast office words it",
                     "weather_now for the latest observation at the nearest reporting station: temperature, wind, humidity, visibility, pressure",
                     "weather_alerts for the watches, warnings and advisories in force at the point",
                     "weather_office with the office id an answer names (OTX) for the office's name, address, telephone and the counties it forecasts for"],
        "notes": ["A point is a latitude and longitude; the campusmap server gives one for any University of Idaho building, osm_geocode for any address or town. The forecast office is named on each answer by id and name (OTX, Spokane, WA, for the Palouse); the name is the Service's, not a guess from the id.",
                  "Temperatures are Fahrenheit as the Service issues them for forecasts; observations arrive in Celsius and are given in both. Winds in miles an hour, pressure in inches of mercury, visibility in miles.",
                  "Forecast periods are the Service's half days ('This Afternoon', 'Tonight', 'Friday'); the hourly forecast runs 48 hours. Times carry the point's own offset.",
                  "An observation is the nearest station's latest report, often an airport some miles away, and can be an hour old; the time says.",
                  "Alerts are the official watches, warnings and advisories; none in force is an empty list, not an error.",
                  "Cite as 'National Weather Service, <office name>' with the time of the forecast or observation."],
        "link": SITE,
    }


@mcp.tool(name="weather_forecast", annotations=_READ_ONLY)
async def weather_forecast(lat: float, lon: float, hourly: bool = False) -> dict:
    """The National Weather Service forecast for a point: seven days in half-day periods, or the next 48 hours by the hour.

    Args:
        lat: Latitude, e.g. 46.7324.
        lon: Longitude, e.g. -117.0002.
        hourly: True for the hourly forecast; false (default) for the half-day periods.
    """
    try:
        la, lo = _coords(lat, lon)
        point = await _point(la, lo)
        url = point["forecastHourly"] if hourly else point["forecast"]
        body = await _cache.remember(f"forecast:{url}", HALF_HOUR, lambda: get_json(url))
        office = await _office(point)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    props = (body.get("properties") if isinstance(body, dict) else None) or {}
    periods = [slim_period(p) for p in props.get("periods") or []]
    if hourly:
        periods = periods[:48]
    rel = (point.get("relativeLocation") or {}).get("properties") or {}
    return {"point": {"lat": la, "lon": lo, "near": f"{rel.get('city')}, {rel.get('state')}" if rel.get("city") else None, "timezone": point.get("timeZone")},
            "office": office, "issued": props.get("updateTime") or props.get("generatedAt"), "hourly": hourly, "periods": periods,
            "link": f"https://forecast.weather.gov/MapClick.php?lat={la}&lon={lo}"}


@mcp.tool(name="weather_now", annotations=_READ_ONLY)
async def weather_now(lat: float, lon: float) -> dict:
    """The latest observation at the reporting station nearest a point: conditions, temperature, wind, humidity, visibility, pressure.

    Args:
        lat: Latitude, e.g. 46.7324.
        lon: Longitude, e.g. -117.0002.
    """
    try:
        la, lo = _coords(lat, lon)
        point = await _point(la, lo)
        stations = await _cache.remember(f"stations:{point['observationStations']}", DAY, lambda: get_json(point["observationStations"]))
        feats = (stations.get("features") if isinstance(stations, dict) else None) or []
        if not feats:
            return {"error": "the Weather Service lists no observation station near this point", "upstream": API}
        st = feats[0]
        sid = (st.get("properties") or {}).get("stationIdentifier")
        obs = await _cache.remember(f"obs:{sid}", TEN_MINUTES, lambda: get_json(f"{API}/stations/{sid}/observations/latest"))
        office = await _office(point)
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    o = (obs.get("properties") if isinstance(obs, dict) else None) or {}
    return {"point": {"lat": la, "lon": lo}, "office": office, "station": {"id": sid, "name": (st.get("properties") or {}).get("name")}, **slim_observation(o),
            "link": f"https://forecast.weather.gov/MapClick.php?lat={la}&lon={lo}"}


@mcp.tool(name="weather_alerts", annotations=_READ_ONLY)
async def weather_alerts(lat: float, lon: float) -> dict:
    """The National Weather Service watches, warnings and advisories in force at a point, most severe first.

    Args:
        lat: Latitude, e.g. 46.7324.
        lon: Longitude, e.g. -117.0002.
    """
    try:
        la, lo = _coords(lat, lon)
        body = await _cache.remember(f"alerts:{la},{lo}", FIVE_MINUTES, lambda: get_json(f"{API}/alerts/active", {"point": f"{la},{lo}"}))
    except ValueError as e:
        return {"error": str(e), "upstream": API}
    feats = (body.get("features") if isinstance(body, dict) else None) or []
    order = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
    alerts = sorted((slim_alert(a) for a in feats), key=lambda a: order.get(a["severity"] or "", 9))
    return {"point": {"lat": la, "lon": lo}, "total": len(alerts), "alerts": alerts, "link": f"https://alerts.weather.gov/search?point={la},{lo}"}


@mcp.tool(name="weather_office", annotations=_READ_ONLY)
async def weather_office(office: str) -> dict:
    """A National Weather Service forecast office by its id: name, address, telephone, region and the counties it is responsible for.

    Args:
        office: The three-letter office id a forecast or observation names, e.g. 'OTX' (Spokane), 'BOI' (Boise), 'PDT' (Pendleton).
    """
    oid = office.strip().upper()
    if not oid.isalpha() or len(oid) != 3:
        return {"error": "office must be a three-letter id such as OTX; weather_forecast names the one for a point", "upstream": API}
    url = f"{API}/offices/{oid}"
    try:
        body = await _cache.remember(f"office:{url}", DAY, lambda: get_json(url))
    except ValueError as e:
        if str(e)[:3] == "404":
            return {"error": f"the Weather Service has no office {oid}", "upstream": API}
        return {"error": str(e), "upstream": API}
    if not isinstance(body, dict) or not body.get("name"):
        return {"error": f"the Weather Service has no office {oid}", "upstream": API}
    county_ids = [u.rsplit("/", 1)[-1] for u in body.get("responsibleCounties") or []]
    counties, counties_error = [], None
    if county_ids:
        try:
            zones = await _cache.remember(f"zones:{','.join(county_ids)}", DAY, lambda: get_json(f"{API}/zones", {"type": "county", "id": ",".join(county_ids)}))
            counties = sorted(({"id": z.get("id"), "county": z.get("name"), "state": z.get("state")} for z in ((f.get("properties") or {}) for f in (zones.get("features") or []))),
                              key=lambda c: (c["state"] or "", c["county"] or ""))
        except ValueError as e:
            counties_error = str(e)
    addr = body.get("address") or {}
    return {"id": oid, "name": body.get("name"), "address": " ".join(x for x in (addr.get("streetAddress"), addr.get("addressLocality"), addr.get("addressRegion"), addr.get("postalCode")) if x) or None,
            "telephone": body.get("telephone"), "email": body.get("email"), "region": body.get("nwsRegion"), "parent": (body.get("parentOrganization") or "").rsplit("/", 1)[-1] or None,
            "counties": counties, "total_counties": len(county_ids), "counties_error": counties_error,
            "observation_stations": len(body.get("approvedObservationStations") or []), "link": url, "site": f"https://www.weather.gov/{oid.lower()}/"}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
# A point comes from the person, campusmap or osm; nothing here lists one (#40).
