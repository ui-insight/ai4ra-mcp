"""uidaho: a chapter's index, each policy with what it covers in its own opening words; a page that cannot be read
is listed as unread; the opening paragraph passes over a contents list and a bare heading; a long policy as an
outline of its sections, one section read by its offset."""

from ai4ra_mcp.servers.uidaho import server as uidaho

LANDING = "Policies\n\nAPM\n\n#### APM\n\nChapter 01: Legal Affairs\n\nChapter 45: Research Office\n"
CHAPTER = ("# Chapter 45: Research Office\n\n## Chapter Index\n\n45.01 - Animal Care and Use\n\n45.06 - Allowable and Unallowable Sponsored Project Expenditures\n\n"
           "45.09 - Effort Reporting\n\n#### APM\n\nChapter 01: Legal Affairs\n")
HEADER = "\n\nHome/\n\n## Owner:\n\nPosition: Office of Sponsored Programs Director\n\nEmail: osp@uidaho.edu\n\nLast updated: {date}\n\n"
PAGES = {
    "https://www.uidaho.edu/policies/apm": LANDING,
    "https://www.uidaho.edu/policies/apm/45": CHAPTER,
    "https://www.uidaho.edu/policies/fsh": "Policies\n\nFSH\n\nChapter 5: Research Policies\n",
    "https://www.uidaho.edu/policies/apm/45/01": "# 45.01 - Animal Care and Use" + HEADER.format(date="May 3, 2019")
        + "Preamble: This policy sets forth the policy and procedures for the University of Idaho regarding the care and use of animals.\n\nContents:\n\nA. Definitions\n",
    "https://www.uidaho.edu/policies/apm/45/06": "# 45.06 - Allowable and Unallowable Sponsored Project Expenditures" + HEADER.format(date="September 19, 2024")
        + "A. Purpose. The purpose of this policy is to ensure that expenses charged to sponsored projects comply with requirements.\n\nB. Scope. This policy applies widely.\n",
}


def _site(monkeypatch):
    async def fake_whole_text(url):
        if url not in PAGES:
            raise ValueError(f"could not connect ({url})")
        return "", PAGES[url]

    monkeypatch.setattr(uidaho, "_whole_text", fake_whole_text)
    uidaho._cache._d.clear()


def test_opening_paragraph_is_the_first_prose_whatever_the_page_calls_it():
    contents = "CONTENTS:\n\nA. Introduction\n\nF. Provisions Pertaining to Proposals for and the Conduct of Research Supported by Grants and Contracts\n\n"
    assert uidaho.opening_paragraph(contents + "A. INTRODUCTION. The UI encourages the creation of scholarly works as an integral part of its mission.").startswith("A. INTRODUCTION. The UI encourages")
    quoted = "A. Purpose. This policy addresses the classification between “gifts” and “sponsored projects.”\n\nB. Scope. The policy applies to any external funding agreement."
    assert uidaho.opening_paragraph(quoted).startswith("A. Purpose.")   # a closing quotation mark after the full stop still ends a sentence
    long = "A. Purpose. " + "This sentence is fifty characters long, or about. " * 20
    cut = uidaho.opening_paragraph(long)
    assert len(cut) <= uidaho.COVERS_CHARS and cut.endswith("about.")
    assert uidaho.opening_paragraph("CONTENTS:\n\n### A heading\n\nClick here for chart.") == "Click here for chart."   # no prose: the first line that is not a heading
    assert uidaho.opening_paragraph("### Under revision.\n\nCONTENTS:") == ""


def test_a_heading_that_opens_with_the_manual_s_name_is_policy_text_not_the_site_s_navigation():
    page = ("# 70.04 - Travel Entitlements\n\n## Owner:\n\nPosition: Travel Services Manager\n\nEmail: ap-staff@uidaho.edu\n\nLast updated: August 2017\n\n"
            "### APM 70.04 is under revision.\n\nA. General. Subject to limitations stated in this section, UI reimburses employees for the expenses of authorized travel.\n\n"
            "#### APM\n\nChapter 01: Legal Affairs\n")
    parsed = uidaho.parse_policy_page(page)
    assert parsed["text"].startswith("### APM 70.04 is under revision.") and parsed["text"].endswith("authorized travel.")
    assert uidaho.opening_paragraph(parsed["text"]).startswith("A. General. Subject to limitations")


async def test_a_chapter_index_lists_each_policy_with_what_it_covers_and_names_the_unread(monkeypatch):
    _site(monkeypatch)
    out = await uidaho.uidaho_guidance_index("apm 45")
    assert out["chapter"] == "APM 45" and out["title"] == "Research Office" and out["url"].endswith("/apm/45")
    assert [p["policy"] for p in out["policies"]] == ["APM 45.01", "APM 45.06"]
    first, second = out["policies"]
    assert first["covers"].startswith("Preamble: This policy sets forth") and first["last_updated"] == "May 3, 2019"
    assert second["covers"].startswith("A. Purpose. The purpose of this policy") and second["url"].endswith("/apm/45/06") and "text" not in second
    assert [u["policy"] for u in out["unread"]] == ["APM 45.09"] and "could not connect" in out["unread"][0]["unread"]
    assert "starter_citations" not in await uidaho.uidaho_guidance_index() and "APM 45" in " ".join(uidaho.USAGE_NOTES)


async def test_a_chapter_that_is_not_there_is_refused_with_the_chapters_that_are(monkeypatch):
    _site(monkeypatch)
    out = await uidaho.uidaho_guidance_index("APM 99")
    assert "no chapter 99" in out["error"] and out["chapters"] == ["APM 01: Legal Affairs", "APM 45: Research Office"]
    assert "APM 45" in (await uidaho.uidaho_guidance_index("chapter 45"))["error"]


FILL = "The University complies with the terms of each sponsored project and with applicable federal regulation. " * 6   # 636 characters
LONG_POLICY = "\n\n".join(
    ["CONTENTS:", "A. Purpose", "B. Definitions", "C. Procedure"]                       # a contents list names the sections before they begin
    + [f"A. PURPOSE. {FILL}", "B. Definitions", f"B-1. Allowable costs. {FILL}", f"B-2. Institutional Base Salary (IBS): {FILL}"]
    + ["C. Procedure. Expenditures fall into the following categories:", "C-1. Salaries", FILL, f"A. A lettered item inside the section. {FILL}", f"B. Another. {FILL}"]
    + [f"C-2. Fringe benefits. {FILL}"] + [f"C-{n}. Item {n}. {FILL}" for n in range(3, 16)] + [f"D. Contact information. {FILL}"])


def _policy(monkeypatch, body):
    async def fake_whole_text(url):
        return "", "# 45.06 - Allowable Expenditures" + HEADER.format(date="September 19, 2024") + body + "\n\n#### APM\n\nChapter 01: Legal Affairs\n"

    monkeypatch.setattr(uidaho, "_whole_text", fake_whole_text)
    uidaho._cache._d.clear()


async def test_a_long_policy_comes_back_as_an_outline_of_its_sections_and_one_is_read_by_its_offset(monkeypatch):
    _policy(monkeypatch, LONG_POLICY)
    first = await uidaho.uidaho_guidance_get("APM 45.06")
    assert first["truncated"] and first["total_chars"] > 12000 and "next_offset" not in first and first["last_updated"] == "September 19, 2024"
    assert first["text"] == "CONTENTS:\n\nA. Purpose\n\nB. Definitions\n\nC. Procedure"   # the lines before the first section: the policy's own contents
    at = {heading: int(offset) for offset, heading in (entry.split(": ", 1) for entry in first["outline"])}
    assert list(at)[:7] == ["A. PURPOSE", "B. Definitions", "B-1. Allowable costs", "B-2. Institutional Base Salary (IBS)", "C. Procedure", "C-1. Salaries", "C-2. Fringe benefits"]
    assert list(at)[-1] == "D. Contact information" and len(at) == 21   # the lettered items inside C-1 are not sections
    salaries = await uidaho.uidaho_guidance_get("APM 45.06", offset=at["C-1. Salaries"])
    assert salaries["text"].startswith("C-1. Salaries") and "A lettered item inside the section" in salaries["text"] and "C-2. Fringe" not in salaries["text"]
    assert not salaries["truncated"] and "outline" not in salaries and salaries["url"].endswith("/apm/45/06")
    definitions = await uidaho.uidaho_guidance_get("APM 45.06", offset=at["B. Definitions"])
    assert "B-1. Allowable costs" in definitions["text"] and "B-2. Institutional" in definitions["text"] and "C. Procedure" not in definitions["text"]   # a lettered section takes its numbered ones
    whole = await uidaho.uidaho_guidance_get("APM 45.06", max_chars=40000)
    assert not whole["truncated"] and "outline" not in whole and whole["returned_chars"] == whole["total_chars"]


async def test_a_short_policy_comes_whole_and_a_long_one_with_no_sections_is_paged(monkeypatch):
    _policy(monkeypatch, f"A. Purpose. {FILL}\n\nB. Scope. {FILL}")
    short = await uidaho.uidaho_guidance_get("APM 45.06")
    assert not short["truncated"] and "outline" not in short and short["text"].startswith("A. Purpose.")
    _policy(monkeypatch, "\n\n".join([FILL.strip()] * 30))
    pages, offset = [], 0
    while True:
        page = await uidaho.uidaho_guidance_get("APM 45.06", offset=offset)
        assert "outline" not in page
        pages.append(page["text"])
        if not page["truncated"]:
            break
        offset = page["next_offset"]
    assert len(pages) == 2 and "\n\n".join(pages) == "\n\n".join([FILL.strip()] * 30)


def test_the_first_call_is_a_chapter_listing_wherever_the_server_says_what_to_do_first():
    assert "start with uidaho_guidance_index and a chapter" in uidaho.USAGE_NOTES[0] and "No call without a chapter" in uidaho.USAGE_NOTES[0]
    assert not any(note.startswith("Call uidaho_guidance_index first") for note in uidaho.USAGE_NOTES)
    assert "READ THIS FIRST" not in (uidaho.uidaho_guidance_index.__doc__ or "") and "with a chapter" in (uidaho.uidaho_guidance_index.__doc__ or "")
