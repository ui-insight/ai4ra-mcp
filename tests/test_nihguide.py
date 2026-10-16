"""nihguide, offline from the search service's answers, a notice page and the weekly index captured on 2026-10-16: a hit
slimmed, a notice page read to its fields and purpose, the weekly index read to its groups, the parameters a search
sends (kind to type, institute to primaryic, dates to MMDDYYYY), paging, and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.nihguide import server as ng

FIX = Path(__file__).parent / "fixtures" / "nihguide"
NOTICES = json.loads((FIX / "notices.json").read_text(encoding="utf-8"))
OPPS = json.loads((FIX / "opps.json").read_text(encoding="utf-8"))
PAGES = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}


def _site(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        return OPPS if params["type"].startswith("active") else NOTICES

    async def get_text(url, params=None, headers=None):
        calls.append((url, dict(params or {})))
        if url.endswith("NOT-OD-25-163.html"):
            return PAGES["notice"]
        if url == ng.WEEKLY:
            return PAGES["weekly"]
        raise ValueError(f"404 from {url}: nothing at that address")

    monkeypatch.setattr(ng, "get_json", get_json)
    monkeypatch.setattr(ng, "get_text", get_text)
    ng._cache._d.clear()
    return calls


def test_a_hit_is_slimmed_and_linked():
    h = ng.slim_hit(NOTICES["data"]["hits"]["hits"][1])
    assert h["number"] == "NOT-OD-26-118" and h["kind"] == "notice" and h["doctype"] == "NOT" and h["released"] == "2026-10-08" and h["expires"] is None
    assert h["institute"] == "OD" and h["notice_subject"] == "Request for Information" and h["purpose"].startswith("The National Institutes of Health") and h["link"] == ng.GUIDE + "notice-files/NOT-OD-26-118.html"
    o = ng.slim_hit(OPPS["data"]["hits"]["hits"][0])
    assert o["kind"] == "opportunity" and o["status"] == "active" and o["doctype"] == "RFA" and o["activity_codes"] == ["T15"] and o["expires"] == "2027-02-12" and o["link"] == ng.GUIDE + "rfa-files/RFA-LM-28-001.html"
    assert ng.doc_link("PAR-26-012") == ng.GUIDE + "pa-files/PAR-26-012.html"


def test_a_notice_page_is_read_to_its_fields():
    n = ng.parse_notice(PAGES["notice"])
    assert n["number"] == "NOT-OD-25-163" and n["title"] == "Updated NIH Policy on Allowable Costs for Animals" and n["release_date"] == "September 25, 2025" and n["related_announcements"] == [] and n["issued_by"][0].startswith("NATIONAL INSTITUTES OF HEALTH")
    assert n["purpose"][0].startswith("This notice alerts the extramural research community") and any("Inquiries" not in p for p in n["purpose"])
    assert n["inquiries"][0].startswith("Please direct all inquiries") and not any("@" in x or "[email" in x for x in n["inquiries"])


def test_the_weekly_index_is_read_to_groups():
    w = ng.parse_weekly(PAGES["weekly"])
    assert w["week_ending"] == "October 16, 2026" and w["total"] >= 1
    first = w["groups"][0]
    assert first["group"] == "General Notices" and first["notices"][0] == {"number": "NOT-OD-26-130", "title": "Request for Information (RFI): Opportunities to Reduce Administrative Burden in NIH Extramural Research",
                                                                            "organization": "Office of the Director, NIH", "link": "https://grants.nih.gov/grants/guide/notice-files/NOT-OD-26-130.html"}


async def test_search_sends_the_service_its_parameters(monkeypatch):
    calls = _site(monkeypatch)
    out = await ng.nihguide_search("administrative burden", institute="od", from_date="2019-01-01", to_date="2026-10-16", rows=3)
    url, p = calls[-1]
    assert url == ng.SERVICE + "/data" and p["type"] == "notices" and p["query"] == "administrative burden" and p["sort"] == "_score" and p["primaryic"] == "OD" and p["daterange"] == "01012019-10162026" and p["perpage"] == 3 and p["from"] == 0
    assert out["total"] == 1450 and out["returned"] == 3 and out["next_start"] == 3 and out["results"][0]["number"] == "NOT-OD-19-136"
    out = await ng.nihguide_search(kind="open", start=20)
    assert calls[-1][1]["type"] == "active,activenosis" and calls[-1][1]["sort"] == "reldate:desc" and calls[-1][1]["from"] == 20 and out["results"][0]["kind"] == "opportunity"
    assert "error" in await ng.nihguide_search(kind="everything") and "error" in await ng.nihguide_search(from_date="last year")


async def test_a_notice_and_the_week(monkeypatch):
    calls = _site(monkeypatch)
    out = await ng.nihguide_notice("not-od-25-163")
    assert out["number"] == "NOT-OD-25-163" and out["release_date"] == "September 25, 2025" and out["link"] == ng.GUIDE + "notice-files/NOT-OD-25-163.html"
    missing = await ng.nihguide_notice("NOT-OD-99-999")
    assert missing["error"].startswith("no Guide page for NOT-OD-99-999")
    assert "error" in await ng.nihguide_notice("12345")
    w = await ng.nihguide_weekly()
    assert w["week_ending"] == "October 16, 2026" and calls[-1][1] == {} and w["link"] == ng.WEEKLY
    w = await ng.nihguide_weekly("2026-10-09")
    assert calls[-1][1] == {"WeekEnding": "10-09-2026"} and w["link"].endswith("?WeekEnding=10-09-2026")
    assert "error" in await ng.nihguide_weekly("Friday")


async def test_the_index_and_the_tools():
    out = await ng.nihguide_index()
    assert "undocumented" in out["upstream"] and any("Grants.gov" in n for n in out["notes"])
    assert {t.name for t in await ng.mcp.list_tools()} == {"nihguide_index", "nihguide_search", "nihguide_notice", "nihguide_weekly"}
