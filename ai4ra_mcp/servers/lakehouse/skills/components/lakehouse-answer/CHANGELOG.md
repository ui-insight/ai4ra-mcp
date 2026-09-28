# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.2.1] — 2026-09-28

- Step 2 says to narrow a large stream's listing by name with the catalog's `like` pattern instead of reading it whole.

## [0.2.0] — 2026-09-28

- The survey goes through `lakehouse_sql_catalog` in its three layers (streams, one stream's tables, one table's columns with statistics) instead of `lakehouse_schema`, which returns a whole stream at once and overran the conversation on a stream of 1,656 tables. Aggregates: the five functions named, COUNT's non-null semantics stated, anything else sent to `lakehouse_sql`.

## [0.1.0] — 2026-09-23

- Initial version: streams, schema, then a filtered or aggregated query; sourced and dated.
