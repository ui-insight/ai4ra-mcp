# Changelog — nsf-budget-justification-udm

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks (schema changes that drop or rename sections or required fields), MINOR for backward-compatible additions (new optional input detail fields, new manifestations), PATCH for wording or clarity with no behavior change expected.

The `schema.json` version is kept in lockstep with the component version. The eight-section output shape is NSF-specific; sibling sponsor-specific budget-justification components will ship as separate components with their own schemas.

## [1.0.0] — 2026-04-19

- Initial version.
- JSON Schema (`schema.json`) defining both input and output contracts:
  - `#/$defs/input` — structured NSF budget object with personnel detail, per-category per-year totals, indirect cost, and optional equipment / travel / participant support / subaward / other-direct-costs detail.
  - `#/$defs/output` — fixed-length array of eight section objects (A..H) with enforced `key` and `title` values at each position.
- Canonical prompt (`prompt.md`) encoding NSF policy grounding: senior-vs-other personnel definitions, $5,000 equipment threshold with useful-life > 1 year, participant-support non-substitution rule, subawards-under-Section-G convention, and the indirect-cost narrative scope.
- Claude Skill manifestation (`skill/SKILL.md`).
- One golden eval case (`multi-year-field-science`): a three-year NSF proposal exercising senior personnel, other personnel (postdoc + graduate students + undergraduate), an equipment line in Year 1, domestic travel, a three-year REU-style participant-support program, a subaward, and a step-change indirect-cost note.
