# Evals — cost-allowability-determination

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.md`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

The component emits human-readable Markdown, so golden outputs are `expected.md` rather than `expected.json`.

## Planned cases

- **All checks pass** — exercises an **Allowable** determination.
- **One issue, no violation** — exercises a **Potential issue** determination.
- **One `not_allowable` finding among passes** — exercises the conservative rule forcing **Not allowable**.
- **Flagged protocol-approval `needs_info`** — exercises the compliance-oversight flag and a **Missing info** determination.

## `validated_against_version`

Every case must declare the component version that its `expected.md` was validated against.
