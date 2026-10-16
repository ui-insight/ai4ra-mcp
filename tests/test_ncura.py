"""ncura, offline from NCURA's public event listing captured 2026-10-16 (the upcoming nine, the past year's 46) and two event
pages (a regional meeting with early-bird and hotel, a virtual workshop): rows with code, title, dates, type and the registration
flag; a search by words; one event's deadlines, fees, description and location; the browser-like User-Agent; a list down said."""

from pathlib import Path

from ai4ra_mcp.servers.ncura import server as n

FIX = Path(__file__).parent / "fixtures" / "ncura"
F = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}


def _site(monkeypatch, calls: list | None = None, down: bool = False):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        if down:
            raise ValueError(f"503 from {url}")
        if url == n.LIST:
            return F["year"] if params["sessionbegdate"].endswith("-400") else F["upcoming"]
        code = params["sessionaltcd"]
        return {"2026REGION67": F["event_region67"], "2026VIRFUNDPREOCT": F["event_virtual"]}.get(code, "<html><body>No event</body></html>")

    monkeypatch.setattr(n, "get_text", get_text)
    n._cache._d.clear()
    return calls


def test_parse_list_and_event():
    up, yr = n.parse_list(F["upcoming"]), n.parse_list(F["year"])
    assert len(up) == 9 and len(yr) == 46 and all(e["start"] and e["end"] and e["title"] for e in yr)
    r67 = next(e for e in up if e["code"] == "2026REGION67")
    assert r67 == {"code": "2026REGION67", "title": "Regional Meeting 2026: Regions VI & VII", "subtitle": "NCURA Regional meeting '26", "start": "2026-11-08", "end": "2026-11-11",
                   "dates": "11/8/2026 - 11/11/2026", "type": "REGSPRING", "registration": "closed", "featured": False, "register_link": None,
                   "check_form": {"text": "Please Click Here for the Check Registration Form", "url": "https://forms.gle/J22hGcMTKcc9hpTAA"},
                   "link": "https://www.ncura.edu/Education/MeetingsConferences/EventInfo.aspx?sessionaltcd=2026REGION67"}
    fund = up[0]
    assert fund["code"] == "2026VIRFUNDPREOCT" and fund["type"] == "FUND" and fund["registration"] == "open" and fund["subtitle"].startswith("Level I") and fund["check_form"]["url"].endswith(".pdf")
    assert {e["type"] for e in yr} >= {"ANNUAL", "DRA", "FRA", "FUND", "PRA", "REGSPRING"} and {e["registration"] for e in yr} == {"open", "closed"}
    ev = n.parse_event(F["event_region67"], "2026REGION67")
    assert ev["title"] == "Regional Meeting 2026: Regions VI & VII" and ev["start"] == "2026-11-08" and ev["end"] == "2026-11-11" and ev["type"] == "REGSPRING"
    assert ev["early_bird_deadline"] == "2026-10-08" and ev["registration_deadline"] == "2026-11-04" and ev["description"].startswith("At this time registration")
    assert ev["fees"][0] == {"what": "Member Full Conference Early", "amount": "$800.00"} and len(ev["fees"]) == 4
    assert ev["location"] == {"venue": "The Westin Denver Downtown", "address": ["1672 Lawrence Street", "Denver, CO 80202"], "hotel_link": "https://book.passkey.com/event/51194580/owner/3485/home"}
    v = n.parse_event(F["event_virtual"], "2026VIRFUNDPREOCT")
    assert v["early_bird_deadline"] is None and v["registration_deadline"] == "2026-10-19" and v["location"]["venue"] == "Virtual Experience" and v["location"]["hotel_link"] is None
    assert {"what": "Member Registration Only", "amount": "$400.00"} in v["fees"]


async def test_tools(monkeypatch):
    calls = _site(monkeypatch)
    out = await n.ncura_events()
    assert out["total"] == 9 and out["events"][0]["code"] == "2026VIRFUNDPREOCT" and out["events"][-1]["code"] == "2027PRACONFER" and out["source"]["calendar"] == n.CALENDAR
    assert calls[0][1]["sessionbegdate"] == ">getdate()-1" and calls[0][1]["ONWEBFLG"] == "Y" and calls[0][2]["User-Agent"].startswith("Mozilla/5.0")
    assert [e["code"] for e in (await n.ncura_events("region vi"))["events"]] == ["2026REGION67"] and n.matches(["pre", "award"], "Part I: Pre-Award Live") and not n.matches(["vi"], "Irving") and (await n.ncura_events("virtual"))["total"] >= 3 and (await n.ncura_events("FRA"))["events"][0]["type"] in ("FRA", None) and len(calls) == 1
    yr = await n.ncura_events(when="year", rows=10)
    assert yr["total"] == 46 and yr["returned"] == 10 and yr["events"][0]["start"] < "2026-01-01" and len(calls) == 2
    assert "error" in await n.ncura_events(when="tomorrow")
    ev = await n.ncura_event("2026region67")
    assert ev["code"] == "2026REGION67" and ev["fees"][2]["what"] == "Non Member Full Conference Early" and ev["source"]["page"] == ev["link"] and calls[-1][1] == {"sessionaltcd": "2026REGION67"}
    assert "no event" in (await n.ncura_event("2026NOPE"))["error"] and "error" in await n.ncura_event("a b")
    idx = await n.ncura_index()
    assert idx["coverage"]["upcoming"] == 9 and "FUND" in idx["coverage"]["types"] and "Region VI" in " ".join(idx["notes"])
    assert {t.name for t in await n.mcp.list_tools()} == {"ncura_index", "ncura_events", "ncura_event"}


async def test_list_down_is_said(monkeypatch):
    _site(monkeypatch, down=True)
    assert "503" in (await n.ncura_events())["error"] and "503" in (await n.ncura_event("2026REGION67"))["error"]
    assert "error" in (await n.ncura_index())["coverage"]
