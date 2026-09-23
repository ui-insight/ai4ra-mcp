# Evals — award-allowability-terms-extraction

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **NIH award with human-subjects terms** — exercises a populated `compliance_approval_requirements` array.
- **NSF award with foreign-travel prior-approval term** — exercises `prior_approval_triggers`.
- **Award with a dollar-capped budget category** — exercises `caps_and_exclusions` and a category `restrictions` value.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
