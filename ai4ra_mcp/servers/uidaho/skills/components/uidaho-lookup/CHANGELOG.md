# Changelog

Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.3.1] — 2026-09-22

- The answer is the reply: write nothing into the document. A workflow run had added a Rates sheet nobody asked for.

## [0.3.0] — 2026-09-22

- Rewritten against the uidaho server's tools (`uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get`, `uidaho_rates`). The prompt no longer carries page URLs; policy answers now cite the policy number and its last-updated date.

## [0.2.1] — 2026-09-14

- Rates for a budget answered in four lines with fractions on request.

## [0.1.0] — 2026-09-14

- First version.

## [0.4.0] — 2026-09-23

- No fallback figures: a page that cannot be read yields no figure, with the tool's reason; every figure carries the address it was read from.
