# Budget Justification Generator — UDM JSON

Generates a complete, professional budget-justification narrative from a grant budget form and the project narrative / proposal. Captures both the structured per-section extracted financial data AND the generated narrative text for each section, plus the final assembled Markdown document and cross-validation notes. Organized in standard R&R Budget / SF-424A category order (A through I). Supports multi-year budgets and agency-specific rules when a NOFO / RFA is provided.

**Current version:** 0.1.0
**Category:** drafting
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** [`schema.json`](schema.json)
**Contract scope:** repo-local, UDM-aligned

## Inputs

Three workflow documents uploaded together:

1. **Budget form / spreadsheet** — R&R Budget Form (SF-424R&R), SF-424A Budget Form, Excel, or PDF.
2. **Project narrative / research plan** — typically 5–30 pages.
3. **Optional NOFO / RFA** — for agency-specific formatting rules, F&A caps, and cost-share requirements.

Total input size: 10–80+ pages (budget 2–10, narrative 5–30, optional NOFO 20–150+).

## Outputs

A single JSON object with seven structured blocks:

- **`project_metadata`** — `project_title`, `pi_name`, `sponsoring_agency`, `budget_period_count`, `is_multi_year_budget`
- **`personnel_and_fringe`** — Sections A (Senior/Key Personnel table + total), B (Other Personnel table + total), C (Fringe Benefit Rates table + total) plus the three section narratives
- **`equipment_and_travel`** — Section D (Equipment items table + total) and Section E (Domestic + Foreign Travel tables + totals + restrictions) plus the three section narratives
- **`participant_support_and_other_direct_costs`** — Section F (Participant Support table) and Section G (nine ODC subcategories: materials, publications, consultants, ADP, subawards, equipment rental, alterations, tuition, other) plus the two section narratives
- **`indirect_costs_and_summary`** — Section H (F&A rate as JSON number + base type + MTDC exclusions + cap details), Cost Sharing (amount + type + sources), and Budget Summary (period table + year-over-year variations + NOFO rules) plus the three section narratives
- **`cross_validation`** — `arithmetic_checks[]` with `{check_name, status, expected, actual, discrepancy}` rows, `items_requiring_clarification[]`, `missing_justification_flags[]` — clearly marked as not-for-submission so an RA can delete this section from `final_justification_document`
- **`final_justification_document`** — Markdown string assembling everything above in R&R Budget / SF-424A category order

See [`schema.json`](schema.json) for the authoritative definition and [`prompt.md`](prompt.md) for encoding rules (monetary structured-data fields as JSON numbers, narrative text preserves `$X,XXX.XX` format, no-fabrication rule, cross-validation marking).

## Why this is a drafting workflow

Unlike the extraction-and-classification components (`award-compliance-extraction-udm`, `subaward-extraction-udm`, etc.), this component **produces narrative text** that the PI / pre-award analyst would otherwise spend several hours assembling. The structured data exists to support the narrative — line-item totals enable arithmetic-check generation, equipment-and-travel tables drive section-narrative generation, etc.

The schema captures the structured data so the downstream consumer can re-validate the math, but the highest-value output is the `final_justification_document` Markdown string. That string is Word-pasteable in standard R&R Budget / SF-424A order, including a `FORMATTING ADVISORY` block at the top when the NOFO specifies page limits / fonts / margins.

## Contract scope

Repo-local, UDM-aligned. Personnel and budget-category leaf fields bind to UDM entities: `Personnel`, `Proposal`, `ProposalBudget.Direct_Cost`, `ProposalBudget.Indirect_Cost`, `ProposalBudget.Period_Number`, `IndirectRate.Rate_Percentage`, `IndirectRate.Base_Type`, `IndirectRate.Rate_Type`, `CostShare.Committed_Amount`, `CostShare.Commitment_Type`, `CostShare.Is_Mandatory`, `Organization.Organization_Name`. The seven-block drafting shape itself is repo-local.

## Relationship to other components

| Concern | Source of truth |
|---|---|
| Agency-agnostic R&R Budget / SF-424A budget-justification drafting | `budget-justification-generator-udm` (this component) |
| NSF-specific eight-section budget-justification drafting | [`nsf-budget-justification-udm`](../nsf-budget-justification-udm/) |
| NSF-specific budget-spreadsheet ingest (structured budget object only, no narrative) | [`nsf-budget-spreadsheet-ingest-udm`](../nsf-budget-spreadsheet-ingest-udm/) |
| Pre-award budget personnel and structure extraction (no narrative generation) | [`proposal-budget-personnel-extraction-udm`](../proposal-budget-personnel-extraction-udm/) |

This component is the agency-agnostic counterpart to the NSF-specific eight-section drafting workflow. Use this component when the agency is not NSF or when the budget follows the standard R&R Budget / SF-424A category order rather than NSF's eight-section structure.

## Triad integration

- **Evaluation datasets:** none yet — planned: a synthetic R&R Budget + project narrative exercise (multi-year, with cost-sharing, mixed-PI structure) validated by a Pre-Award Analyst end-to-end against the `final_justification_document` Markdown.
- **Harness notes:** scoring is two-layered. The structured fields (numeric totals, table rows) validate against `schema.json` and against the arithmetic checks in `cross_validation`. The narrative strings (section narratives + `final_justification_document`) require human review against the project narrative and budget form — golden cases should capture validated narrative text for diff-based scoring.
- **Shared UDM relationship:** aligned, not owning. Leaf fields bind to UDM entities, but the seven-block drafting shape is repo-local.

## Runtime topology — the Vandalizer workflow

The canonical runtime for this component is the [`budget-justification-generator` workflow](https://github.com/AI4RA/prompt-library/tree/main/workflows/budget-justification-generator) shipped at the top level of this repo. The single source of truth is [`workflows/budget-justification-generator/manifest.yaml`](https://github.com/AI4RA/prompt-library/blob/main/workflows/budget-justification-generator/manifest.yaml); the companion `.vandalizer.json` envelope is generated by [`scripts/build_vandalizer_workflows.py`](https://github.com/AI4RA/prompt-library/blob/main/scripts/build_vandalizer_workflows.py) and committed alongside. The runtime mirrors the source [`ui-insight/ProcessMapping/workflows/budget-justification-generator/`](https://github.com/ui-insight/ProcessMapping/tree/main/workflows/budget-justification-generator) workflow:

- **Step 1 (parallel Extraction + Generation)** — four Extraction tasks, each extracting structured budget data AND generating the narrative text for specific budget categories: personnel-and-fringe (Sections A+B+C), equipment-and-travel (Sections D+E), participant-support-and-other-direct-costs (Sections F+G), indirect-costs-and-summary (Section H + Cost Sharing + Budget Summary). Each task carries an embedded SearchSet that includes both data fields and a `*_justification_narrative` field for the generated text.
- **Step 2 (Consolidation Prompt)** — assembles the four JSON fragments into the schema-conformant seven-block object, performs the three cross-validation checks (CFR-01 Direct + Indirect = Total; CHK-01 line items sum to category totals; CHK-03 personnel costs match FTE), and renders the `final_justification_document` Markdown string in R&R Budget / SF-424A order with the cross-validation notes section clearly marked as not-for-submission.

Regenerate the workflow JSON whenever this component bumps MINOR or MAJOR (or whenever the workflow manifest changes); CI fails if the committed `.vandalizer.json` drifts from a fresh build.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt

## Evals

See [`evals/`](evals/) for reference inputs and known-good outputs. Initial case pending: a synthetic R&R Budget + project narrative exercise validated by a Pre-Award Analyst end-to-end.

## Provenance

Authored 2026-05-20 against the `budget-justification-generator` (Workflow_ID: `WF-BUDGET-JUSTIFICATION-GENERATOR`) process-mapping workflow in `ui-insight/ProcessMapping` at commit `2c1f47f46474130743af5aee44d074bcd21787e9`. This is a drafting workflow (rather than a single-process extraction); it does not derive from a single `processes/` map and was built to automate the budget-justification drafting step that PIs and pre-award analysts spend hours on per proposal.
