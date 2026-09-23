# Evals — nsf-budget-spreadsheet-justification-udm

This wrapper does not yet have checked-in golden cases.

Future cases should include:

- `input-source.md` documenting the spreadsheet fixture provenance.
- `input.md` containing a compact workbook evidence package: sheet inventory, relevant visible values, formulas when available, and cell/range references.
- `expected.json` containing the eight-section JSON array validated against `components/nsf-budget-justification-udm/schema.json` at `#/$defs/output`.
- `metadata.yaml` with `validated_against_version`.

Recommended first cases:

- **University budget template full case** — exercises personnel, equipment, travel, subawards, other direct costs, tuition/fees, and F&A rates.
- **Blank-template columns** — verifies that unused Year 4/Year 5 columns do not inflate `project_years`.
- **Missing-detail fallback** — verifies that the prompt acknowledges missing purpose/rationale fields rather than fabricating them.
