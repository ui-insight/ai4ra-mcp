"""ncura, offline from NCURA's public event listing captured 2026-10-16 (the upcoming nine, the past year's 46) and two event
pages (a regional meeting with early-bird and hotel, a virtual workshop): rows with code, title, dates, type and the registration
flag; a search by words; one event's deadlines, fees, description and location; the browser-like User-Agent; a list down said.
And the Regions VI & VII program, from Region VI's meeting page (cut to its program button) and the program PDF it linked on
2026-11-09: 102 rows by day, wrapped cells joined, a subset font's glyph decoded, a title printed in the description column, a
date that disagrees with its heading kept and said; the Markdown table and details; a page with no program link said."""

from pathlib import Path

from ai4ra_mcp.servers.ncura import server as n

FIX = Path(__file__).parent / "fixtures" / "ncura"
F = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}
PDF = (FIX / "program_rm26.pdf").read_bytes()
PDF_URL = "https://www.ncuraregionvi.org/_files/ugd/0b07d0_855acbcbec404b97967c4ae76ab623e3.pdf"


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
    assert {t.name for t in await n.mcp.list_tools()} == {"ncura_index", "ncura_events", "ncura_event", "ncura_program"}


async def test_list_down_is_said(monkeypatch):
    _site(monkeypatch, down=True)
    assert "503" in (await n.ncura_events())["error"] and "503" in (await n.ncura_event("2026REGION67"))["error"]
    assert "error" in (await n.ncura_index())["coverage"]


def _program_site(monkeypatch, page: str | None = None):
    calls = []

    async def get_text(url, params=None, headers=None):
        calls.append(url)
        assert url == n.MEETING and headers["User-Agent"].startswith("Mozilla/5.0")
        return F["meeting_rm2026"] if page is None else page

    async def get_bytes(url, params=None, headers=None):
        calls.append(url)
        assert url == PDF_URL
        return PDF

    monkeypatch.setattr(n, "get_text", get_text)
    monkeypatch.setattr(n, "get_bytes", get_bytes)
    n._cache._d.clear()
    return calls


def test_parse_program():
    prog = n.parse_program(PDF)
    s = prog["sessions"]
    assert prog["heading"] == "RM26 Program (update) - 11/06/2026" and len(s) == 102
    assert [d for d in dict.fromkeys(x["day"] for x in s)] == ["Sunday, November 8 - Workshops", "Monday, November 9 - Sessions",
                                                              "Tuesday, November 10 - Sessions", "Wednesday, November 11 - Sessions"]
    ai = next(x for x in s if x["title"] == "Augmenting Research Administration with AI")
    assert ai["track"] == "Workshop" and ai["level"] == "Post Award / Intermediate" and (ai["date"], ai["time"], ai["location"]) == ("8-Nov", "8:00 AM", "Curtis")
    assert ai["presenters"].startswith("Nathan Layman, Data Scientist, Office of Sponsored Programs, University of Idaho\nBert Baumgaertner")
    assert "primarily human-driven.\n\nParticipants will gain" in ai["description"] and ai["description"].startswith("Artificial intelligence is reshaping")
    first = s[0]  # a title, a level and a track wrapped over lines join with spaces
    assert first["title"] == "Same Mountain, Different Slopes: Navigating Communication with Intention" and first["level"] == "Workforce Wellness and Resilience / Basic"
    assert any(x["track"] == "Workforce Wellness and Resilience" for x in s) and any(x["track"] == "Agencies & Sponsors" for x in s)
    assert any(x["title"] == "Subaward Jeoparty: The Mane Event" for x in s)  # 'ty' is a glyph of a subset font, the 'S' sits lower
    dinner = next(x for x in s if x["title"] == "Dinner Groups")  # printed in the description column
    assert dinner["description"] is None and dinner["time"] == "6:00 PM - 9:00 PM" and dinner["day"].startswith("Monday")
    ug = next(x for x in s if x["title"] == "Uniform Guidance Reconstructed")
    assert ug["day"].startswith("Tuesday") and ug["date"] == "9-Nov" and ug["date_differs"] and sum(x["date_differs"] for x in s) == 1
    assert sum(1 for x in s if x["title"] == "Break") == 7 and all(x["time"] and x["title"] for x in s)


async def test_program_tool(monkeypatch):
    calls = _program_site(monkeypatch)
    out = await n.ncura_program()
    assert out["total"] == out["returned"] == 102 and out["program"] == "RM26 Program (update) - 11/06/2026" and calls == [n.MEETING, PDF_URL]
    assert out["source"]["program_pdf"] == PDF_URL and out["source"]["meeting_page"] == n.MEETING and out["source"]["event"].endswith("2026REGION67")
    md = out["markdown"]
    assert md.startswith("# RM26 Program (update) - 11/06/2026\n\n## Sunday, November 8 - Workshops\n\n| Time | Session | Track | Type | Level | Room |")
    assert "| 8:00 AM | Augmenting Research Administration with AI | Workshop | Workshop | Post Award / Intermediate | Curtis |" in md
    assert "| 10:30 AM (dated 9-Nov in the program) | Uniform Guidance Reconstructed |" in md and "Artificial intelligence" not in md
    sub = await n.ncura_program("subaward", "monday", details=True)
    assert sub["returned"] == 3 and len(calls) == 2  # cached
    assert "### 1:15 PM · Subaward Jeoparty: The Mane Event\nCompliance · Concurrent Session · Intermediate · Confluence C\n\n**Presenters:** Carrie Chesbro" in sub["markdown"]
    assert "## Tuesday" not in sub["markdown"] and (await n.ncura_program("Idaho"))["returned"] == 5 and (await n.ncura_program(day="workshops"))["returned"] == 7
    none = await n.ncura_program("nothing like this")
    assert none["returned"] == 0 and none["markdown"] is None


async def test_program_link_gone_is_said(monkeypatch):
    _program_site(monkeypatch, page="<html><body>Registration is Closed</body></html>")
    out = await n.ncura_program()
    assert "links no program PDF" in out["error"] and out["source"]["meeting_page"] == n.MEETING
