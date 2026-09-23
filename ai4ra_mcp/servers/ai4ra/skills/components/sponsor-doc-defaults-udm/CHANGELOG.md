# Changelog — sponsor-doc-defaults-udm

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks (schema changes that drop or rename fields, or remove / rename vocabulary codes), MINOR for backward-compatible additions (new vocabulary codes, new optional fields, new manifestations, newly supported sponsors), PATCH for wording or clarity with no behavior change expected.

The `schema.json` version is kept in lockstep with the component version.

## [1.0.0] — 2026-04-18

- Initial version.
- JSON Schema (`schema.json`) defining a single output object with `sponsor_name`, `sponsor_division`, `knowledge_notes`, and a `document_requirements` array.
- Controlled 29-code vocabulary shared with sibling prompt-library components so downstream routing can dispatch on `code` directly.
- Canonical prompt (`prompt.md`) covering NSF PAPPG defaults and NIH R-series defaults, with explicit rules for conditional requirements, per-person requirements, and the unknown-sponsor fallback (empty array + explanation in `knowledge_notes`).
- Claude Skill manifestation (`skill/SKILL.md`) tuned for "what does sponsor X require" triggers.
- Three golden eval cases: NSF full proposal, NIH R01, and an unrecognized sponsor (exercises the empty-requirements rule).
