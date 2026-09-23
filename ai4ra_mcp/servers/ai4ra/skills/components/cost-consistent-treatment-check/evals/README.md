# Evals — cost-consistent-treatment-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Project-specific scientific supplies** — exercises `not_applicable`.
- **Administrative salary direct-charged without justification** — exercises `issue`.
- **Office supplies also recovered in the indirect pool** — exercises `not_allowable`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
