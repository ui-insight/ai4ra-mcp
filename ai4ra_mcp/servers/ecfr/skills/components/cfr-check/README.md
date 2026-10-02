# CFR Check

Checks a passage of a document against 2 CFR 200, the Uniform Guidance, as fetched from the eCFR, and reports a finding for each sentence that disagrees with it. Report-only and client-neutral: the findings are in the reply, so the same check works in any MCP client; putting a finding on the document (a comment on its sentence, say) is a client's placement skill.

**Version:** 0.12.0 · **Category:** review · **Status:** experimental · **Output:** findings

## Inputs

A passage of text, however the client supplies it. The current rules are used unless the request names a date. As an MCP prompt it takes two optional arguments, `passage` and `date`, appended to the text when given; fetched through `ecfr_guide` or as a file it is the text alone and the client supplies the passage.

The skill needs `ecfr_search` (limited to title 2, part 200) and `ecfr_get_regulation`. It searches once and reads once, each as one round of calls, and reads only what a sentence needs.

## Outputs

One finding per sentence that disagrees with the fetched text, in four lines: the word `finding.` with the pinpoint, the sentence's own words, one clause quoted from the fetched section with its link, and a `Suggested Fix:` line that opens with Add, Change or Remove. There is no verdict: the check surfaces what a person should look at, with the evidence beside it, and does not rule. A sentence draws a finding when it states something the quoted clause forbids, or when the clause conditions or requires something the passage does not show; the Suggested Fix line says which (Change or Remove, or Add). Then a closing: the date the rules were read as of, the sections fetched, one line for each sentence not checked, `not checked: "<its words>"`, and that institution policy and sponsor terms were not read. Two sentences of the passage that disagree with each other are not a finding: each is held to the regulation on its own.

## The form is a contract

The four lines are the findings contract in this repository's README (Skills): a client may read them without a model, and the `Statement:` words are what a finding is placed by. A change to the form is a MAJOR version. The source line is the quotation and its link with nothing before it, the pinpoint above it having named the source; `policy-check` on the `uidaho` server reports in the same form.

## Nothing from memory

No section is cited and no clause quoted unless it was fetched in the turn. A sentence whose rule could not be fetched is reported as not checked.

## Provenance

The pane's `cfr-check` 0.1.1 (mindrouter-365, 2026-09-30) with the document tools taken out and the workarounds removed after the server changes of 2026-10-01: the search is limited to title 2, part 200 (#17) and a call with no date reads the current text, so the version menu, the agency filter and the call-budget rules are gone. The verdict "worth asking" went then, since it spoke of sponsor terms that were never fetched, and the other two went in 0.10.0 (#26).

## Evals

See [`evals/`](evals/). None yet.
