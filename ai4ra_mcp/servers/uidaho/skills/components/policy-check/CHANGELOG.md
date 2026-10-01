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
