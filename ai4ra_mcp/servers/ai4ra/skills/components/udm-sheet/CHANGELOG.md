# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-09-29

- Initial version: a plan from a matching tool, confirmed once, then the sheet written by formula.

## [0.2.0] — 2026-09-29

- The matching and conversion tools are gone: the model decides the renames, splits, combines and transforms from the data, following the conversion guide the udm server serves (`udm_conversion_guide`) and the schema it serves in portions (`udm_index`, `udm_schema`). The workbook side is unchanged: one question, then every cell a formula on the source.
