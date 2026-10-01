# Changelog

Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-10-01

- First version: `cfr-check`'s method against the university's policy pages. The governing policy is chosen from a chapter's index by what each policy covers (#18), read with `uidaho_guidance_get`, and a disagreement is reported in the findings contract's four lines with a `UI:` source line. Disagreement between two sentences of the passage is left to the federal check, so a client that runs both does not get it twice.
