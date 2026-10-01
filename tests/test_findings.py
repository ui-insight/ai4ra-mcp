"""The findings contract: every skill whose catalog entry says its output is findings writes the form the README
gives, in its prompt, in the same order, so a client can read a check's reply without a model."""

import re
from pathlib import Path

from ai4ra_mcp.app import META, SERVERS
from ai4ra_mcp.common.skills import load_catalog, prompt_text

SERVERS_DIR = Path(__file__).parent.parent / "ai4ra_mcp" / "servers"
FORM = re.compile(r'''^\s*(violates|unclear)\. \S.*\n\s*Statement: "<[^"\n]+>"\n\s*([A-Za-z][\w ]*): "<[^"\n]+>" <[^>\n]+>\n\s*Fix: <[^>\n]+>$''', re.M)


def checks():
    out = []
    for name in SERVERS:
        skills = SERVERS_DIR / name / "skills"
        for c in load_catalog(skills).get("components", []):
            if c.get("contracts", {}).get("output", {}).get("format") == "findings":
                out.append((name, c, prompt_text(skills, c)))
    return out


def test_the_two_checks_report_findings():
    assert {(server, c["slug"]) for server, c, _ in checks()} == {("ecfr", "cfr-check"), ("uidaho", "policy-check")}


def test_every_check_writes_the_form_with_its_own_source_label():
    labels = {}
    for server, c, text in checks():
        m = FORM.search(text)
        assert m, f"{server}/{c['slug']} does not show the four lines of a finding in order"
        labels[c["slug"]] = m.group(2)
        assert m.group(2) == META[server]["label"]   # the source line carries the name a client shows for the server it was fetched from
        assert "by its own words" in text and "forbids" in text and "does not show" in text
        assert "Before you report" in text and "is left not checked" in text   # a sentence one fetch away is fetched, not listed
        assert "speaks most directly" in text and "not by itself grounds for a finding" in text and "never a sentence that has a finding" in text
        assert "violates" in text and "unclear" in text and "copied exactly" in text and "not checked" in text
        # the sample finding names no real section or policy, since a model took one for a lead and fetched it (#19)
        assert re.search(r"^\s*(violates|unclear)\. [^\n]*<[^\n]+>", text, re.M), f"{c['slug']}: the sample pinpoint should be a form, not a real citation"
        assert "stop reading and report" in text and "in one round of calls" in text and "is not mentioned" in text
        assert not any(r.startswith(("excel:", "word:", "skill_")) for r in c["requires"])   # report-only: no client's tools
    assert labels == {"cfr-check": "eCFR", "policy-check": "University of Idaho"}


def test_only_the_federal_check_reports_two_sentences_that_disagree():
    by = {c["slug"]: text for _, c, text in checks()}
    assert "Conflicts with:" in by["cfr-check"] and "Conflicts with:" not in by["policy-check"]
