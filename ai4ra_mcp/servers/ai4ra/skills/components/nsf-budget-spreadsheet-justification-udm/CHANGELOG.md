# Changelog — nsf-budget-spreadsheet-justification-udm

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible capability additions, PATCH for wording or clarity with no behavior change expected.

The output contract delegates to `nsf-budget-justification-udm` at `#/$defs/output`; this wrapper version tracks spreadsheet-ingestion prompt behavior.

## [1.0.0] — 2026-04-24

- Initial version.
- Canonical prompt for interpreting NSF-style proposal budget workbooks and emitting the existing eight-section NSF budget-justification JSON array.
- Guidance for common workbook tabs: `Full Budget`, `Personnel`, `Travel`, `Other Direct Costs`, `Equipment`, `Subawards`, `Participant Support`, `Tuition, Fees, Insurance`, and `Rates`.
- Explicit mapping from spreadsheet rows and tabs to NSF sections A through H, including the warning that some institutional templates label direct-cost totals as `H` while the prompt-library output section `H` is always `Indirect Costs`.
