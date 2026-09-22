"""Offline checks: every server mounts, lists the tools it promises, and the
University of Idaho parsers read the page shapes they were written for."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ai4ra_mcp.app import SERVERS, build_app
from ai4ra_mcp.common.skills import load_catalog
from ai4ra_mcp.servers.uidaho import server as uidaho

EXPECTED_TOOLS = {
    "ecfr": {"ecfr_regulatory_index", "ecfr_search", "ecfr_list_titles", "ecfr_list_agencies",
             "ecfr_get_title_versions", "ecfr_get_regulation", "ecfr_get_title_structure", "ecfr_compare_regulations"},
    "grants": {"grants_gov_search", "grants_gov_opportunity"},
    "uidaho": {"uidaho_guidance_index", "uidaho_guidance_search", "uidaho_guidance_get", "uidaho_rates"},
    "ai4ra": {"fetch_document", "web_search"},
    "nih": {"nih_index", "nih_projects_search", "nih_project", "nih_publications"},
    "nsf": {"nsf_index", "nsf_awards_search", "nsf_award", "nsf_award_outcomes"},
    "sam": {"sam_index", "sam_entity", "sam_exclusions_search", "sam_assistance_listing", "sam_assistance_listings_search"},
    "fac": {"fac_index", "fac_audits_search", "fac_findings", "fac_federal_awards"},
}


@pytest.mark.parametrize("name", list(EXPECTED_TOOLS))
async def test_server_lists_its_tools(name):
    tools = {t.name for t in await SERVERS[name].list_tools()}
    assert tools == EXPECTED_TOOLS[name]


@pytest.mark.parametrize("name", list(EXPECTED_TOOLS))
async def test_every_catalogued_skill_is_a_prompt(name):
    skills = Path(uidaho.__file__).parent.parent / name / "skills"
    slugs = {c["slug"] for c in load_catalog(skills).get("components", [])}
    prompts = {p.name for p in await SERVERS[name].list_prompts()}
    assert prompts == slugs


def test_app_mounts_every_server_and_its_skills():
    with TestClient(build_app()) as client:
        index = client.get("/").json()
        assert index["v"] == 1
        assert [s["name"] for s in index["servers"]] == list(SERVERS)
        by = {s["name"]: s for s in index["servers"]}
        assert by["sam"]["key"]["required"] is True and by["sam"]["key"]["hint"]
        assert by["ecfr"]["key"] is None and by["ecfr"]["label"] == "eCFR"
        assert by["nih"]["skills_base"] == "nih/skills/" and by["nih"]["mcp"] == "nih/mcp" and by["nih"]["web"].endswith("/nih/skills/")
        for s in index["servers"]:
            assert client.get("/" + s["skills"]).status_code == 200
        r = client.post("/grants/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                        headers={"Accept": "application/json, text/event-stream"})
        assert r.status_code == 200
        assert {t["name"] for t in r.json()["result"]["tools"]} == EXPECTED_TOOLS["grants"]


def test_app_answers_cors_preflight():
    with TestClient(build_app(["ecfr"])) as client:
        r = client.options("/ecfr/mcp", headers={"Origin": "https://pane.example.edu", "Access-Control-Request-Method": "POST",
                                                  "Access-Control-Request-Headers": "content-type,authorization"})
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == "*"


APM_LANDING = "Policies\n\nAPM\n\n#### APM\n\nChapter 01: Legal Affairs\n\nChapter 45: Research Office\n\nChapter 45: Research Office\n\nDeleted APM Policies\n"
APM_CHAPTER = ("# Chapter 45: Research Office\n\n## Chapter Index\n\n45.01 - Animal Care and Use\n\n45.06 - Allowable and Unallowable Sponsored Project Expenditures\n\n"
               "#### APM\n\nChapter 01: Legal Affairs\n")
FSH_CHAPTER = "Chapter 5: Research Policies\n\n## Chapter Index\n\n5100 - General Research Policy\n\n5600 - Financial Disclosure Policy\n\n## FSH\n\nChapter 1: History\n"
APM_POLICY = ("# 45.06 - Allowable and Unallowable Sponsored Project Expenditures\n\nHome/\n\n## Owner:\n\nPosition: Office of Sponsored Programs Director\n\n"
              "Email: osp@uidaho.edu\n\nLast updated: September 19, 2024\n\nA. Purpose. The purpose of this policy is to ensure...\n\nB. Scope.\n\n#### APM\n\nChapter 01: Legal Affairs\n")


def test_parse_chapters_dedupes_and_builds_urls():
    chapters = uidaho.parse_chapters("APM", APM_LANDING)
    assert [c["chapter"] for c in chapters] == ["01", "45"]
    assert chapters[1]["url"] == "https://www.uidaho.edu/policies/apm/45"


def test_parse_policies_for_both_sources():
    apm = uidaho.parse_policies("APM", "45", APM_CHAPTER)
    assert [p["policy"] for p in apm] == ["APM 45.01", "APM 45.06"]
    assert apm[1]["url"] == "https://www.uidaho.edu/policies/apm/45/06"
    fsh = uidaho.parse_policies("FSH", "5", FSH_CHAPTER)
    assert [p["policy"] for p in fsh] == ["FSH 5100", "FSH 5600"]
    assert fsh[0]["url"] == "https://www.uidaho.edu/policies/fsh/5/5100"


def test_parse_policy_page_reads_header_and_stops_at_nav():
    page = uidaho.parse_policy_page(APM_POLICY)
    assert page["title"].startswith("45.06 - Allowable")
    assert page["owner"] == {"position": "Office of Sponsored Programs Director", "email": "osp@uidaho.edu"}
    assert page["last_updated"] == "September 19, 2024"
    assert page["text"].startswith("A. Purpose.") and page["text"].endswith("B. Scope.")


@pytest.mark.parametrize("ref,expected", [
    ("APM 45.06", ("APM", "45", "06")), ("45.06", ("APM", "45", "06")), ("fsh 5100", ("FSH", "5", "5100")),
    ("5100", ("FSH", "5", "5100")), ("APM 5100", None), ("cost sharing", None),
])
def test_parse_policy_ref(ref, expected):
    assert uidaho.parse_policy_ref(ref) == expected
