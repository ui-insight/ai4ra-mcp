# Evals — cost-documentation-check

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Itemized receipt and approval present** — exercises `pass`.
- **Travel charge missing an itinerary** — exercises `issue`.
- **Documentation status not supplied** — exercises `needs_info`.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
