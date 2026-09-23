# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-05-21

- Initial experimental release.
- Structured single-expense transaction record: identifying fields, accounting codes, documentation inventory, and an advisory category hint.
- `amount` is a JSON number; `documentation_on_hand` is a string array; absent scalars are null.
- No eval cases yet — status `experimental` until at least one golden extraction is added under `evals/cases/`.
