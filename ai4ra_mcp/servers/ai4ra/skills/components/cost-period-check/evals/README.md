# Evals — cost-period-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Charge dated after the end date** — exercises `not_allowable`.
- **Charge within an authorized pre-award window** — exercises `pass` via `pre_award_cost_window`.
- **Charge with no transaction date supplied** — exercises `needs_info`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
