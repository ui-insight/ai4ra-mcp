# Evals — cost-selected-item-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Alcoholic beverages on a working dinner receipt** — exercises `not_allowable` via 2 CFR 200.423.
- **Conference registration** — exercises `pass` or `issue` via 2 CFR 200.432.
- **Routine project scientific supplies** — exercises `not_applicable` (no selected-item section governs).
- **Equipment purchase near the capitalization threshold** — exercises `issue` via 2 CFR 200.439.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
