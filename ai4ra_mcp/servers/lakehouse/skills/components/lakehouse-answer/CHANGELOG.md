# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.3.0] — 2026-09-28

- Step 3: a plain count is `aggregate` with no `group_by` (the tool now runs it as one SQL statement and returns one row), so the prompt's promise that COUNT on `*` counts every row holds.
- Step 4 (new): row counts across many tables are one statement, never one call per table: first the stream's `_stats` table by `table_name LIKE`, then one `UNION ALL` of `COUNT(*)` branches for the tables Marina has not measured, or the catalog's `counts=true`. A session asked which of 2,467 tables held documents and queued forty single counts, which the client's calls-per-round cap stopped.
- Step 5 (new): a failed call carries Marina's message, which says what to change; the same call is never repeated unchanged, and a timeout is narrowed or split rather than retried.

## [0.2.1] — 2026-09-28

- Step 2 says to narrow a large stream's listing by name with the catalog's `like` pattern instead of reading it whole.

## [0.2.0] — 2026-09-28

- The survey goes through `lakehouse_sql_catalog` in its three layers (streams, one stream's tables, one table's columns with statistics) instead of `lakehouse_schema`, which returns a whole stream at once and overran the conversation on a stream of 1,656 tables. Aggregates: the five functions named, COUNT's non-null semantics stated, anything else sent to `lakehouse_sql`.

## [0.1.0] — 2026-09-23

- Initial version: streams, schema, then a filtered or aggregated query; sourced and dated.

## [0.3.1] — 2026-09-30

- Step 4 addresses the stats table by the stream alone (`lakehouse."<stream>"."_stats"`), the form Marina accepts, and says the stats table takes only SELECT with WHERE, ORDER BY, LIMIT and simple aggregates over itself (#13).

## [0.3.2] — 2026-09-30

- Every table reference is lakehouse."<stream>"."<table>": Marina's schema is the stream's name since its PR #382 (2026-09-29), and the stats table allows GROUP BY and the simple aggregates (#13, settled from Marina's client reference).
