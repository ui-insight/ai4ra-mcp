# CFR Check

Checks a passage of a document against 2 CFR 200, the Uniform Guidance, as fetched from the eCFR, and reports a finding for each sentence that disagrees with it. Report-only and client-neutral: the findings are in the reply, so the same check works in any MCP client; putting a finding on the document (a comment on its sentence, say) is a client's placement skill.

**Version:** 0.3.0 · **Category:** review · **Status:** experimental · **Output:** findings

## Inputs

A passage of text, however the client supplies it. The current rules are used unless the request names a date.

The skill needs `ecfr_search` (limited to title 2, part 200) and `ecfr_get_regulation`. It searches once and reads once, each as one round of calls, and reads only what a sentence needs.

## Outputs

One finding per sentence that disagrees, in four lines: the verdict (violates or unclear) with the pinpoint, the sentence's own words, one clause quoted from the fetched section with its link, and a fix. Then a closing: the date the rules were read as of, the sections fetched, each sentence not checked and why, and that institution policy and sponsor terms were not read.

## The form is a contract

The four lines are the findings contract in this repository's README (Skills): a client may read them without a model, and the `Statement:` words are what a finding is placed by. A change to the form is a MAJOR version. The source line opens with the name of the server the clause was fetched from, `eCFR:`; `policy-check` on the `uidaho` server reports in the same form with a `University of Idaho:` line.

## Nothing from memory

No section is cited and no clause quoted unless it was fetched in the turn. A sentence whose rule could not be fetched is reported as not checked.

## Provenance

The pane's `cfr-check` 0.1.1 (mindrouter-365, 2026-09-30) with the document tools taken out and the workarounds removed after the server changes of 2026-10-01: the search is limited to title 2, part 200 (#17) and a call with no date reads the current text, so the version menu, the agency filter and the call-budget rules are gone. The verdict "worth asking" is gone too: it spoke of sponsor terms that were never fetched.

## Evals

See [`evals/`](evals/). None yet.
