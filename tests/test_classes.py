"""classes, offline from responses captured at banner.uidaho.edu on 2026-10-14: a section slimmed with its meets line and
credits read from the three fields Banner uses; the instructor search's three outcomes (one match, several, none) and a full
name among several; the twelve section panels and the six course panels read down to fields (a restriction's cohort name
passing through unchanged, a fee table, a cross-list table, the one bookstore link); the catalog searched and a course
slimmed; the newest open term as the default and a term by name; a route that answers with a page where JSON was expected
reported with its status and route."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from ai4ra_mcp.servers.classes import banner
from ai4ra_mcp.servers.classes import server as classes

FIX = Path(__file__).parent / "fixtures" / "classes"
TERMS = json.loads((FIX / "getTerms.json").read_text())
INSTRUCTORS = {name: json.loads((FIX / f"get_instructor_{name}.json").read_text()) for name in ("Miura", "Smith", "zzqx")}
SEARCH = json.loads((FIX / "searchResults_instructor.json").read_text())
DETAILS = {"description": (FIX / "getCourseDescription.html").read_text(), "details": (FIX / "getClassDetails.html").read_text(),
           "prerequisites": (FIX / "getSectionPrerequisites.html").read_text(), "enrollment": (FIX / "getEnrollmentInfo.html").read_text(),
           "meetings": json.loads((FIX / "getFacultyMeetingTimes.json").read_text()),
           **{key: (FIX / f"section_{route}.html").read_text() for key, route in banner.SECTION_PANELS if key not in ("description", "details", "prerequisites", "enrollment")}}
COURSE = {key: (FIX / f"course_{route}.html").read_text() for key, route in banner.COURSE_PANELS}
CATALOG = json.loads((FIX / "courseSearchResults.json").read_text())
CATALOG_BY_KEYWORD = json.loads((FIX / "courseSearchResults_keyword.json").read_text())


def _banner(monkeypatch, calls: list | None = None):
    calls = calls if calls is not None else []

    async def get_terms():
        return TERMS

    @asynccontextmanager
    async def session(term, mode="search"):
        calls.append(("session", term) if mode == "search" else ("session", term, mode))
        yield object()
        calls.append(("reset", term))

    async def find_instructors(client, term, fragment, max=20):
        calls.append(("instructors", fragment))
        return [m for name, found in INSTRUCTORS.items() if name.lower() in fragment.lower() for m in found]

    async def search(client, term, subject="", course_number="", instructor_code="", rows=25, start=0):
        calls.append(("search", subject, course_number, instructor_code, rows, start))
        data = [s for s in SEARCH["data"] if (not subject or s["subject"] == subject) and (not course_number or s["courseNumber"] == course_number)]
        return {"totalCount": len(data), "data": data[start:start + rows]}

    async def details(client, term, crn):
        calls.append(("details", term, crn))
        if crn != "48346":
            raise banner.BannerError("searchResults/getClassDetails", 500, "not the 200 the route returns")
        return DETAILS

    async def search_catalog(client, term, subject="", course_number="", keyword="", rows=25, start=0):
        calls.append(("catalog", subject, course_number, keyword, rows, start))
        if keyword:
            return {**CATALOG_BY_KEYWORD, "data": CATALOG_BY_KEYWORD["data"][start:start + rows]}
        data = [c for c in CATALOG["data"] if c["subject"] == subject and (not course_number or c["courseNumber"] == course_number)]
        return {"totalCount": len(data), "data": data}

    async def course_details(client, term, subject, course_number):
        calls.append(("course", term, subject, course_number))
        return COURSE

    for name, fn in (("get_terms", get_terms), ("session", session), ("find_instructors", find_instructors), ("search", search), ("details", details),
                     ("search_catalog", search_catalog), ("course_details", course_details)):
        monkeypatch.setattr(banner, name, fn)
    classes._cache._d.clear()
    return calls


def test_a_section_is_slimmed_with_its_meets_line_and_credits():
    by_crn = {s["courseReferenceNumber"]: s for s in SEARCH["data"]}
    s = banner.slim_section(by_crn["48346"])
    assert s["crn"] == "48346" and s["subject"] == "BIOL" and s["number"] == "1010" and s["section"] == "01" and s["title"] == "Opportunities in Biological Sciences"
    assert s["meets"] == "M 14:30-15:20 LIFE SCIENCES SOUTH 277" and s["campus"] == "Moscow" and s["schedule_type"] == "Lecture" and s["method"] == "Classroom Meeting"
    assert s["instructors"] == [{"name": "Miura, Tanya A.", "email": "tmiura@uidaho.edu", "primary": True}]
    assert (s["enrollment"], s["capacity"], s["seats_available"], s["waitlist"], s["open"], s["part_of_term"]) == (70, 85, 15, 0, True, "1")
    assert s["credits"] == "1"                                         # creditHours null, creditHourLow 1, no high
    assert banner.slim_section(by_crn["52163"])["credits"] == "3"      # creditHours set wins over the 1-16 range
    assert banner.slim_section(by_crn["50810"])["credits"] == "1-4"    # a range
    assert banner.slim_section(by_crn["52163"])["meets"] == "TBA"      # no time, no days


async def test_the_newest_open_term_is_the_default_and_a_term_goes_by_code_or_name(monkeypatch):
    _banner(monkeypatch)
    assert await classes._resolve_term("") == ("202610", "Fall 2026")          # Spring 2027 is view-only, so not it
    assert await classes._resolve_term("fall 2026") == ("202610", "Fall 2026")
    assert await classes._resolve_term("202520") == ("202520", "Spring 2026")
    out = await classes.classes_terms()
    assert out["total"] == len(TERMS) == 10 and out["terms"] == [t for t in map(classes.term_entry, TERMS)]
    assert out["terms"][:2] == [{"code": "202620", "name": "Spring 2027", "view_only": True}, {"code": "202610", "name": "Fall 2026", "view_only": False}]
    assert await classes._resolve_term("Fall 2024") == ("202410", "Fall 2024")   # the oldest listed resolves by name, not only the newest few (#43)


async def test_banner_s_terms_are_paged_until_a_short_page(monkeypatch):
    pages = {1: [{"code": str(202620 - i * 10), "description": f"term {i}"} for i in range(banner.TERMS_PAGE)], 51: [{"code": "199910", "description": "old"}]}
    seen = []

    async def fake_json(client, method, route, params=None, **kw):
        seen.append(params["offset"])
        return pages[params["offset"]]

    @asynccontextmanager
    async def client():
        yield object()

    monkeypatch.setattr(banner, "_json", fake_json)
    monkeypatch.setattr(banner, "_client", client)
    terms = await banner.get_terms()
    assert len(terms) == banner.TERMS_PAGE + 1 and terms[-1]["code"] == "199910" and seen == [1, 51]


async def test_a_search_needs_a_subject_number_or_instructor_and_pages(monkeypatch):
    calls = _banner(monkeypatch)
    assert "at least one" in (await classes.classes_search())["error"]
    out = await classes.classes_search(subject="biol", rows=3)
    assert out["term"] == "202610" and out["term_name"] == "Fall 2026" and out["total"] == 10 and len(out["sections"]) == 3 and out["next_start"] == 3
    assert "instructors_matched" not in out
    assert calls == [("session", "202610"), ("search", "BIOL", "", "", 3, 0), ("reset", "202610")]   # the session is reset after the search
    last = await classes.classes_search(subject="BIOL", rows=3, start=9)
    assert len(last["sections"]) == 1 and "next_start" not in last
    assert "no term named" in (await classes.classes_search(subject="BIOL", term="Autumn 2026"))["error"]


async def test_an_instructor_search_s_three_outcomes(monkeypatch):
    calls = _banner(monkeypatch)
    one = await classes.classes_search(instructor="Miura")
    assert one["total"] == 11 and one["instructors_matched"] == ["Miura, Tanya A."] and calls[1:3] == [("instructors", "Miura"), ("search", "", "", INSTRUCTORS["Miura"][0]["code"], 25, 0)]
    assert all(any(i["name"] == "Miura, Tanya A." for i in s["instructors"]) for s in one["sections"])
    several = await classes.classes_search(instructor="Smith")
    assert several["total"] == 0 and several["sections"] == [] and f"matches {len(INSTRUCTORS['Smith'])} instructors" in several["error"] and "in full" in several["error"]
    assert several["instructors_matched"][:2] == ["Champagne, Dylan S.", "Smith, Alistair"] and not any(c[0] == "search" for c in calls[3:])
    none = await classes.classes_search(instructor="zzqx")
    assert none["total"] == 0 and none["instructors_matched"] == [] and "no instructor matching 'zzqx'" in none["error"]


async def test_a_full_name_is_looked_up_by_its_surname_and_chosen_from_banner_s_list(monkeypatch):
    smiths = INSTRUCTORS["Smith"]
    assert classes.choose_instructor("Smith", smiths)[0] is None
    assert classes.choose_instructor("smith, brian r.", smiths)[0]["description"] == "Smith, Brian R."     # a full name, any case
    assert classes.choose_instructor("Brian R Smith", smiths)[0]["description"] == "Smith, Brian R."       # or first-name first
    assert classes.choose_instructor("Smith, Brian", smiths)[0] is None                                   # two Brians still
    assert classes.choose_instructor("Alistair", smiths)[0]["description"] == "Smith, Alistair"            # only one has the word
    assert classes.choose_instructor("Smith", smiths)[1][0] == "Champagne, Dylan S."                       # Banner's list, as it came
    assert [classes.lookup_word(x) for x in ("Smith, Brian R.", "Brian R. Smith", "Miura", " Miura ")] == ["Smith", "Smith", "Miura", "Miura"]
    calls = _banner(monkeypatch)
    out = await classes.classes_search(instructor="Smith, Alistair")   # Banner's lookup takes one word, so it is asked for the surname
    assert calls[1] == ("instructors", "Smith") and calls[2][3] == next(m["code"] for m in smiths if m["description"] == "Smith, Alistair")
    assert out["instructors_matched"] == [m["description"] for m in smiths] and "error" not in out


async def test_a_section_s_panels_read_down_to_fields(monkeypatch):
    _banner(monkeypatch)
    out = await classes.classes_section("Fall 2026", "48346")
    assert out["title"] == "Opportunities in Biological Sciences" and out["subject"] == "Biology" and out["number"] == "1010"
    assert out["description"].startswith("1 credits. This course will provide a first-year experience") and out["description"].endswith("Typically Offered: Fall.")
    assert out["details"] == {"campus": "Moscow", "schedule_type": "Lecture", "method": "Classroom Meeting", "section": "01", "credits": "1",
                              "grade_mode": "No Section specified grade mode, please see Catalog link below for more information."}
    assert out["meetings"] == [{"days": "M", "start": "14:30", "end": "15:20", "building": "LIFE SCIENCES SOUTH", "room": "277", "from": "08/24/2026", "to": "12/18/2026", "type": "Class",
                                "instructors": [{"name": "Miura, Tanya A.", "email": "tmiura@uidaho.edu", "primary": True}]}]
    assert out["instructors"] == [{"name": "Miura, Tanya A.", "email": "tmiura@uidaho.edu", "primary": True}]
    assert out["prerequisites"] == "No prerequisite information available." and out["corequisites"] is None
    assert out["restrictions"] == ["Cannot be enrolled in one of the following Cohorts: Prison Education Initiative (PEI)",
                                   "Cannot be enrolled in one of the following Majors: WSU (9998)"]   # the cohort's name as published; Banner's 'not all apply' note left out
    assert out["cross_listed"] == [] and out["linked"] == [] and out["fees"] == [] and out["attributes"] == ["Lower-division LWDV"]
    assert out["day_one_access_url"] == "https://vandalsuidaho.sharepoint.com/sites/InsideUI-Student-Accounts/SitePages/Vandal-Day-One-Access.aspx"
    assert out["enrollment"] == {"actual": 70, "maximum": 85, "seats_available": 15, "waitlist_actual": 0, "waitlist_capacity": 999, "waitlist_seats_available": 999}
    assert out["read_from"] == "the schedule"
    assert "digits only" in (await classes.classes_section("Fall 2026", "abc"))["error"]


def test_a_title_s_html_entities_are_unescaped():
    assert banner.slim_course({"courseTitle": "Research &amp; Curriculum Progress"})["title"] == "Research & Curriculum Progress"
    assert banner.slim_section({"courseTitle": "Research &amp; Curriculum Progress"})["title"] == "Research & Curriculum Progress"


def test_a_cross_list_table_and_a_fee_table_are_read_as_rows():
    assert banner.parse_crn_table((FIX / "section_getXlstSections_crosslisted.html").read_text()) == [{"crn": "51860", "subject": "Chemistry", "number": "5750", "title": "Organometallic Chemistry", "section": "01"}]
    assert banner.parse_fees((FIX / "section_getFees_lab.html").read_text()) == [{"description": "CHEM 1111L Lab Fee", "amount": "$120.00", "level": None}]


async def test_the_catalog_is_searched_in_its_own_mode_and_a_course_slimmed(monkeypatch):
    calls = _banner(monkeypatch)
    assert "at least one" in (await classes.classes_catalog())["error"]
    out = await classes.classes_catalog(subject="chem", course_number="1120")
    assert calls[:3] == [("session", "202610", "courseSearch"), ("catalog", "CHEM", "1120", "", 25, 0), ("reset", "202610")]
    assert out["read_from"] == "the catalog" and out["total"] == 1 and "next_start" not in out
    assert out["courses"] == [{"subject": "CHEM", "number": "1120", "title": "General Chemistry II", "credits": "4", "college": "Science", "department": "Chemistry",
                               "levels": None, "schedule_types": None, "grade_modes": None, "attributes": None, "has_sections": None, "effective": {"from": "202500", "to": "999999"}}]
    by_word = await classes.classes_catalog(keyword="Microbiology", rows=3)
    assert calls[-2] == ("catalog", "", "", "Microbiology", 3, 0) and by_word["total"] == 18 and by_word["next_start"] == 3
    assert [(c["subject"], c["number"], c["title"]) for c in by_word["courses"]] == [("BE", "4330", "Bioremediation"), ("BE", "5330", "Bioremediation"), ("BIOL", "2500", "General Microbiology")]   # a keyword matches the description too


async def test_a_course_s_record_is_the_catalog_s_not_a_section_s(monkeypatch):
    calls = _banner(monkeypatch)
    assert "both needed" in (await classes.classes_course("", "CHEM", ""))["error"]
    out = await classes.classes_course("Fall 2026", "chem", "1120")
    assert calls[1:3] == [("catalog", "CHEM", "1120", "", 5, 0), ("course", "202610", "CHEM", "1120")]
    assert out["subject"] == "CHEM" and out["number"] == "1120" and out["title"] == "General Chemistry II" and out["credits"] == "4" and out["read_from"] == "the catalog"
    assert out["description"].startswith("4 credits. Continuation of CHEM 1111.") and out["description"].endswith("or Permission")
    assert out["prerequisites"].startswith("( Chemistry 111 (Undergraduate, grade D) Or") and out["corequisites"] is None
    assert out["restrictions"] == ["Cannot be enrolled in one of the following Majors: WSU (9998)", "Cannot be enrolled in one of the following Cohorts: Prison Education Initiative (PEI)"]
    assert out["attributes"] == ["Natural Science (w/o lab) L", "Lower-division LWDV"] and out["fees"] == [] and out["link"].endswith("/courseSearch/courseSearch")
    missing = await classes.classes_course("Fall 2026", "CHEM", "9999")
    assert missing["error"] == "the catalog has no CHEM 9999 in Fall 2026" and calls[-2][0] != "course"


def test_a_prerequisite_table_is_one_line_with_its_parentheses():
    line = banner.parse_prerequisites((FIX / "getSectionPrerequisites_chem.html").read_text())
    assert line == ("( Chemistry 111 (Undergraduate, grade D) Or Chemistry 1111 (Undergraduate, grade D) ) "
                    "And ( Chemistry 111L (Undergraduate, grade D) Or Chemistry 1111L (Undergraduate, grade D) )")


async def test_a_route_that_stops_answering_is_reported_with_its_status_and_route(monkeypatch):
    _banner(monkeypatch)
    out = await classes.classes_section("202610", "99999")
    assert out["error"] == "Banner answered 500 on searchResults/getClassDetails: not the 200 the route returns"
    assert out["upstream"].endswith("/searchResults/getClassDetails") and "not a published API" in out["note"]
    assert classes._cache.get("section:202610:99999") is None    # an error is not cached


async def test_the_index_names_the_current_term_and_the_caveats(monkeypatch):
    _banner(monkeypatch)
    out = await classes.classes_index()
    assert out["current_term"] == {"code": "202610", "name": "Fall 2026"} and out["caveats"] == classes.CAVEATS and "banner.uidaho.edu" in out["upstream"]
