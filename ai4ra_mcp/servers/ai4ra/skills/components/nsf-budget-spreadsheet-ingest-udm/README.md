# NSF Budget Spreadsheet Ingest — UDM

Normalizes an NSF-style proposal budget workbook (or workbook-derived evidence) into the structured budget object consumed by `nsf-budget-justification-udm`. This component is the extraction half of a multi-step budget-justification pipeline: it isolates spreadsheet interpretation from narrative drafting so each responsibility can be prompted, versioned, and evaluated independently.

**Current version:** 1.0.0
**Category:** extraction
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** delegates to [`../nsf-budget-justification-udm/schema.json`](../nsf-budget-justification-udm/schema.json) (`#/$defs/input`)
**Contract scope:** delegated wrapper over a repo-local NSF budget-justification input contract

## Inputs

A workbook attachment or extracted spreadsheet evidence package. Typical evidence includes sheet names, used ranges, visible values, formulas when available, and cell-referenced tables from tabs such as:

- `Full Budget`
- `Personnel`
- `Travel`
- `Other Direct Costs`
- `Equipment`
- `Subawards`
- `Participant Support`
- `Tuition, Fees, Insurance`
- `Rates`

Sheet names are hints. The prompt also supports equivalent workbooks where headings, category labels, or extracted CSV snippets carry the same information.

## Outputs

A single JSON object matching `#/$defs/input` of the existing `nsf-budget-justification-udm` schema. Core fields:

- `project_title`, `project_summary`, `project_years`
- `personnel[]` with `senior` flag separating Section A from Section B personnel
- `budget_summary.categories.A..G` year-indexed totals
- `indirect_cost` with `rate_percent`, `base_description`, and optional off-campus / agreement citations
- Optional detail objects: `equipment_items[]`, `travel_detail`, `participant_support_detail`, `subawards[]`, `other_direct_costs_detail`

## Contract Scope

Delegated wrapper. This component does not define its own JSON schema; it emits the input contract owned by `nsf-budget-justification-udm`. The spreadsheet interpretation guidance is sponsor-specific and repo-local, not a shared AI4RA-UDM schema.

## Triad Integration

- **Evaluation datasets:** none yet; initial coverage is repo-local only.
- **Harness notes:** invoke with workbook-derived evidence, then validate the emitted JSON object against `components/nsf-budget-justification-udm/schema.json` at `#/$defs/input`.
- **Shared UDM relationship:** can feed UDM-backed proposal workflows, but the spreadsheet interpretation itself is prompt-library repo-local.

## Manifestations

- [`prompt.md`](prompt.md) — canonical prompt

## Evals

See [`evals/`](evals/). No golden cases are checked in yet; future cases should pair a workbook-derived evidence fixture with an expected structured-budget JSON object.

## Provenance

Extracted 2026-04-24 from the `nsf-budget-spreadsheet-justification-udm` one-shot prompt so that spreadsheet ingestion and narrative drafting could be separately versioned, parameterized, and evaluated in a multi-step budget-justification workflow.
