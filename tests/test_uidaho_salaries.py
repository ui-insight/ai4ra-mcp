"""uidaho_salaries, offline: the newest budget book's 'Employee salaries' link picked past a year marked coming soon, the
salary book's lines read with the department lines above them (name, title, FY or AY basis, salary, administrative
stipend), a search by name, title or department, and the book's year, as-of date and link on every answer. The lines
here are made in the book's shape; the real book is a public record read live."""

from ai4ra_mcp.servers.uidaho import server as u

PAGE = """<h3>FY2027 Budget books</h3><p>Employee salaries (coming soon)</p>
<h3>FY2026 Budget books</h3><p><a href="https://content-hub.uidaho.edu/api/public/content/abc?v=1">Employee salaries</a> Faculty, exempt and classified salaries</p>
<h3>FY2025 Budget books</h3><p><a href="https://content-hub.uidaho.edu/api/public/content/old?v=2">Employee salaries</a></p>"""

BOOK = """[page 1]
EMPLOYEE
SALARIES
OPERATING BUDGETS
FY2025 - 2026

[page 2]
FY2026 SALARIES AS OF MAY 14, 2025
Name Title Rank Yr. Type FY2026 SalaryAdmin Stipend
2060 - Research
UR University Research - 3980
UR Office of Sponsored Programs
Doe, Jane Q. Sponsored Programs Administrator FY 63,523.20
Roe, Richard Accountant II FY 62,836.80
RCI Research Centers and Institutes - 3979
RCI Inst for Interdisc Data Sci
Fictional, Pat C. Research Administration Data FY 92,518.40
2020 - Provost
CALS College of Agricultural & Life Sci - 3970
CALS Plant Sciences
Example, Sam Assoc Program Director Associate Professor AY 96,947.20Yes
Long Surname Cut, Head Research Scientist FY 76,065.60
1
"""


def test_pick_salary_book_and_parse():
    assert u.pick_salary_book(PAGE) == (2026, "https://content-hub.uidaho.edu/api/public/content/abc?v=1")
    assert u.pick_salary_book("<h3>FY2027 Budget books</h3><p>coming soon</p>") is None
    book = u.parse_salary_book(BOOK)
    assert book["fiscal_year"] == 2026 and book["as_of"] == "MAY 14, 2025" and len(book["rows"]) == 5
    jane = book["rows"][0]
    assert jane == {"name": "Doe, Jane Q.", "title": "Sponsored Programs Administrator", "who": "Doe, Jane Q. Sponsored Programs Administrator", "basis": "FY", "salary_usd": 63523.2, "admin_stipend": False,
                    "division": "2060 - Research", "unit": "UR University Research - 3980", "department": "UR Office of Sponsored Programs"}
    sam = book["rows"][3]
    assert sam["name"] == "Example, Sam" and sam["title"] == "Assoc Program Director Associate Professor" and sam["basis"] == "AY" and sam["admin_stipend"] and sam["department"] == "CALS Plant Sciences"
    cut = book["rows"][4]
    assert cut["who"] == "Long Surname Cut, Head Research Scientist" and cut["salary_usd"] == 76065.6  # a name the book cut short keeps the raw line


async def test_search_by_name_title_or_department(monkeypatch):
    async def fake_book():
        return {**u.parse_salary_book(BOOK), "book_year": 2026, "url": "https://content-hub.uidaho.edu/api/public/content/abc?v=1"}

    monkeypatch.setattr(u, "_salary_book", fake_book)
    out = await u.uidaho_salaries("fictional")
    assert out["total"] == 1 and out["positions"][0]["salary_usd"] == 92518.4 and out["fiscal_year"] == 2026 and out["as_of"] == "MAY 14, 2025"
    assert out["source"]["url"].endswith("abc?v=1") and out["source"]["linked_from"] == u.SALARIES_PAGE and "FY2026" in out["source"]["book"]
    assert (await u.uidaho_salaries("sponsored programs"))["total"] == 2 and (await u.uidaho_salaries("research scientist"))["total"] == 1
    assert (await u.uidaho_salaries("Associate Professor Plant"))["positions"][0]["name"] == "Example, Sam"
    assert (await u.uidaho_salaries("nobody here"))["total"] == 0 and "error" in await u.uidaho_salaries("")
    two = await u.uidaho_salaries("Research", rows=1)
    assert two["returned"] == 1 and two["total"] >= 2


async def test_a_page_without_the_book_is_said(monkeypatch):
    async def no_book():
        raise ValueError("the budget-planning page links no 'Employee salaries' budget book today")

    monkeypatch.setattr(u, "_salary_book", no_book)
    out = await u.uidaho_salaries("Doe")
    assert "no 'Employee salaries'" in out["error"] and out["linked_from"] == u.SALARIES_PAGE
    assert "uidaho_salaries" in {t.name for t in await u.mcp.list_tools()}
