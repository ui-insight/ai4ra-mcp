"""omb, offline from the main content of whitehouse.gov's memoranda page and the 2025 and 2024 sections of the archived prior
page, captured 2026-10-16: the entries under each year with number, title, date and PDF; the two lists merged newest first
with the current page preferred for a number on both; a rescission named in referenced_by; a search by year and words; one
memorandum by number in its several spellings; the browser-like User-Agent sent; a list page down said."""

from pathlib import Path

from ai4ra_mcp.servers.omb import server as o

FIX = Path(__file__).parent / "fixtures" / "omb"
CURRENT = (FIX / "current.html").read_text(encoding="utf-8")
ARCHIVE = (FIX / "archive.html").read_text(encoding="utf-8")


def _site(monkeypatch, calls: list | None = None, down: set | None = None):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append((url, dict(headers or {})))
        if down and url in down:
            raise ValueError(f"503 from {url}")
        return CURRENT if url == o.CURRENT else ARCHIVE

    monkeypatch.setattr(o, "get_text", get_text)
    o._cache._d.clear()
    return calls


def test_parse_and_merge():
    cur = o.parse_list(CURRENT, "current")
    arc = o.parse_list(ARCHIVE, "archive")
    assert cur[0]["number"] == "M-26-19" and cur[0]["date"] == "2026-09-10" and cur[0]["year"] == 2026 and cur[0]["pdf"].endswith("M-26-19-Amendment-to-OMB-Memorandum-M-16-13.pdf")
    assert cur[0]["title"] == "Amendment to OMB Memorandum M-16-13"
    m2411 = next(m for m in arc if m["number"] == "M-24-11")
    assert m2411["title"].startswith("Reducing Burden") and m2411["date"] == "2024-04-04" and m2411["pages"] == 9 and m2411["source"] == "archive"
    rows = o.merge(cur, arc)
    assert rows[0]["number"] == "M-26-19" and rows == sorted(rows, key=lambda m: (m["date"] or "", m["number"]), reverse=True)
    numbers = [m["number"] for m in rows]
    assert len(numbers) == len(set(numbers))  # a 2025 memorandum on both lists is one row
    both = [m for m in rows if m["year"] == 2025 and m["source"] == "current"]
    assert both and not [m for m in rows if m["number"] in {b["number"] for b in both} and m["source"] == "archive"]
    assert next(m for m in rows if m["number"] == "M-25-13")["referenced_by"] == ["M-25-14"]


async def test_search_and_one(monkeypatch):
    calls = _site(monkeypatch)
    out = await o.omb_memoranda(query="financial assistance")
    assert out["total"] >= 2 and all("financial assistance" in m["title"].lower() for m in out["memoranda"]) and out["memoranda"][0]["date"] >= out["memoranda"][-1]["date"]
    assert all(h["User-Agent"].startswith("Mozilla/5.0") for _, h in calls) and {u for u, _ in calls} == {o.CURRENT, o.ARCHIVE}
    y = await o.omb_memoranda(year=2024, rows=5)
    assert y["returned"] == 5 and all(m["year"] == 2024 for m in y["memoranda"]) and y["total"] > 5 and len(calls) == 2  # cached
    one = await o.omb_memorandum("m 25 13")
    assert one["number"] == "M-25-13" and one["referenced_by"][0]["title"] == "Rescission of M-25-13" and one["list_page"] == o.CURRENT
    assert (await o.omb_memorandum("24-11"))["title"].startswith("Reducing Burden")
    assert "not on either list" in (await o.omb_memorandum("M-19-99"))["error"] and "error" in await o.omb_memorandum("twelve")
    idx = await o.omb_index()
    assert idx["coverage"].startswith("2024 to 2026") and idx["errors"] is None
    assert {t.name for t in await o.mcp.list_tools()} == {"omb_index", "omb_memoranda", "omb_memorandum"}


async def test_one_list_down_is_said_and_the_other_used(monkeypatch):
    _site(monkeypatch, down={o.ARCHIVE})
    out = await o.omb_memoranda(year=2026)
    assert out["total"] > 10 and "503" in out["source"]["errors"]["archive"]
    _site(monkeypatch, down={o.CURRENT, o.ARCHIVE})
    assert "neither memoranda page answered" in (await o.omb_memoranda())["error"]
