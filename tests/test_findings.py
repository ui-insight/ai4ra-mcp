"""The findings contract: every skill whose catalog entry says its output is findings writes the form the README
gives, in its prompt, in the same order, so a client can read a check's reply without a model."""

import re
from pathlib import Path

from ai4ra_mcp.app import META, SERVERS
from ai4ra_mcp.common.skills import load_catalog, prompt_text

SERVERS_DIR = Path(__file__).parent.parent / "ai4ra_mcp" / "servers"
FORM = re.compile(r'''^\s*finding\. \S.*\n\s*Statement: "<[^"\n]+>"\n\s*"<[^"\n]+>" <[^>\n]+>\n\s*Suggested Fix: <Add \| Change \| Remove> <[^>\n]+>$''', re.M)
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


def test_every_check_writes_the_form():
    for server, c, text in checks():
        m = FORM.search(text)
        assert m, f"{server}/{c['slug']} does not show the four lines of a finding in order"
        assert "copied exactly" in text
        # one word for every finding and no verdict: a check surfaces what a person should look at and does not rule (#26)
        assert "violates" not in text and "unclear" not in text and "verdict" not in text and "you do not rule" in text
        # the source line is the quotation and its link alone, the pinpoint above it having named the source (#26)
        assert META[server]["label"] + ":" not in text and "with nothing before it" in text
        # the sample finding names no real section or policy, since a model took one for a lead and fetched it (#19)
        assert re.search(r"^\s*finding\. [^\n]*<[^\n]+>", text, re.M), f"{c['slug']}: the sample pinpoint should be a form, not a real citation"
        # bounded work, by numbered sentences (#19, #23)
        assert "Number the sentences" in text and "in one round of calls" in text and "stop reading and report" in text and "Before you report" in text
        assert "is left not checked" in text and "used only when it does" in text
        # at the scale of a whole page: only a numbered sentence is ever listed, a heading is not read with the one above it
        assert "is never mentioned" in text and "found nothing against" in text and "own outline" in text
        # no client's limits in the text: what a client refuses or cuts off it says itself, at that moment (#28)
        assert "refused because" not in text and "limit on calls" not in text and "a limit stopped" not in text
        assert "or that you could not read for, is left not checked" in text and "if there was something you could not read, one line saying what" in text
        # judgment: the clause on the sentence's own subject, which itself forbids, requires or conditions; no finding on
        # a general principle, or on a fact the sentence does not state (#20, #21, #22, #25)
        assert "forbids" in text and "does not show" in text and "speaks most directly" in text and "not by itself grounds for a finding" in text
        assert "must itself forbid, require or condition something" in text and "a fact the sentence does not state" in text
        assert "Test each finding" in text and "there is no finding: drop it" in text and "is not mentioned" in text
        # the reading a sentence still lacks is one further round, not a round per afterthought (#25)
        assert "one further round of calls" in text and "no round after it" in text
        # forms a client can hold a reply to: the quotation, the Suggested Fix line, the pinpoint a read returned, the not-checked line (#22, #23)
        # the last line is a suggestion to the person who verifies the finding, and is labelled as one (#27)
        assert "`Suggested Fix:`" in text and not re.search(r"(?<!Suggested )Fix:", text)
        assert "exactly as it stands" in text and "opens with Add, Change or Remove" in text and "states no rule" in text and "is or is not allowable" in text
        assert "Add when the passage does not show something the clause requires" in text   # what the two verdicts carried (#26)
        assert "copy the `pinpoint` that read returned" in text and NOT_CHECKED in text and "never a sentence that has a finding" in text
        assert not any(r.startswith(("excel:", "word:", "skill_")) for r in c["requires"])   # report-only: no client's tools


def test_no_check_sets_one_sentence_of_the_document_against_another():
    """A finding holds a sentence to the fetched text; a conflict inside the document rests on nothing fetched (#24)."""
    for _, c, text in checks():
        assert "Conflicts with" not in text and "with another sentence" not in text, c["slug"]
        assert "Two sentences of the passage that disagree with each other are not this check's to report." in text, c["slug"]


def test_a_sentence_that_states_a_rate_is_never_listed_as_not_checked():
    """The rate document read, a rate or its base ends as a finding or as nothing, and the close says so where the
    list is written; with no such sentence the rate document is not read (#25)."""
    text = next(t for _, c, t in checks() if c["slug"] == "policy-check")
    assert "it ends as a finding or as nothing" in text and "or one that states a rate or its base when the rate document was read" in text
    assert "A base is held to the agreement's own line" in text and "`uidaho_rates` is not called" in text


async def test_a_check_takes_its_passage_as_a_prompt_argument_and_is_served_unchanged_as_a_guide():
    """A client that shows a prompt as a form asks for the passage; one that reads the skill as a guide or a file
    supplies the passage itself, and gets the text word for word (#28)."""
    from ai4ra_mcp.common.skills import guide_get
    wanted = {"cfr-check": ["passage", "date"], "policy-check": ["passage"]}
    for server, c, text in checks():
        listed = next(p for p in await SERVERS[server].list_prompts() if p.name == c["slug"])
        assert [a.name for a in listed.arguments] == wanted[c["slug"]] and not any(a.required for a in listed.arguments)
        assert all(a.description for a in listed.arguments)
        bare = (await SERVERS[server].get_prompt(c["slug"], None)).messages[0].content.text
        assert bare == text == guide_get(SERVERS_DIR / server / "skills", c["slug"])["guide"]
        filled = (await SERVERS[server].get_prompt(c["slug"], {"passage": "Dr. Vale will charge three months.\n\nNo equipment is requested."})).messages[0].content.text
        assert filled == text + "\n\nThe passage:\nDr. Vale will charge three months.\n\nNo equipment is requested."
    dated = (await SERVERS["ecfr"].get_prompt("cfr-check", {"passage": "P.", "date": "2024-06-01"})).messages[0].content.text
    assert dated.endswith("The passage:\nP.\n\nThe date:\n2024-06-01")

