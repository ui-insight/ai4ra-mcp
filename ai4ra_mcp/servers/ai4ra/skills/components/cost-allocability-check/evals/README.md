# Evals — cost-allocability-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Supply purchased specifically for the funded aim** — exercises `pass`.
- **Shared lab equipment with no allocation basis** — exercises `issue`.
- **Cost shifted from an overspent award** — exercises `not_allowable`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
