# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-05-21

- Initial experimental release.
- Single-requirement allowability check anchored to 2 CFR 200.403(d) and 200.405(c).
- Emits the shared cost-allowability finding object (`status`, `summary`, `rationale`, `evidence`, `follow_up_actions`, `confidence`) with `check_id` "cost-consistent-treatment".
- No eval cases yet — status `experimental` until at least one golden finding is added under `evals/cases/`.
