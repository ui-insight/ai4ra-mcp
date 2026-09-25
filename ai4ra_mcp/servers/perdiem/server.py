"""perdiem: GSA per diem rates, the lodging and M&IE ceilings for federal travel within the continental US.

Upstream: https://api.gsa.gov/travel/perdiem/v2/ (rates/city/{city}/state/{ST}/year/{YYYY}, rates/state/{ST}/year/{YYYY},
rates/zip/{zip}/year/{YYYY}, rates/conus/mie/{YYYY}). A free api.data.gov key as the query param api_key; DEMO_KEY
works for a handful of calls an hour. Years are federal fiscal years (October 1 to September 30). Lodging is a
per-night ceiling by calendar month; M&IE (meals) is per day.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from urllib.parse import quote

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, api_key, get_json, missing_key
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_PERDIEM_KEY"
KEY_HOW = "A free key comes from https://api.data.gov/signup/ (an email address is all it asks); DEMO_KEY works for a few calls an hour."
BASE = "https://api.gsa.gov/travel/perdiem/v2"
RATES_PAGE = "https://www.gsa.gov/travel/plan-book/per-diem-rates"
STANDARD = "Standard Rate"
_cache = TTLCache()

mcp = MCPServer(
    "perdiem",
    instructions="GSA per diem: the lodging ceiling by month and the M&IE rate for a city, state or zip in a fiscal year, and the M&IE meal breakdown. Needs a free api.data.gov key. Read gsa_perdiem_index first.",
)


def fiscal_year(today: dt.date | None = None) -> int:
    """The federal fiscal year a date falls in: October starts the next one."""
    d = today or dt.date.today()
    return d.year + 1 if d.month >= 10 else d.year


async def _get(path: str) -> dict | list:
    key = api_key(KEY_ENV)
    if not key:
        raise LookupError(KEY_ENV)
    # The cache key is the path alone, so a key never sits in memory beside the data it fetched.
    return await _cache.remember(path, DAY, lambda: get_json(f"{BASE}/{path}", {"api_key": key}))


def slim_location(r: dict, state: str, year: int) -> dict:
    months = {m.get("short"): m.get("value") for m in ((r.get("months") or {}).get("month") or []) if m.get("short")}
    values = [v for v in months.values() if isinstance(v, (int, float))]
    city = r.get("city")
    return {
        "city": city, "county": r.get("county"), "state": state, "zip": r.get("zip"), "year": year,
        "meals": r.get("meals"), "lodging_by_month": months,
        "lodging_min": min(values) if values else None, "lodging_max": max(values) if values else None,
        # GSA sends standardRate as the string "false" even on the standard-rate row; the city name is the reliable sign.
        "standard_rate": str(r.get("standardRate")).lower() == "true" or city == STANDARD,
    }


def slim_mie(t: dict) -> dict:
    return {"total": t.get("total"), "breakfast": t.get("breakfast"), "lunch": t.get("lunch"), "dinner": t.get("dinner"),
            "incidentals": t.get("incidental"), "first_and_last_day": t.get("FirstLastDay")}


def _locations(body: dict, year: int) -> list[dict]:
    out = []
    for block in (body.get("rates") if isinstance(body, dict) else None) or []:
        state = block.get("state")
        out.extend(slim_location(r, state, year) for r in block.get("rate") or [])
    return out


@mcp.tool(name="gsa_perdiem_index", annotations=_READ_ONLY)
async def gsa_perdiem_index() -> dict:
    """How to use the GSA per diem tools. READ THIS FIRST: the key, the fiscal year, what lodging and M&IE mean."""
    return {
        "upstream": "https://api.gsa.gov/travel/perdiem/v2/ (GSA per diem rates for the continental US)",
        "key": {"on_this_request": api_key(KEY_ENV) is not None, "per_user": "send your own api.data.gov key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "workflow": ["gsa_perdiem_rates by city and state, by state alone (every listed location in it) or by zip, for a fiscal year",
                     "gsa_perdiem_mie_breakdown for the year's M&IE tiers: breakfast, lunch, dinner, incidentals and the first-and-last-day amount"],
        "notes": ["Years are federal fiscal years: FY2026 runs October 1, 2025 to September 30, 2026, so Oct, Nov and Dec in lodging_by_month are the earlier calendar year.",
                  f"The current fiscal year is {fiscal_year()}; the default year when none is given.",
                  "Lodging is a per-night ceiling before tax and varies by month in seasonal locations; meals is the M&IE rate per day, paid at 75 percent on the first and last day of travel.",
                  "A city not listed takes the standard CONUS rate, the row with standard_rate true (city 'Standard Rate'); gsa_perdiem_rates returns that row and says so when a city is not found.",
                  "Only the continental US is here. Alaska, Hawaii and territories are the Defense Department's rates and foreign locations the State Department's.",
                  "Cite the fiscal year and the location (city, county, state) with the GSA per diem page link."],
    }


@mcp.tool(name="gsa_perdiem_rates", annotations=_READ_ONLY)
async def gsa_perdiem_rates(year: int = 0, city: str = "", state: str = "", zip: str = "") -> dict:
    """GSA per diem rates for a fiscal year: lodging by month and the M&IE rate, for a city and state, a whole state, or a zip.

    Give one of: city with state, state alone (every listed location in the state plus the standard rate), or zip.
    Returns one location per row with city, county, state, zip, meals (M&IE per day), lodging_by_month, lodging_min,
    lodging_max, a standard_rate flag, and a link to the GSA per diem page.

    Args:
        year: Federal fiscal year, e.g. 2026 (October 2025 to September 2026). 0 means the current fiscal year.
        city: City name as GSA lists it, e.g. 'Boise'. Needs state.
        state: Two-letter state, e.g. 'ID'.
        zip: Five-digit zip code, e.g. '83702'. Used alone.
    """
    yr = int(year or 0) or fiscal_year()
    if yr < 2000 or yr > fiscal_year() + 1:
        return {"error": f"year must be a federal fiscal year between 2000 and {fiscal_year() + 1}"}
    city, state, zip = city.strip(), state.strip().upper(), "".join(ch for ch in zip if ch.isdigit())
    if zip:
        if len(zip) != 5:
            return {"error": "zip must be five digits"}
        path, query = f"rates/zip/{zip}/year/{yr}", {"zip": zip}
    elif state:
        if len(state) != 2 or not state.isalpha():
            return {"error": "state must be a two-letter code, e.g. 'ID'"}
        path = f"rates/city/{quote(city, safe='')}/state/{state}/year/{yr}" if city else f"rates/state/{state}/year/{yr}"
        query = {"city": city, "state": state} if city else {"state": state}
    elif city:
        return {"error": "city needs state, e.g. city='Boise', state='ID'"}
    else:
        return {"error": "give one of city with state, state alone, or zip"}
    try:
        body = await _get(path)
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    locations = _locations(body, yr)
    out: dict = {"year": yr, "query": query, "returned": len(locations), "locations": locations, "link": RATES_PAGE}
    if not locations:
        out["note"] = "GSA lists nothing for this query; check the zip or the year (rates are published for the current and recent fiscal years)."
    elif city and not any(city.lower() in (loc["city"] or "").lower() for loc in locations):
        # An unlisted city comes back as the whole state; the standard rate is what applies to it.
        std = [loc for loc in locations if loc["standard_rate"]]
        out.update({"returned": len(std), "locations": std,
                    "note": f"GSA lists no rate for {city}, {state} in FY{yr}; the standard CONUS rate applies. Ask for the state alone to see every listed location."})
    return out


@mcp.tool(name="gsa_perdiem_mie_breakdown", annotations=_READ_ONLY)
async def gsa_perdiem_mie_breakdown(year: int = 0) -> dict:
    """The M&IE tiers for a fiscal year: each daily total with its breakfast, lunch, dinner and incidentals, and the first-and-last-day (75 percent) amount.

    Match a location's meals value from gsa_perdiem_rates to a tier's total to itemize it.

    Args:
        year: Federal fiscal year, e.g. 2026. 0 means the current fiscal year.
    """
    yr = int(year or 0) or fiscal_year()
    if yr < 2000 or yr > fiscal_year() + 1:
        return {"error": f"year must be a federal fiscal year between 2000 and {fiscal_year() + 1}"}
    try:
        body = await _get(f"rates/conus/mie/{yr}")
    except LookupError:
        return missing_key(KEY_ENV, KEY_HOW)
    except ValueError as e:
        return {"error": str(e)}
    tiers = [slim_mie(t) for t in body] if isinstance(body, list) else []
    return {"year": yr, "returned": len(tiers), "tiers": tiers, "link": RATES_PAGE,
            "note": "first_and_last_day is 75 percent of the total, the M&IE paid on a travel day; incidentals cover tips and fees."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
