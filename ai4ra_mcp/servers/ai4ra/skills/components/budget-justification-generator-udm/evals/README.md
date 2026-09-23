# Evals — budget-justification-generator-udm

Each case lives under `cases/<case-slug>/` with at minimum:

- `metadata.yaml` — case identity plus **`validated_against_version`** (required): the component version at which the expected output was last human-validated
- `input-source.md` — where to obtain the three source documents (budget form, project narrative, optional NOFO) plus retrieval date
- `expected.json` — the known-good output, validated against `../../schema.json` and reviewed by a Pre-Award Analyst
- `expected.md` — the expected `final_justification_document` Markdown string extracted for diff-based scoring (mirrors the JSON's `final_justification_document` field)
- `notes.md` — optional; qualitative observations from review

Run artifacts go under `runs/` (gitignored).

## Planned cases

The first cases should exercise distinct structural features of the contract, not simply add volume:

- **Single-PI single-year R&R budget** — baseline. Single year, one senior personnel, no other personnel, no equipment, no foreign travel. Exercises the empty-section narratives (`"No other personnel costs are requested..."`, `"No equipment costs are requested..."`).
- **Multi-PI multi-year budget with cost share** — multi-year, multiple senior personnel, postdocs and grad students in `other_personnel`, populated `budget_period_summary` table, populated `cost_share_*` fields with sources. Exercises the year-over-year personnel and budget summary narratives.
- **Budget with subawards over $25K MTDC threshold** — populated `subaward_details` with multiple institutions, exercises Section G.5 subaward narrative and the MTDC base exclusion handling for indirect cost calculations.
- **Budget with NOFO-imposed F&A cap** — `is_fa_rate_capped: true`, populated `fa_rate_cap_details`, populated `nofo_budget_rules`, populated `nofo_page_limit_for_justification`. Exercises the `FORMATTING ADVISORY` block at the top of `final_justification_document`.
- **Budget with arithmetic discrepancy** — line items do NOT sum to category totals. Exercises CHK-01 / CFR-01 flag generation in `cross_validation.arithmetic_checks` with `status: "FAIL"` and populated discrepancy values, without altering the budget form's numbers.
- **Budget with placeholder PI-clarification items** — narrative contains `"clarification needed from PI"` strings. Exercises the `items_requiring_clarification` aggregation in `cross_validation` and preservation of the placeholders in the final document.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against. Re-running evals at a new component version: if the expected output did not change, bump only `validated_against_version`. If it did change, update `expected.json` and `validated_against_version` together.

## Triad alignment reminder

If this component gains a relationship to a dataset in `AI4RA/evaluation-data-sets` (e.g., a new `synthetic.budget_justifications` dataset with paired budget forms and validated narratives), update `component_catalog_overrides.yaml` at the repo root in the same PR.

## Scoring notes

Scoring is two-layered. The structured fields (numeric totals, table rows) validate against `schema.json` and against the arithmetic checks in `cross_validation`. The narrative strings (section narratives + `final_justification_document`) require human review against the project narrative and budget form. Golden cases should capture validated narrative text for diff-based scoring (`expected.md` next to `expected.json`).
