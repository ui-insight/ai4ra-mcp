"""congress, offline from answers captured from the API on 2026-10-16: a bill's record with its summary and text versions
assembled from three calls, its actions paged, the bill and law lists with their windows, a state's members, the key as
a header, a missing key, and bad input."""

import json
from pathlib import Path

from ai4ra_mcp.servers.congress import server as cg

FIX = Path(__file__).parent / "fixtures" / "congress"
PAGES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FIX.glob("*.json")}


def _api(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_json(url, params=None, headers=None):
        calls.append((url, dict(params or {}), dict(headers or {})))
        path = url[len(cg.BASE) + 1:]
        if path == "bill/119/hr/1":
            return PAGES["bill"]
        if path == "bill/119/hr/1/actions":
            return PAGES["actions"]
        if path == "bill/119/hr/1/summaries":
            return PAGES["summaries"]
        if path == "bill/119/hr/1/text":
            return PAGES["text"]
        if path == "law/119":
            return PAGES["laws"]
        if path == "member/ID":
            return PAGES["members"]
        if path in ("bill/119", "bill/119/hr"):
            return PAGES["bills"]
        raise ValueError(f"404 from {url}: nothing at that address")

    monkeypatch.setattr(cg, "get_json", get_json)
    monkeypatch.setenv(cg.KEY_ENV, "k-congress")
    cg._cache._d.clear()
    return calls


async def test_a_bill_is_assembled_from_its_record_summary_and_text(monkeypatch):
    calls = _api(monkeypatch)
    out = await cg.congress_bill(119, "HR", 1)
    assert [c[0][len(cg.BASE) + 1:] for c in calls] == ["bill/119/hr/1", "bill/119/hr/1/summaries", "bill/119/hr/1/text"] and all(c[2] == {"X-Api-Key": "k-congress"} and c[1]["format"] == "json" for c in calls)
    assert out["title"].startswith("An act to provide for reconciliation") and out["laws"] == [{"number": "119-21", "type": "Public Law"}] and out["latest_action"]["text"] == "Became Public Law No: 119-21."
    assert out["sponsors"][0]["name"].startswith("Rep. Arrington") and out["policy_area"] == "Economics and Public Finance" and out["counts"]["actions"] == 59
    assert out["summary"]["text"].startswith("One Big Beautiful Bill Act") and "<" not in out["summary"]["text"] and out["text_versions"][0]["version"] == "Enrolled Bill" and "PDF" in out["text_versions"][0]["formats"]
    assert out["link"] == "https://www.congress.gov/bill/119th-congress/house-bill/1"
    assert "k-congress" not in repr(list(cg._cache._d.keys()))
    assert (await cg.congress_bill(119, "hr", 99999))["error"] == "no bill HR 99999 in the 119th Congress"
    assert "error" in await cg.congress_bill(119, "bill", 1) and "error" in await cg.congress_bill(12, "hr", 1) and "error" in await cg.congress_bill(119, "hr", 0)


async def test_actions_bills_laws_and_members(monkeypatch):
    calls = _api(monkeypatch)
    a = await cg.congress_bill_actions(119, "hr", 1, rows=3)
    assert calls[-1][1]["limit"] == 3 and a["total"] == 59 and a["actions"][0]["text"] == "Became Public Law No: 119-21." and a["next_offset"] == len(a["actions"]) and a["link"].endswith("/all-actions")
    b = await cg.congress_bills(119, "hr", from_date="2026-01-01", rows=3)
    assert calls[-1][0].endswith("/bill/119/hr") and calls[-1][1]["fromDateTime"] == "2026-01-01T00:00:00Z" and calls[-1][1]["sort"] == "updateDate desc" and b["total"] == 8595 and b["bills"][0]["number"]
    assert "error" in await cg.congress_bills(119, "bills") and "error" in await cg.congress_bills(119, from_date="January")
    laws = await cg.congress_laws(119, rows=3)
    assert laws["total"] == 126 and laws["laws"][0]["laws"][0]["type"] == "Public Law"
    m = await cg.congress_members("id")
    assert m["total"] == 4 and {x["chamber"] for x in m["members"]} == {"House of Representatives", "Senate"} and m["members"][0]["link"].startswith("https://www.congress.gov/member/")
    assert "error" in await cg.congress_members("Idaho")


async def test_a_missing_key_is_refused(monkeypatch):
    _api(monkeypatch)
    monkeypatch.delenv(cg.KEY_ENV, raising=False)
    for out in (await cg.congress_bill(119, "hr", 1), await cg.congress_bill_actions(119, "hr", 1), await cg.congress_bills(), await cg.congress_laws(), await cg.congress_members("ID")):
        assert out["error"].startswith("no API key on this request")
    idx = await cg.congress_index()
    assert idx["key"]["required"] is True and any("no word search" in n for n in idx["notes"])
    assert {t.name for t in await cg.mcp.list_tools()} == {"congress_index", "congress_bill", "congress_bill_actions", "congress_bills", "congress_laws", "congress_members"}
