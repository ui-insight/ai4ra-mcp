# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-09-22

- Initial version: the Rates sheet with seven fixed-label rows a budget form reads, reference rows for the other rates and the MTDC exclusions, and a Source line for provenance. Replaces the uidaho-lookup step of the proposal workbook, which answered in the reply only.

## [0.2.0] — 2026-09-23

- A Link column: every row carries the address the rate was read from (the PDF and the page that links to it, the fringe page), and the Source row carries both addresses in its text and its Link cell. The fallback figures are gone: a document that cannot be read leaves its rows without values, marked "not fetched" with the tool's reason, and the reply says so; nothing is estimated.
