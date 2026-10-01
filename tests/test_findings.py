"""The findings contract: every skill whose catalog entry says its output is findings writes the form the README
gives, in its prompt, in the same order, so a client can read a check's reply without a model."""

import re
from pathlib import Path

from ai4ra_mcp.app import META, SERVERS
from ai4ra_mcp.common.skills import load_catalog, prompt_text

SERVERS_DIR = Path(__file__).parent.parent / "ai4ra_mcp" / "servers"
FORM = re.compile(r'''^\s*(violates|unclear)\. \S.*\n\s*Statement: "<[^"\n]+>"\n\s*([A-Za-z][\w ]*): "<[^"\n]+>" <[^>\n]+>\n\s*Fix: <Add \| Change \| Remove> <[^>\n]+>$''', re.M)
NOT_CHECKED = '`not checked: "<the sentence\'s words, copied exactly>"`'


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
        assert "violates" in text and "unclear" in text and "copied exactly" in text
        # the sample finding names no real section or policy, since a model took one for a lead and fetched it (#19)
        assert re.search(r"^\s*(violates|unclear)\. [^\n]*<[^\n]+>", text, re.M), f"{c['slug']}: the sample pinpoint should be a form, not a real citation"
        # bounded work, by numbered sentences (#19, #23)
        assert "Number the sentences" in text and "in one round of calls" in text and "stop reading and report" in text and "Before you report" in text
        assert "is left not checked" in text and "used only when it does" in text
        # judgment: the clause on the sentence's own subject, no finding on a general principle, verdicts that do not overlap (#20, #21, #22)
        assert "forbids" in text and "does not show" in text and "speaks most directly" in text and "not by itself grounds for a finding" in text
        assert "Test each finding" in text and "there is no finding: drop it" in text and "is not mentioned" in text
        # forms a client can hold a reply to: the quotation, the Fix line, the pinpoint a read returned, the not-checked line (#22, #23)
        assert "exactly as it stands" in text and "opens with Add, Change or Remove" in text and "states no rule" in text and "is or is not allowable" in text
        assert "copy the `pinpoint` that read returned" in text and NOT_CHECKED in text and "never a sentence that has a finding" in text
        assert m.group(2) == META[server]["label"]   # the source line carries the name a client shows for the server it was fetched from
        labels[c["slug"]] = m.group(2)
        assert not any(r.startswith(("excel:", "word:", "skill_")) for r in c["requires"])   # report-only: no client's tools
    assert labels == {"cfr-check": "eCFR", "policy-check": "University of Idaho"}


def test_only_the_federal_check_reports_two_sentences_that_disagree():
    by = {c["slug"]: text for _, c, text in checks()}
    assert "Conflicts with:" in by["cfr-check"] and "Conflicts with:" not in by["policy-check"]
