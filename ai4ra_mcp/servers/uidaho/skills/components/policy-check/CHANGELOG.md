# Changelog

Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-10-01

- First version: `cfr-check`'s method against the university's policy pages. The governing policy is chosen from a chapter's index by what each policy covers (#18), read with `uidaho_guidance_get`, and a disagreement is reported in the findings contract's four lines with a `UI:` source line. Disagreement between two sentences of the passage is left to the federal check, so a client that runs both does not get it twice.

## [0.2.0] — 2026-10-01

- Rates. A sentence that states an F&A rate, its base or a fringe rate is checked against the rate agreement or the fringe-rate page with `uidaho_rates`, inside the same check: no second skill and no extra step for a client. The pinpoint for a rate is the document and the place in it, and the clause is the document's own line.

## [0.3.0] — 2026-10-01

- The same bounds as `cfr-check` 0.2.0 (#19): the policies are chosen once from the index and read in one round of calls, only what a sentence needs is read, and the check then stops and reports. The sample finding's pinpoint is a form, not a real policy. A sentence with no finding is not mentioned, and "not checked" is only a sentence whose policy could not be fetched.

## [0.4.0] — 2026-10-01

- The same four changes as `cfr-check` 0.3.0 (#20): the source line is labelled `University of Idaho:`, the name of the server the clause was fetched from, in place of `UI:`; a policy is chosen for each sentence that asserts something checkable, and one with none draws no finding and is listed as not checked; the closing names a sentence not checked by its own words only, with no policy number and no word on what governs it; violates and unclear no longer overlap.

## [0.5.0] — 2026-10-01

- Before reporting, a sentence that asserts something and has no fetched policy behind it gets the policy the index offers for it, read then, as `cfr-check` 0.4.0 does with the section its search returned (#20, item 2 as revised). Not checked is only a sentence the index offers nothing for, or that a limit on calls cut off.

## [0.6.0] — 2026-10-01

From the first two-source run, where the check fetched about 77,000 characters for three sentences (#21).

- The first call is the listing for APM 45; the index with no chapter and the title search are not used, and another chapter is listed only for a sentence APM 45 plainly does not cover.
- One policy for each sentence that asserts something, and no more. A long policy now comes back as an outline of its sections, and the check reads the section that speaks to the sentence by its offset, not the whole policy.
- The same judgment lines as `cfr-check` 0.5.0: the clause that speaks most directly to the sentence's subject; a general principle alone is not grounds for a finding; a sentence is checked when any fetched text speaks to it; a sentence with a finding is never listed as not checked.

## [0.7.0] — 2026-10-01

From the run after 0.6.0 (#22), where a finding on an administrative assistant's effort quoted a clause about a rate of pay, called it a violation, and its Fix said the charge "is not allowable", which no fetched policy says.

- `Fix:` says only what to change in the document, in terms of the clause quoted; it states no rule and never says something is or is not allowable.
- A step before the report: name the word or figure in the sentence that the quoted clause speaks to; if the clause's subject is not in the sentence, there is no finding.
- The quotation is one sentence or line exactly as it stands. A rate finding quotes one fiscal year's line, the year the pinpoint names, and a second figure takes a second source line: a finding was withheld for joining two years' lines. Each rate document is read once.
- A not-checked line has nothing after the sentence's words, no reason.

## [0.8.0] — 2026-10-01

From the run after 0.7.0 (#23), where the fringe sentence, whose figures match no rate on the page, was listed as not checked with that as the reason.

- A sentence that states a rate has been checked once the rate document is read and is never listed as not checked: the figure on the page for the class named, in any year shown, is no finding; the figure in none is unclear, quoting the current year's line, a second class on a second line, with a Fix that asks for the rate and its fiscal year.
- The sentences are numbered first and each ends as a finding, nothing, or not checked; one policy a sentence; a clause read for another sentence is used only when it names this one's subject.
- The pinpoint of a section read by its offset is copied from the `pinpoint` the read returns. `Fix:` opens with Add, Change or Remove and ends at the change. A sentence not checked is one line, `not checked: "<the sentence's words, copied exactly>"`.

## [0.9.0] — 2026-10-01

From the first whole-document run (run 0c6f044f), where both passages ran past a client's 60,000-character limit on fetches.

- A lettered section is not read together with the numbered ones under it: the run read APM 45.06 E-2, E-6 and E-8 and then E whole, which holds them. The outline now shows each section's size, and an offset is a number from that policy's own outline.
- A sentence that was not numbered is never mentioned, "not checked" is never a sentence that was checked and drew nothing, and a limit that stopped the reading gets one line of its own in the closing.
- A policy is listed as read only if its text was fetched: the closing had named one that only the index mentioned.

## [0.10.0] — 2026-10-01

From the first whole-document run on passages of 1,500 characters (run b860db9b; #25), and a decision on what the check is (#26): it surfaces candidate findings, with the evidence beside them, for a person to verify. It does not rule.

- The same changes as `cfr-check` 0.10.0: one word, `finding.`, in place of the two verdicts; no label before the quotation (a second class of a rate takes a second quotation line); the quoted clause must itself forbid, require or condition something, where the run had quoted a sentence on what the University "uses ... as a starting point"; no finding on a fact the sentence does not state, where the run had held a sentence that charges at a rate to a clause that sets a ceiling; one further round of reading before the report and no more, where one step had spent its eight rounds a part at a time.
- Rates (#25 item 4). Once the rate document is read, a sentence that states a rate or its base ends as a finding or as nothing, and the closing's rule says so where the list is written: the run had read the agreement and then listed two such sentences as not checked. The step said what to do with a figure and nothing of a base, so a base is now held to the agreement's own line for it. With no such sentence in the passage the rate document is not read.
