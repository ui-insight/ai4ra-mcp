# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-05-21

- Initial experimental release.
- Synthesis component: aggregates the upstream single-requirement check findings into one Markdown allowability determination.
- Conservative decision rule — a single `not_allowable` finding forces an overall **Not allowable**.
- Surfaces a compliance-oversight flag whenever the protocol-approval check returned anything other than `not_applicable`.
- Human-readable Markdown output; no JSON schema.
- No eval cases yet — status `experimental` until at least one golden determination is added under `evals/cases/`.
