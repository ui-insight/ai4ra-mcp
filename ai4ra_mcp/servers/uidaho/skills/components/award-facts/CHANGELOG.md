# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-09-15

- First version: the first step of the award-review workflow, replacing a question to the user.

## [0.1.1] — 2026-09-15

- The tab named in the request comes first; the headers decide only when none is named.

## [0.2.0] — 2026-09-15

- Reads the FRIGITD export's key block (grant, title, agency, PI/Manager, project period) instead of a Grant Maintenance export, which Banner does not export.

## [0.2.1] — 2026-09-15

- Dates are copied as the cell reads, not converted: a run wrote helper formulas into the export to convert them.

## [0.2.2] — 2026-09-15

- Says which cell is the grant code: a run reported the chart-of-accounts letter.

## [0.3.0] — 2026-09-15

- Names the tab it read and why (the request's, the only export, or the one the user was on), since the workflow no longer asks.

## [0.3.1] — 2026-09-15

- The Tab line is the name alone; how it was found is its own line, since the name is written into a cell.
