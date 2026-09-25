"""bls: the Bureau of Labor Statistics Public Data API, the CPI and ECI series a budget's escalation rate rests on.

Upstream: https://api.bls.gov/publicAPI/ (POST timeseries/data/). v1 needs no key: 25 queries a day per IP, 10 years
and 25 series a query. v2 takes a free registration key in the body as registrationkey: 500 a day, 20 years, 50
series, and catalog titles. Data points are year plus period (M01-M12 months, M13 annual average, Q01-Q04 quarters).
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ai4ra_mcp.common.http import DAY, TTLCache, api_key, post_json
from ai4ra_mcp.common.skills import register_prompts

_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
KEY_ENV = "AI4RA_MCP_BLS_KEY"
KEY_HOW = "Optional. A free registration key comes from https://data.bls.gov/registrationEngine/ and lifts the limit from the shared 25 queries a day to 500, with catalog titles."
BASE = "https://api.bls.gov/publicAPI"
LIMITS = {"v1": {"queries_a_day": 25, "years": 10, "series": 25}, "v2": {"queries_a_day": 500, "years": 20, "series": 50}}
# Verified live on v1, 2026-09-24. PCU5417--5417-- (PPI scientific R&D services) no longer exists and is left out.
COMMON_SERIES = [
    {"id": "CUUR0000SA0", "name": "CPI-U, all items, U.S. city average, not seasonally adjusted", "frequency": "monthly", "values": "index level (1982-84=100)", "use": "the usual escalation basis for non-salary costs; take the 12-month change"},
    {"id": "CUSR0000SA0", "name": "CPI-U, all items, U.S. city average, seasonally adjusted", "frequency": "monthly", "values": "index level", "use": "month-to-month comparison; 12-month changes are conventionally taken from the unadjusted series"},
    {"id": "CUUR0400SA0", "name": "CPI-U, all items, West region, not seasonally adjusted", "frequency": "monthly", "values": "index level", "use": "a regional basis for a western institution"},
    {"id": "CUUR0000SAM", "name": "CPI-U, medical care, U.S. city average, not seasonally adjusted", "frequency": "monthly", "values": "index level", "use": "health-insurance and clinical cost lines"},
    {"id": "CUUR0000SEEB", "name": "CPI-U, college tuition and fees, U.S. city average, not seasonally adjusted", "frequency": "monthly", "values": "index level", "use": "graduate tuition remission lines"},
    {"id": "CIU1010000000000A", "name": "ECI, total compensation, all civilian workers, 12-month percent change", "frequency": "quarterly", "values": "percent change already", "use": "salary and fringe escalation; the latest quarter is the rate"},
    {"id": "CIU2010000000000A", "name": "ECI, wages and salaries, all civilian workers, 12-month percent change", "frequency": "quarterly", "values": "percent change already", "use": "salary-only escalation"},
    {"id": "CIU1020000000000A", "name": "ECI, total compensation, private industry, 12-month percent change", "frequency": "quarterly", "values": "percent change already", "use": "a private-sector comparison"},
]
_cache = TTLCache()

mcp = MCPServer(
    "bls",
    instructions="Bureau of Labor Statistics: CPI, ECI and other time series by id for a span of years, and the series ids a budget escalation rate uses. A key is optional. Read bls_index first.",
)


def _version() -> tuple[str, str | None]:
    key = api_key(KEY_ENV)
    return ("v2", key) if key else ("v1", None)


def _point(p: dict) -> dict:
    try:
        value = float(p.get("value"))
    except (TypeError, ValueError):
        value = None
    return {"year": p.get("year"), "period": p.get("period"), "period_name": p.get("periodName"), "value": value,
            "latest": str(p.get("latest")).lower() == "true"}


def slim_series(s: dict) -> dict:
    sid = s.get("seriesID")
    points = sorted((_point(p) for p in s.get("data") or []), key=lambda p: (p["year"] or "", p["period"] or ""), reverse=True)
    out = {"id": sid, "title": (s.get("catalog") or {}).get("series_title"), "returned": len(points), "data": points,
           "link": f"https://data.bls.gov/timeseries/{sid}"}
    if not points:
        out["note"] = "no data came back for this id; the message list says whether it exists"
    return out


@mcp.tool(name="bls_index", annotations=_READ_ONLY)
async def bls_index() -> dict:
    """How to use the BLS tools. READ THIS FIRST: which API version is in use, its limits, and how an escalation rate is computed."""
    version, key = _version()
    return {
        "upstream": f"https://api.bls.gov/publicAPI/{version}/ (BLS Public Data API)",
        "in_use": {"version": version, "why": "a registration key is on this request" if key else "no registration key, so the shared v1 limits apply", **LIMITS[version]},
        "key": {"on_this_request": key is not None, "per_user": "send your own BLS registration key as a bearer token; the server holds none unless the deployment set " + KEY_ENV + " as a fallback", "how": KEY_HOW},
        "workflow": ["bls_common_series for the ids a budget justification uses (CPI-U, ECI, CPI medical care, CPI tuition)",
                     "bls_series with those ids and a span of years; points come newest first"],
        "notes": ["An escalation rate for a budget is usually the trailing 12-month change in CPI-U or ECI: take two points a year apart from the same series and compute 100 * (new - old) / old.",
                  "ECI series ending in A are already 12-month percent changes; their latest value is the rate, no arithmetic needed.",
                  "Periods: M01-M12 are months, M13 the annual average (only with annual_average), Q01-Q04 quarters. The latest flag marks the newest point BLS has.",
                  "State clearly which series id and which two periods the rate came from, and link the series page.",
                  "The response's message list carries BLS errors and limit warnings (a series that does not exist, a daily threshold reached); read it when data is empty.",
                  "v1's 25 queries a day are per IP and shared by everyone on this server, so a personal registration key is better; results are cached for a day to spare the quota."],
    }


@mcp.tool(name="bls_series", annotations=_READ_ONLY)
async def bls_series(series_ids: str, start_year: str = "", end_year: str = "", annual_average: bool = False) -> dict:
    """BLS time series by id: each series' data points newest first, with the year, period, value and latest flag.

    Use bls_common_series for the ids a budget uses. Without years BLS returns its latest three.

    Args:
        series_ids: One or more series ids, comma-separated, e.g. 'CUUR0000SA0,CIU1010000000000A'. Up to 25 (50 with a key).
        start_year: First year, e.g. '2024'. Empty for BLS's default span.
        end_year: Last year, e.g. '2026'. At most 10 years after start_year (20 with a key).
        annual_average: Also return each year's annual average as period M13. Default false.
    """
    ids = [s.strip().upper() for s in series_ids.replace(";", ",").split(",") if s.strip()]
    if not ids:
        return {"error": "series_ids is required, e.g. 'CUUR0000SA0'"}
    version, key = _version()
    limits = LIMITS[version]
    if len(ids) > limits["series"]:
        return {"error": f"at most {limits['series']} series a query on {version}"}
    start, end = start_year.strip(), end_year.strip()
    if (start and not start.isdigit()) or (end and not end.isdigit()) or bool(start) != bool(end):
        return {"error": "give start_year and end_year together as four-digit years, or neither"}
    if start and int(end) - int(start) + 1 > limits["years"]:
        return {"error": f"at most {limits['years']} years a query on {version}; split the span"}
    if start and int(end) < int(start):
        return {"error": "end_year is before start_year"}
    payload: dict = {"seriesid": ids}
    if start:
        payload.update({"startyear": start, "endyear": end})
    if annual_average:
        payload["annualaverage"] = True
    if version == "v2":
        payload["catalog"] = True
    # The cache key is the query alone; the key goes in the body only.
    cache_key = f"{version}:" + repr(sorted(payload.items()))
    body_sent = {**payload, "registrationkey": key} if key else payload
    try:
        body = await _cache.remember(cache_key, DAY, lambda: post_json(f"{BASE}/{version}/timeseries/data/", body_sent))
    except ValueError as e:
        return {"error": str(e)}
    results = body.get("Results") or {}
    series = [slim_series(s) for s in results.get("series") or []]
    out = {"api_version": version, "status": body.get("status"), "returned": len(series), "series": series}
    if body.get("message"):
        out["message"] = body["message"]
    if str(body.get("status", "")).upper() != "REQUEST_SUCCEEDED":
        # BLS answers a bad request or an exhausted quota with 200 and a status; do not keep that answer a day.
        _cache._d.pop(cache_key, None)
        out["error"] = f"BLS status {body.get('status')}: " + "; ".join(body.get("message") or [])
    return out


@mcp.tool(name="bls_common_series", annotations=_READ_ONLY)
async def bls_common_series() -> dict:
    """The BLS series ids a budget justification's escalation rates use, with what each measures and how to read its values.

    Returns:
        A list of series with id, name, frequency, what the values are (an index level or already a percent change) and the budget use.
    """
    return {"returned": len(COMMON_SERIES), "series": [{**s, "link": f"https://data.bls.gov/timeseries/{s['id']}"} for s in COMMON_SERIES],
            "note": "Index-level series need two points a year apart: rate = 100 * (new - old) / old. ECI 'A' series are already the 12-month change."}


SKILLS_DIR = Path(__file__).parent / "skills"
register_prompts(mcp, SKILLS_DIR)
