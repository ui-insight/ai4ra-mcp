# Policy Check

Checks a passage of a document against University of Idaho policy, the APM and the FSH, and against the university's F&A and fringe rates, as fetched from the university's policy pages and rate documents, and reports a finding for each sentence that disagrees with it. Report-only and client-neutral: the findings are in the reply. It is the university's sibling of `cfr-check` on the `ecfr` server and reports in the same form, so a client that runs both can put the two on one sentence together.

**Version:** 0.11.0 · **Category:** review · **Status:** experimental · **Output:** findings

## Inputs

A passage of text, however the client supplies it.

The skill needs `uidaho_guidance_index` (a chapter's policies with what each covers; its first call is the listing for APM 45), `uidaho_guidance_get` (one policy for each sentence that asserts something, and of a long policy only the section that speaks to it), and `uidaho_rates` for a sentence that states an F&A or fringe rate.

## Outputs

One finding per sentence that disagrees, in four lines: the word `finding.` with the policy's number and paragraph, the sentence's own words, one clause quoted from the fetched policy with its link and nothing before it, and a `Suggested Fix:` line. There is no verdict: the check surfaces what a person should look at and does not rule. A stated rate is compared with the rate agreement or the fringe-rate page: a figure the document gives for the class, type or location named, in any year shown, draws no finding, and one it gives in none is a finding; a base stated differently from the agreement's own line is one too. Once the rate document is read, a sentence that states a rate or its base is never listed as not checked. Then a closing: the policies and rate documents read with their dates, one line for each sentence not checked, `not checked: "<its words>"`, and that federal regulation and sponsor terms were not read. Two sentences of the passage that disagree with each other are not a finding, here or in the federal check: each is held to the source on its own.

## The form is a contract

The four lines are the findings contract in this repository's README (Skills): a client may read them without a model. A change to the form is a MAJOR version.

## Nothing from memory

No policy is cited and no clause quoted unless it was fetched in the turn. A sentence whose policy could not be fetched is reported as not checked. A policy is the page as it stands today; the university's site keeps no earlier versions, so there is no date to choose.

## Evals

See [`evals/`](evals/). None yet.
