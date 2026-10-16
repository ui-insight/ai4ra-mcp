"""costs, offline from the main content of five www.uidaho.edu pages captured 2026-10-16 (student billing, account payments,
cost of attendance, SHIP, the insurance requirement): the page read into headings, accordions, lists and tables; the semester
schedule by student group without the summer and winter sections; summer per-credit rates; a cost of attendance table by
residency; the late fee dates and payment plan rules; the SHIP premium table; every answer naming its page and heading; a
page whose section is gone said."""

from pathlib import Path

from ai4ra_mcp.servers.costs import server as c

FIX = Path(__file__).parent / "fixtures" / "costs"
PAGES = {p.stem: p.read_text(encoding="utf-8") for p in FIX.glob("*.html")}


def _site(monkeypatch, calls: list | None = None, missing: set | None = None):
    calls = calls if calls is not None else []

    async def get_text(url, params=None, headers=None):
        calls.append(url)
        key = next(k for k, v in c.PAGES.items() if v["url"] == url)
        if missing and key in missing:
            raise ValueError(f"503 from www.uidaho.edu: {url}")
        return PAGES[key]

    monkeypatch.setattr(c, "get_text", get_text)
    c._cache._d.clear()
    return calls


def test_blocks_and_sections_read_the_page_as_it_reads():
    secs = c.sections(c.blocks(PAGES["billing"]))
    heads = [(s["level"], s["heading"]) for s in secs]
    assert (2, "2026-27 per semester tuition and fee schedule") in heads and (3, "Undergraduate") in heads and (2, "Late fees") in heads
    late = next(s for s in secs if s["heading"] == "Spring 2026 late fee schedule")
    assert late["path"] == ["Student billing", "Late fees", "Spring 2026 late fee schedule"] and late["blocks"][1]["kind"] == "list"
    assert c.split_item("Full-time (10-20 credits): $4,912") == {"name": "Full-time (10-20 credits)", "value": "$4,912"} and "note" in c.split_item("Refer to the class schedule")
    t = c.table([["", "In-state", "Out-of-state"], ["Tuition", "$1", "$2"]])
    assert t == {"columns": ["In-state", "Out-of-state"], "rows": [{"label": "Tuition", "In-state": "$1", "Out-of-state": "$2"}]}


async def test_tuition_schedules(monkeypatch):
    calls = _site(monkeypatch)
    out = await c.costs_tuition()
    assert out["year"] == "2026-27" and [g["students"] for g in out["groups"]] == ["Undergraduate", "Graduate", "Law", "In-service fees", "Student health insurance fee"]
    grad = out["groups"][1]["parts"][0]
    assert grad["group"].startswith("All graduate students") and grad["rates"][0]["items"][0] == {"name": "Full-time (9-20 credits)", "value": "$5,898"}
    assert out["source"]["url"] == c.PAGES["billing"]["url"] and out["source"]["heading"] == "2026-27 per semester tuition and fee schedule"
    ship = out["groups"][-1]
    assert ship["parts"] == [] and ship["text"][0].startswith("University of Idaho requires") and ship["see"].startswith("costs_insurance") and "see" not in grad
    law = await c.costs_tuition(students="law")
    assert [g["students"] for g in law["groups"]] == ["Law"] and len(calls) == 1  # cached
    summer = await c.costs_tuition("summer")
    items = summer["groups"][0]["parts"][0]["rates"][0]["items"]
    assert {"name": "Graduate", "value": "$618/credit"} in items and summer["source"]["heading"].startswith("Summer 2026")
    winter = await c.costs_tuition("winter")
    assert winter["groups"][0]["parts"][0]["rates"][0]["items"][0]["name"] == "Undergraduate"
    prior = await c.costs_tuition("prior")
    assert prior["year"] == "2025-26" and prior["groups"][0]["students"] == "Undergraduate"
    assert "error" in await c.costs_tuition("fall")


async def test_attendance_tables(monkeypatch):
    _site(monkeypatch)
    out = await c.costs_attendance("graduate")
    assert out["year"] == "2026-27" and out["total"] >= 1
    grad = next(x for x in out["costs"] if x["students"].startswith("Graduate student"))
    t = grad["tables"][0]
    assert t["columns"] == ["Idaho resident (In-state)", "Non-Idaho resident (Out-of-state)"] and t["rows"][0]["label"].startswith("Full-time tuition") and t["rows"][0]["Idaho resident (In-state)"] == "$11,796"
    assert t["rows"][-1]["label"] == "Total cost of attendance"
    mba = await c.costs_attendance("MBA")
    assert mba["total"] == 1 and "M.B.A." in mba["costs"][0]["students"] and mba["costs"][0]["under"][-1] == "Program-specific cost of attendance"
    assert (await c.costs_attendance())["total"] > 15 and out["source"]["url"] == c.PAGES["attendance"]["url"]


async def test_deadlines_and_insurance(monkeypatch):
    _site(monkeypatch)
    out = await c.costs_deadlines()
    spring = out["late_fees"]["terms"][0]
    assert spring["term"] == "Spring 2026 late fee schedule" and spring["parts"][0]["rates"][0]["items"][0] == {"name": "Wednesday, Jan. 28, 2026", "value": "Last day to pay or set up a payment plan before late fee begins."}
    assert any("due in full by the first day of the term" in d for d in out["due"]) and out["payment_plans"][0]["heading"] == "Payment plans"
    assert {s["page"] for s in out["sources"]} == {c.PAGES["billing"]["title"], c.PAGES["payments"]["title"]} and out["sources"][0]["url"].endswith("#late-fees")
    ins = await c.costs_insurance()
    costs = ins["ship_costs"]["parts"][0]
    assert costs["group"] == "2026-2027 SHIP costs" and costs["rates"][0]["table"]["rows"][0] == {"label": "Fall semester (includes coverage for winter break)", "Total Cost": "$1,171.50"}
    assert ins["dependent_and_spousal_coverage"]["parts"][0]["rates"][0]["table"]["rows"][0]["label"] == "Student only"
    assert ins["requirement"]["heading"] == "Student health insurance requirement" and len(ins["sources"]) == 2


async def test_a_page_down_or_reorganised_is_said(monkeypatch):
    _site(monkeypatch, missing={"billing"})
    out = await c.costs_tuition()
    assert "503" in out["error"] and out["source"]["url"] == c.PAGES["billing"]["url"]
    d = await c.costs_deadlines()
    assert "billing_error" in d and d["payment_plans"] and len(d["sources"]) == 1
    _site(monkeypatch)
    monkeypatch.setitem(c.SCHEDULES, "semester", r"^Tuition and fee schedule for next year$")
    out = await c.costs_tuition()
    assert "no heading matching" in out["error"]
    idx = await c.costs_index()
    assert "uidaho_rates" in " ".join(idx["notes"]) and len(c.PAGES) == 5
    assert {t.name for t in await c.mcp.list_tools()} == {"costs_index", "costs_tuition", "costs_attendance", "costs_deadlines", "costs_insurance"}
