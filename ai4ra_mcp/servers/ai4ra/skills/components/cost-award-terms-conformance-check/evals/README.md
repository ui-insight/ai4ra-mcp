# Evals — cost-award-terms-conformance-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Charge within an approved category and no restrictions** — exercises `pass`.
- **Travel exceeding an award per-trip cap** — exercises `not_allowable`.
- **No award caps or exclusions supplied** — exercises `needs_info`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
