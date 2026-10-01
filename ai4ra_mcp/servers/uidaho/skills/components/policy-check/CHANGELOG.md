# Changelog

Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-10-01

- First version: `cfr-check`'s method against the university's policy pages. The governing policy is chosen from a chapter's index by what each policy covers (#18), read with `uidaho_guidance_get`, and a disagreement is reported in the findings contract's four lines with a `UI:` source line. Disagreement between two sentences of the passage is left to the federal check, so a client that runs both does not get it twice.

## [0.2.0] — 2026-10-01

- Rates. A sentence that states an F&A rate, its base or a fringe rate is checked against the rate agreement or the fringe-rate page with `uidaho_rates`, inside the same check: no second skill and no extra step for a client. The pinpoint for a rate is the document and the place in it, and the clause is the document's own line.
