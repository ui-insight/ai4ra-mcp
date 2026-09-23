# Evals — nsf-budget-spreadsheet-ingest-udm

Each case lives under `cases/<case-slug>/` with at minimum:

- `metadata.yaml` — case identity plus `validated_against_version`
- `input-source.md` — where to obtain the source workbook (URL, version, date retrieved)
- `expected.json` — the known-good structured budget, validating against `#/$defs/input` of `../../nsf-budget-justification-udm/schema.json`
- `notes.md` — optional; qualitative observations from review

Run artifacts go under `runs/` (gitignored).

Prefer cases that exercise distinct workbook shapes: single-year vs multi-year, with and without subawards, equipment-heavy vs equipment-zero, summary/detail conflicts, and workbooks with non-standard tab names.
