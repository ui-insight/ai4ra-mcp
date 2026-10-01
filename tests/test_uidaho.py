"""uidaho: a chapter's index, each policy with what it covers in its own opening words; a page that cannot be read
is listed as unread; the opening paragraph passes over a contents list and a bare heading."""

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
