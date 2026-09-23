# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.4.1] — 2026-09-22

- The announcement is read to its last page (offset = next_offset until truncated is false); a run that stopped at the first page recorded the tracks, page limits and title rule as not stated.

## [0.4.0] — 2026-09-22

- A facility, dataset, partner or prior award named without an address is found with `web_search` and read, instead of guessing a path (a run had 404ed on a guessed University of Idaho path and got the facility only by luck from an NSF award title).

## [0.1.0] — 2026-09-14

- Extracted from the proposal-workbook skill's inline stage so it can be run and tested on its own.
