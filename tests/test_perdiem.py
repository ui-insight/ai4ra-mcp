"""perdiem: the GSA shapes slimmed, the request built from city, state or zip, the unlisted-city answer, and the missing-key answer."""

import datetime as dt

from ai4ra_mcp.servers.perdiem import server as p

MONTHS = [{"value": 167, "number": 1, "short": "Jan", "long": "January"}, {"value": 167, "number": 2, "short": "Feb", "long": "February"},
          {"value": 167, "number": 3, "short": "Mar", "long": "March"}, {"value": 167, "number": 4, "short": "Apr", "long": "April"},
          {"value": 167, "number": 5, "short": "May", "long": "May"}, {"value": 191, "number": 6, "short": "Jun", "long": "June"},
          {"value": 191, "number": 7, "short": "Jul", "long": "July"}, {"value": 191, "number": 8, "short": "Aug", "long": "August"},
          {"value": 191, "number": 9, "short": "Sep", "long": "September"}, {"value": 191, "number": 10, "short": "Oct", "long": "October"},
          {"value": 167, "number": 11, "short": "Nov", "long": "November"}, {"value": 167, "number": 12, "short": "Dec", "long": "December"}]
BOISE = {"months": {"month": MONTHS}, "meals": 86, "zip": None, "county": "Ada", "city": "Boise", "standardRate": "false"}
STANDARD = {"months": {"month": [{**m, "value": 110} for m in MONTHS]}, "meals": 68, "zip": None, "county": None, "city": "Standard Rate", "standardRate": "false"}
CDA = {"months": {"month": [{**m, "value": 130} for m in MONTHS]}, "meals": 74, "zip": None, "county": "Kootenai", "city": "Coeur d'Alene", "standardRate": "false"}
CITY_BODY = {"request": None, "errors": None, "rates": [{"oconusInfo": None, "rate": [BOISE], "state": "ID", "year": 2026, "isOconus": "false"}], "version": None}
STATE_BODY = {"request": None, "errors": None, "rates": [{"oconusInfo": None, "rate": [BOISE, CDA, STANDARD], "state": "ID", "year": 2026, "isOconus": "false"}], "version": None}
EMPTY_BODY = {"request": None, "errors": None, "rates": [], "version": None}
MIE_BODY = [{"total": 68, "breakfast": 16, "lunch": 19, "dinner": 28, "incidental": 5, "FirstLastDay": 51},
            {"total": 74, "breakfast": 18, "lunch": 20, "dinner": 31, "incidental": 5, "FirstLastDay": 55.5},
            {"total": 86, "breakfast": 22, "lunch": 23, "dinner": 36, "incidental": 5, "FirstLastDay": 64.5}]


def test_location_slims_with_month_dict_and_range():
    loc = p.slim_location(BOISE, "ID", 2026)
    assert loc["city"] == "Boise" and loc["county"] == "Ada" and loc["state"] == "ID" and loc["meals"] == 86 and loc["year"] == 2026
    assert loc["lodging_by_month"]["Jan"] == 167 and loc["lodging_by_month"]["Jul"] == 191 and len(loc["lodging_by_month"]) == 12
    assert loc["lodging_min"] == 167 and loc["lodging_max"] == 191 and loc["standard_rate"] is False


def test_standard_rate_row_is_flagged_despite_gsa_saying_false():
    assert p.slim_location(STANDARD, "ID", 2026)["standard_rate"] is True
    assert p.slim_location({**BOISE, "standardRate": "true"}, "ID", 2026)["standard_rate"] is True


def test_mie_tier_slims():
    t = p.slim_mie(MIE_BODY[1])
    assert t == {"total": 74, "breakfast": 18, "lunch": 20, "dinner": 31, "incidentals": 5, "first_and_last_day": 55.5}


def test_fiscal_year_starts_in_october():
    assert p.fiscal_year(dt.date(2026, 9, 30)) == 2026 and p.fiscal_year(dt.date(2026, 10, 1)) == 2027


async def test_rates_builds_the_path_for_city_state_and_zip(monkeypatch):
    monkeypatch.setenv(p.KEY_ENV, "k")
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"], seen["params"] = url, params
        return CITY_BODY

    monkeypatch.setattr(p, "get_json", fake_get_json)
    p._cache._d.clear()
    out = await p.gsa_perdiem_rates(2026, city="Boise", state="id")
    assert seen["url"].endswith("/rates/city/Boise/state/ID/year/2026") and seen["params"] == {"api_key": "k"}
    assert out["returned"] == 1 and out["locations"][0]["city"] == "Boise" and out["link"].startswith("https://www.gsa.gov/") and "note" not in out
    p._cache._d.clear()
    await p.gsa_perdiem_rates(2026, state="ID")
    assert seen["url"].endswith("/rates/state/ID/year/2026")
    p._cache._d.clear()
    await p.gsa_perdiem_rates(2026, zip="83702")
    assert seen["url"].endswith("/rates/zip/83702/year/2026")
    p._cache._d.clear()
    await p.gsa_perdiem_rates(2026, city="Coeur d'Alene", state="ID")
    assert "/rates/city/Coeur%20d%27Alene/state/ID/" in seen["url"]


async def test_unlisted_city_returns_the_standard_rate_row(monkeypatch):
    monkeypatch.setenv(p.KEY_ENV, "k")

    async def fake_get_json(url, params=None, headers=None):
        return STATE_BODY

    monkeypatch.setattr(p, "get_json", fake_get_json)
    p._cache._d.clear()
    out = await p.gsa_perdiem_rates(2026, city="Moscow", state="ID")
    assert out["returned"] == 1 and out["locations"][0]["standard_rate"] is True and "Moscow" in out["note"]
    p._cache._d.clear()
    out = await p.gsa_perdiem_rates(2026, state="ID")
    assert out["returned"] == 3 and [loc["city"] for loc in out["locations"]] == ["Boise", "Coeur d'Alene", "Standard Rate"]


async def test_empty_answer_and_bad_input(monkeypatch):
    monkeypatch.setenv(p.KEY_ENV, "k")

    async def fake_get_json(url, params=None, headers=None):
        return EMPTY_BODY

    monkeypatch.setattr(p, "get_json", fake_get_json)
    p._cache._d.clear()
    out = await p.gsa_perdiem_rates(2026, zip="00000")
    assert out["returned"] == 0 and "note" in out
    assert "error" in await p.gsa_perdiem_rates(2026)
    assert "error" in await p.gsa_perdiem_rates(2026, city="Boise")
    assert "error" in await p.gsa_perdiem_rates(2026, state="Idaho")
    assert "error" in await p.gsa_perdiem_rates(2026, zip="837")
    assert "error" in await p.gsa_perdiem_rates(1999, state="ID")


async def test_mie_breakdown(monkeypatch):
    monkeypatch.setenv(p.KEY_ENV, "k")
    seen = {}

    async def fake_get_json(url, params=None, headers=None):
        seen["url"] = url
        return MIE_BODY

    monkeypatch.setattr(p, "get_json", fake_get_json)
    p._cache._d.clear()
    out = await p.gsa_perdiem_mie_breakdown(2026)
    assert seen["url"].endswith("/rates/conus/mie/2026") and out["returned"] == 3 and out["tiers"][0]["first_and_last_day"] == 51


async def test_without_a_key_the_tools_say_so(monkeypatch):
    monkeypatch.delenv(p.KEY_ENV, raising=False)
    p._cache._d.clear()
    assert "no API key" in (await p.gsa_perdiem_rates(2026, state="ID"))["error"]
    assert "no API key" in (await p.gsa_perdiem_mie_breakdown(2026))["error"]
    assert (await p.gsa_perdiem_index())["key"]["on_this_request"] is False


async def test_lists_tools():
    assert {t.name for t in await p.mcp.list_tools()} == {"gsa_perdiem_index", "gsa_perdiem_rates", "gsa_perdiem_mie_breakdown"}
