"""nihdates, offline from the main content of grants.nih.gov's standard due dates and salary cap pages captured 2026-10-16: the
due dates table as rows with codes and application kinds, a code's rows and a series, the cycles table, the page's own
updated date, the salary cap by fiscal year with its notice, the cap on a date, and what is said when no period covers today."""

from datetime import date
from pathlib import Path

from ai4ra_mcp.servers.nihdates import server as n

FIX = Path(__file__).parent / "fixtures" / "nihdates"
DUE = (FIX / "due.html").read_text(encoding="utf-8")
CAP = (FIX / "cap.html").read_text(encoding="utf-8")


def _site(monkeypatch, broken: bool = False):
    async def get_text(url, params=None, headers=None):
        if broken:
            return "<html><body><main><p>Page moved</p></main></body></html>"
        return DUE if url == n.DUE_URL else CAP

    monkeypatch.setattr(n, "get_text", get_text)
    n._cache._d.clear()


def test_parse_due_reads_both_tables():
    d = n.parse_due(DUE)
    assert len(d["due"]) == 17 and d["updated"] == "March 24, 2026" and "no longer have dedicated AIDS" in d["aids_note"]
    r01 = [r for r in d["due"] if "R01" in r["activity_codes"]]
    assert [(r["applications"], r["cycle_1"], r["cycle_3"]) for r in r01] == [(["new"], "February 5", "October 5"), (["renewal", "resubmission", "revision"], "March 5", "November 5")]
    u01 = next(r for r in d["due"] if "U01" in r["activity_codes"] and r["applications"] == ["new"])
    assert (u01["cycle_1"], u01["cycle_2"], u01["cycle_3"]) == ("February 5", "June 5", "October 5")  # the form column spliced in is dropped
    assert d["cycles"][0] == {"what": "Application Due Dates", "cycle_1": "January 25 - May 7", "cycle_2": "May 25 - September 7", "cycle_3": "September 25 - January 7"}
    assert any("series" in c for r in d["due"] for c in r["activity_codes"])


def test_parse_cap_reads_every_fiscal_year():
    caps = n.parse_cap(CAP)
    assert caps[0]["fiscal_year"] == 2026 and caps[-1]["fiscal_year"] == 1990 and len(caps) == 30
    assert caps[0]["periods"][1] == {"from": "2026-01-01", "to": "2026-09-30", "level": "Executive Level II", "amount_usd": 228000, "text": "January 1, 2026 through September 30, 2026 (Executive Level II): $228,000"}
    assert caps[1]["notice"] == "NOT-OD-25-085" and caps[1]["notice_link"] == "https://grants.nih.gov/grants/guide/notice-files/NOT-OD-25-085.html"
    assert n.cap_on(caps, date(2024, 3, 1))["amount_usd"] == 221900 and n.cap_on(caps, date(2024, 3, 1))["fiscal_year"] == 2024 and n.cap_on(caps, date(2030, 1, 1)) is None


async def test_tools(monkeypatch):
    _site(monkeypatch)
    out = await n.nihdates_due("r21")
    assert out["total"] == 2 and all("R21" in r["activity_codes"] for r in out["due"]) and out["source"] == {"url": n.DUE_URL, "page_updated": "March 24, 2026", "read": date.today().isoformat(), "note": out["source"]["note"]}
    assert (await n.nihdates_due("K08"))["total"] == 2 and (await n.nihdates_due("F31"))["total"] == 1 and (await n.nihdates_due("T32"))["total"] == 1
    none = await n.nihdates_due("Z99")
    assert none["total"] == 0 and "opportunity" in none["note"]
    assert (await n.nihdates_due())["total"] == 17
    cy = await n.nihdates_cycles()
    assert len(cy["cycles"]) == 9 and cy["cycles"][1]["what"] == "Scientific Merit Review"
    cap = await n.nihdates_salary_cap(2024)
    assert cap["years"][0]["fiscal_year"] == 2024 and cap["years"][0]["periods"][1]["amount_usd"] == 221900
    assert "lists no FY" in (await n.nihdates_salary_cap(1980))["error"]
    every = await n.nihdates_salary_cap()
    assert len(every["years"]) == 30 and (every["in_force"] is not None or every["latest"]["fiscal_year"] == 2026 and "latest posted" in every["in_force_note"])
    idx = await n.nihdates_index()
    assert "NOT-OD-26-029" in " ".join(idx["notes"])
    assert {t.name for t in await n.mcp.list_tools()} == {"nihdates_index", "nihdates_due", "nihdates_cycles", "nihdates_salary_cap"}


async def test_a_reorganised_page_is_said(monkeypatch):
    _site(monkeypatch, broken=True)
    out = await n.nihdates_due("R01")
    assert "none of the rows" in out["error"] and out["source"]["url"] == n.DUE_URL
    assert "none of the rows" in (await n.nihdates_salary_cap())["error"]
