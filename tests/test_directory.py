"""directory, offline from pages captured at directory.uidaho.edu on 2026-10-15 (result rows anonymised, the page's internal
identifiers zeroed): a results table read to its visible cells and paged; one match read as the person's details with a
phone 'Not listed' as null; no match said; a department resolved against the form's list (exact, one partial, several, none);
rows rounded to the form's page sizes; a page that is neither a table nor a person reported with its route; and nothing of
the page's internal identifier anywhere in what a tool returns or keeps."""

import json
from pathlib import Path

import pytest

from ai4ra_mcp.servers.directory import directory
from ai4ra_mcp.servers.directory import server as d

FIX = Path(__file__).parent / "fixtures" / "directory"
PAGES = {name: (FIX / f"{name}.html").read_text(encoding="utf-8") for name in ("search_one", "search_many", "search_two", "search_none", "advanced")}


def _site(monkeypatch, calls: list | None = None):
    """The live site stood in for: the advanced form, and a results page chosen by the LastName and email sent."""
    calls = calls if calls is not None else []

    async def get(route, params=None):
        calls.append((route, dict(params or {})))
        if route == "advanced":
            return PAGES["advanced"]
        if route == "nothing":
            raise directory.DirectoryError(route, 404, "not the 200 the route returns")
        p = {k: (v.lower() if isinstance(v, str) else v) for k, v in (params or {}).items()}  # the site matches names regardless of case
        if p.get("email", "").startswith("nlayman") or (p.get("LastName") == "layman" and p.get("FirstName") == "nathan"):
            return PAGES["search_one"]
        if p.get("LastName") == "lay":
            return PAGES["search_two"]
        if p.get("LastName") == "smith" or p.get("dept") == "office of sponsored programs":
            return PAGES["search_many"]
        if p.get("LastName") == "broken":
            return "<html><body class='Cdir_x'>something else</body></html>"
        return PAGES["search_none"]

    monkeypatch.setattr(directory, "_get", get)
    d._cache._d.clear()
    return calls


def test_a_results_table_is_read_to_its_visible_cells():
    found = directory.parse_results(PAGES["search_many"])
    assert found["total"] == 22 and len(found["people"]) == 10
    assert found["people"][0] == {"name": "Example, Person01", "email": "person01@uidaho.edu", "phone": "208-885-0001",
                                  "department": "Earth and Spatial Sciences", "status": "Faculty or Staff"}
    assert all(set(p) == {"name", "email", "phone", "department", "status"} for p in found["people"])


def test_one_match_is_the_person_s_details_with_an_unlisted_phone_as_null():
    found = directory.parse_results(PAGES["search_one"])
    assert found["total"] == 1
    assert found["people"][0] == {"name": "Layman, Nathan", "phone": None, "email": "nlayman@uidaho.edu", "title": "Research Administration Data S",
                                  "department": "Office of Sponsored Programs", "office": "LSS 280", "campus_zip": "3051"}


def test_no_match_and_a_short_page_are_read():
    assert directory.parse_results(PAGES["search_none"]) == {"total": 0, "people": []}
    two = directory.parse_results(PAGES["search_two"])
    assert two["total"] == 2 and [p["name"] for p in two["people"]] == ["Example, Person01", "Example, Person02"]


def test_a_page_that_is_neither_is_reported_with_its_route():
    with pytest.raises(directory.DirectoryError) as e:
        directory.parse_results("<html><body>Cdir_ but nothing else</body></html>")
    assert e.value.route == "search" and "neither a results table nor a person's details" in str(e.value)
    err = e.value.as_error()
    assert err["upstream"] == directory.BASE + "search" and "not a published API" in err["note"]


def test_the_form_s_departments_are_listed_without_all():
    names = [v for v in directory._OPTION.findall(directory._SELECT.search(PAGES["advanced"]).group(0)) if v and v != "All"]
    assert len(names) == 250 and "Office of Sponsored Programs" in names and "All" not in names


@pytest.mark.parametrize("rows,depth", [(1, 10), (10, 10), (11, 20), (20, 20), (21, 30), (30, 30), (99, 30)])
def test_rows_round_up_to_the_form_s_page_sizes(rows, depth):
    assert directory.depth_for(rows) == depth


async def test_a_search_pages_and_sends_the_form_s_fields(monkeypatch):
    calls = _site(monkeypatch)
    out = await d.directory_search(last_name="Smith", rows=10, start=0)
    assert out["total"] == 22 and len(out["people"]) == 10 and out["next_start"] == 10 and out["query"] == {"last_name": "Smith"}
    route, params = calls[-1]
    assert route == "search" and params == {"tab": "advanced", "pt": "emp", "FirstName": "", "LastName": "Smith", "email": "", "dept": "All", "major": "All", "depth": 10, "offset": 0}
    out = await d.directory_search(last_name="Smith", sounds_like=True, rows=25, start=20)
    assert calls[-1][1]["SoundsLike"] == "on" and calls[-1][1]["depth"] == 30 and calls[-1][1]["offset"] == 20
    assert "next_start" not in await d.directory_search(last_name="lay")
    assert "error" in await d.directory_search()


async def test_one_match_comes_back_as_details_and_a_department_resolves_against_the_list(monkeypatch):
    calls = _site(monkeypatch)
    out = await d.directory_search(email="nlayman")
    assert out["total"] == 1 and out["people"][0]["title"] == "Research Administration Data S" and "details" in out["note"]
    out = await d.directory_search(department="sponsored programs")
    assert out["query"]["department"] == "Office of Sponsored Programs" and calls[-1][1]["dept"] == "Office of Sponsored Programs"
    assert [r for r, _ in calls].index("advanced") < len(calls) - 1 and [r for r, _ in calls].count("advanced") == 1  # fetched once, before the search, then cached
    out = await d.directory_search(department="office of")
    assert out["total"] == 0 and len(out["departments_matched"]) > 1 and "pass one name in full" in out["error"]
    out = await d.directory_search(department="zzqx")
    assert out["departments_matched"] == [] and "no department matching" in out["error"]


async def test_a_person_is_one_match_several_or_none(monkeypatch):
    _site(monkeypatch)
    one = await d.directory_person(last_name="Layman", first_name="Nathan")
    assert one["person"]["email"] == "nlayman@uidaho.edu" and one["person"]["office"] == "LSS 280"
    several = await d.directory_person(last_name="Smith")
    assert several["total"] == 22 and len(several["people"]) == 10 and "narrow by" in several["error"]
    none = await d.directory_person(last_name="zzqxv")
    assert none["total"] == 0 and "not an employee" in none["error"]


async def test_the_departments_tool_and_a_broken_route(monkeypatch):
    _site(monkeypatch)
    deps = await d.directory_departments()
    assert deps["total"] == 250 and deps["departments"][0] != "All"
    assert "error" in await d.directory_search(last_name="broken")


async def test_nothing_of_the_page_s_internal_identifier_is_returned_or_kept(monkeypatch):
    """The fixtures carry the identifier zeroed; the live page carries a number. Neither reaches a result or the cache."""
    _site(monkeypatch)
    for out in (await d.directory_search(last_name="Smith"), await d.directory_search(email="nlayman"), await d.directory_person(last_name="lay")):
        assert "pidm" not in json.dumps(out).lower()
    assert "pidm" not in json.dumps(list(d._cache._d.keys())).lower()
    live_shape = PAGES["search_many"].replace('data-pidm="0"', 'data-pidm="1046538"').replace("pidm=0", "pidm=1046538")
    assert "1046538" not in json.dumps(directory.parse_results(live_shape))


async def test_the_index_names_the_upstream_and_the_caveats():
    out = await d.directory_index()
    assert out["upstream"].startswith("The University of Idaho campus directory at https://directory.uidaho.edu/")
    assert out["caveats"] == d.CAVEATS and any("Employees only" in c for c in d.CAVEATS)
