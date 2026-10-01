# Policy Check

Checks a passage of a document against University of Idaho policy, the APM and the FSH, and against the university's F&A and fringe rates, as fetched from the university's policy pages and rate documents, and reports a finding for each sentence that disagrees with it. Report-only and client-neutral: the findings are in the reply. It is the university's sibling of `cfr-check` on the `ecfr` server and reports in the same form, with a `University of Idaho:` line where that one has `eCFR:`, so a client that runs both can put the two on one sentence together.

**Version:** 0.9.0 · **Category:** review · **Status:** experimental · **Output:** findings

## Inputs

A passage of text, however the client supplies it.

The skill needs `uidaho_guidance_index` (a chapter's policies with what each covers; its first call is the listing for APM 45), `uidaho_guidance_get` (one policy for each sentence that asserts something, and of a long policy only the section that speaks to it), and `uidaho_rates` for a sentence that states an F&A or fringe rate.

## Outputs

One finding per sentence that disagrees, in four lines: the verdict (violates or unclear) with the policy's number and paragraph, the sentence's own words, one clause quoted from the fetched policy with its link, and a fix. A stated rate is compared with the rate agreement or the fringe-rate page: a figure the document gives for a different type, location, class or year than the passage names is a finding, and one it gives nowhere is unclear, since a sponsor's limit or an approved reduction was not read. Then a closing: the policies and rate documents read with their dates, each sentence not checked and why, and that federal regulation and sponsor terms were not read. Sentences of the passage that disagree with each other are left to the federal check.

## The form is a contract

The four lines are the findings contract in this repository's README (Skills): a client may read them without a model. A change to the form is a MAJOR version.

## Nothing from memory

No policy is cited and no clause quoted unless it was fetched in the turn. A sentence whose policy could not be fetched is reported as not checked. A policy is the page as it stands today; the university's site keeps no earlier versions, so there is no date to choose.

## Evals

See [`evals/`](evals/). None yet.
