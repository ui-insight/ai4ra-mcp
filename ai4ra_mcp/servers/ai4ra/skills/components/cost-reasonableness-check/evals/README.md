# Evals — cost-reasonableness-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Market-priced routine supply purchase** — exercises `pass`.
- **Conference registration far above the typical rate** — exercises `issue`.
- **Expense with no basis for the amount** — exercises `needs_info`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
