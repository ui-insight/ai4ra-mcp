# NSF Budget Spreadsheet to Justification — UDM

Drafts an NSF-format budget justification directly from an NSF-style proposal budget spreadsheet or spreadsheet evidence package. The component interprets workbook tabs for personnel, equipment, travel, participant support, other direct costs, subawards, tuition/fees, and rates, then emits the same eight-section JSON narrative contract used by `nsf-budget-justification-udm`.

**Current version:** 1.0.0
**Category:** drafting
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** delegates to [`../nsf-budget-justification-udm/schema.json`](../nsf-budget-justification-udm/schema.json) (`#/$defs/output`)
**Contract scope:** delegated wrapper over a repo-local NSF budget-justification contract

## Inputs

Input is a workbook attachment or extracted spreadsheet evidence package. Typical evidence includes sheet names, used ranges, visible values, formulas when available, and cell-referenced tables from tabs such as:

- `Full Budget`
- `Personnel`
- `Travel`
- `Other Direct Costs`
- `Equipment`
- `Subawards`
- `Participant Support`
- `Tuition, Fees, Insurance`
- `Rates`

Sheet names are treated as hints. The prompt also supports equivalent budget workbooks where headings, category labels, or extracted CSV snippets carry the same information.

## Outputs

The output is a JSON array of exactly eight section objects, in A..H order, matching `#/$defs/output` in the existing `nsf-budget-justification-udm` schema:

| `key` | `title` |
| --- | --- |
| `A` | `Senior Personnel` |
| `B` | `Other Personnel` |
| `C` | `Fringe Benefits` |
| `D` | `Equipment` |
| `E` | `Travel` |
| `F` | `Participant Support Costs` |
| `G` | `Other Direct Costs` |
| `H` | `Indirect Costs` |

## Contract Scope

This component is a delegated wrapper. It does not define a new JSON output schema; it reuses the repo-local NSF narrative output contract owned by `nsf-budget-justification-udm`. The spreadsheet interpretation guidance is repo-local and sponsor-specific, not a shared AI4RA-UDM schema.

## Triad Integration

- **Evaluation datasets:** none yet; initial coverage is repo-local only.
- **Harness notes:** invoke with workbook-derived evidence, then validate the emitted JSON array against `components/nsf-budget-justification-udm/schema.json` at `#/$defs/output`.
- **Shared UDM relationship:** can feed UDM-backed proposal workflows, but the spreadsheet wrapper and narrative contract remain prompt-library repo-local.

## Manifestations

- [`prompt.md`](prompt.md) — canonical prompt

## Evals

See [`evals/`](evals/) for evaluation notes. No golden cases are checked in yet for this wrapper; a future case should include a workbook-derived evidence fixture and an expected eight-section JSON output.

## Provenance

Designed 2026-04-24 from a University of Idaho-style NSF budget workbook template, with the goal of bridging spreadsheet-first proposal budgets into the existing structured NSF budget-justification component.
