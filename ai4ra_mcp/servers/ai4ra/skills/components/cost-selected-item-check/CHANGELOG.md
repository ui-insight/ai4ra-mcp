# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-05-21

- Initial experimental release.
- Single-requirement check that routes an expense to the governing selected item of cost in 2 CFR 200.421-200.476 and applies that section's rule.
- Emits the shared cost-allowability finding object (`status`, `summary`, `rationale`, `evidence`, `follow_up_actions`, `confidence`) with `check_id` "cost-selected-item"; the rationale names the applied section.
- Section rules are applied from the prompt's enumeration of key sections plus model knowledge; a bundled selected-items reference is a planned enhancement.
- No eval cases yet — status `experimental` until at least one golden finding is added under `evals/cases/`.
