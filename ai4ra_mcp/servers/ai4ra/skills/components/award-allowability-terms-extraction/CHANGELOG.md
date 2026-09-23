# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-05-21

- Initial experimental release.
- Structured award-terms record covering period of performance, approved budget categories, caps and exclusions, federal prior-approval triggers, indirect-cost treatment, compliance-approval requirements, and special conditions.
- `prior_approval_triggers` (federal sponsor prior approval) and `compliance_approval_requirements` (institutional IRB / IACUC / IBC approvals) are kept as separate fields because they are distinct regulatory regimes.
- No eval cases yet — status `experimental` until at least one golden extraction is added under `evals/cases/`.
