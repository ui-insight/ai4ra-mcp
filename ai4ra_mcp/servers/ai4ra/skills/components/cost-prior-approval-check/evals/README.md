# Evals — cost-prior-approval-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Routine supply purchase with no trigger** — exercises `pass`.
- **Foreign travel with no approval evidence** — exercises `issue`.
- **Equipment outside the approved budget with no approval** — exercises `not_allowable`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
