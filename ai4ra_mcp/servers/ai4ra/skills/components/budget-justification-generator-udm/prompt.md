---
name: budget-justification-generator-udm
version: 0.1.0
category: drafting
domain: research-administration
status: experimental
tags: [budget-justification, drafting, pre-award, nsf, nih, rr-budget, sf-424a, narrative-generation, multi-year, udm, structured-output, json]
audience: [sponsored-programs-staff, pre-award-teams, pis, proposal-developers]
owner: ui-insight
created: 2026-05-20
updated: 2026-05-20
---

# Budget Justification Generator — UDM JSON

> **Purpose:** Generate a complete, professional budget justification narrative from a grant budget form and the project narrative / proposal. Takes a structured budget and a project narrative as input. Produces a formatted justification document that ties every cost to specific project aims and activities, organized in standard R&R Budget / SF-424A category order (A through I). Supports multi-year budgets and agency-specific rules when a NOFO / RFA is provided.
> **Expected input:** Three documents uploaded together: the budget form / spreadsheet (R&R Budget Form, SF-424A, or Excel), the project narrative / research plan, and optionally the funding opportunity announcement (NOFO / RFA) for agency-specific formatting rules and F&A caps.
> **Expected output:** A single JSON object that validates against [`schema.json`](schema.json). The object captures both the structured per-section extracted financial data AND the generated narrative text for each section, plus the final assembled markdown document and cross-validation notes. No prose outside the JSON.

## When to use this contract

This is a **drafting** workflow, not an extraction workflow. It produces a Word-pasteable budget justification narrative organized by R&R Budget / SF-424A category order (A through I) that a PI or pre-award analyst would otherwise spend several hours assembling by hand. The contract captures:

- Per-section **extracted financial data** (line-item totals, FTEs, rates, allocations) from the budget form, so the downstream consumer can re-validate the math.
- Per-section **generated narrative text** that ties costs to specific project aims and activities pulled from the project narrative.
- An **assembled final document** (Markdown) in standard R&R Budget / SF-424A order, suitable for paste into Word.
- **Cross-validation notes** capturing arithmetic checks and items requiring PI clarification, marked clearly as not-for-submission so an RA can delete them.

This component does **not** cover NSF-specific eight-section narrative drafting — that lives in `nsf-budget-justification-udm`. It does not cover ingest of an NSF budget spreadsheet — that lives in `nsf-budget-spreadsheet-ingest-udm`. This component is the **agency-agnostic** drafting workflow that follows the standard R&R Budget / SF-424A category order.

This component is one of the three prompt-library workflows that produces narrative text alongside structured data. Output validates against `schema.json` (draft 2020-12), but the bulk of the value is in the narrative strings.

---

## Prompt

You are generating a complete, professional Budget Justification narrative from three input documents (uploaded together as workflow documents):

1. The **budget form / spreadsheet** (R&R Budget Form, SF-424A, or Excel).
2. The **project narrative / research plan**.
3. Optionally the **funding opportunity announcement (NOFO / RFA)** for agency-specific formatting rules, F&A caps, and cost-share requirements.

**Be 100% accurate on every dollar amount, rate, calculation, and personnel detail.** Reproduce financial figures exactly as they appear in the budget form. Show calculations explicitly (`rate × base = total`). Tie every cost to specific project activities from the narrative. **Never fabricate or estimate values not present in the source documents.** When a value cannot be determined from the documents, use the literal string `"Not specified in the provided documents"` in narrative text, and `null` for missing scalar fields in the structured data.

Return a single JSON object that validates against [`schema.json`](schema.json) with these top-level keys:

- `project_metadata` — object with `project_title`, `pi_name`, `sponsoring_agency`, `budget_period_count`, and `is_multi_year_budget`.
- `personnel_and_fringe` — object with structured data + narrative text for Sections A (Senior/Key Personnel), B (Other Personnel), and C (Fringe Benefits).
- `equipment_and_travel` — object with structured data + narrative text for Sections D (Equipment), E (Travel: Domestic + Foreign).
- `participant_support_and_other_direct_costs` — object with structured data + narrative text for Sections F (Participant Support) and G (Other Direct Costs, subcategories G.1–G.9).
- `indirect_costs_and_summary` — object with structured data + narrative text for Section H (Indirect Costs / F&A), Cost Sharing, and Budget Summary.
- `cross_validation` — object with arithmetic check results, items requiring PI clarification, and missing-justification flags.
- `final_justification_document` — single Markdown string assembling everything above in R&R Budget / SF-424A category order (A through I).

### Critical: monetary fields are JSON numbers, not strings

Apply the boss's PR #33 review feedback consistently to every monetary field in the structured data:

- `personnel_and_fringe.total_senior_personnel_cost`, `total_other_personnel_cost`, `total_fringe_benefits`, `salary_cap_amount`
- `equipment_and_travel.total_equipment_cost`, `total_domestic_travel_cost`, `total_foreign_travel_cost`
- `participant_support_and_other_direct_costs.total_participant_support`, `publication_costs`, `total_subaward_costs`, `tuition_remission`, `total_other_direct_costs`
- `indirect_costs_and_summary.fa_rate_percentage`, `total_direct_costs`, `total_indirect_costs`, `total_project_costs`, `cost_share_amount`

Quoted strings inside the narrative text (`final_justification_document` and the per-section `*_justification_narrative`) preserve the document's $X,XXX.XX format for readability — that is correct. But every structured-data field above is a JSON number.

### Cross-field rules (from source workflow)

1. **Direct + Indirect = Total** (CFR-01): `total_direct_costs + total_indirect_costs == total_project_costs`. Flag deviations in `cross_validation.arithmetic_checks` without altering values.
2. **Line items sum to category totals** (CHK-01): per-category sub-totals computed from line items must match the budget form's category totals. Flag deviations.
3. **Personnel costs match FTE** (CHK-03): personnel cost calculations consistent with FTE / person-months in the budget. Flag inconsistencies as warnings.

### Per-section structure

Each of the four mid-level blocks (`personnel_and_fringe`, `equipment_and_travel`, `participant_support_and_other_direct_costs`, `indirect_costs_and_summary`) has:

- Structured financial data fields (numeric totals, table arrays of `{name, role, person_months, salary}` etc.).
- A `*_justification_narrative` string field containing the generated professional narrative text for that section.

For the **final assembled document** (`final_justification_document`), assemble in R&R Budget / SF-424A order:

```
A. Senior/Key Personnel  ←  personnel_and_fringe.section_a_narrative
B. Other Personnel       ←  personnel_and_fringe.section_b_narrative
C. Fringe Benefits       ←  personnel_and_fringe.section_c_narrative + personnel summary table
D. Equipment             ←  equipment_and_travel.section_d_narrative
E. Travel                ←  equipment_and_travel.section_e_domestic + section_e_foreign + travel summary table
F. Participant Support   ←  participant_support_and_other_direct_costs.section_f_narrative
G. Other Direct Costs    ←  participant_support_and_other_direct_costs.section_g_narrative + ODC summary table
H. Indirect Costs        ←  indirect_costs_and_summary.section_h_narrative
Cost Sharing             ←  indirect_costs_and_summary.cost_share_narrative
Budget Summary           ←  indirect_costs_and_summary.budget_summary_narrative + period table for multi-year
```

Include a `FORMATTING ADVISORY` block at the top only if the NOFO specified formatting requirements (page limit, font, margins, section naming).

### Cross-validation notes — for the RA's internal review only

`cross_validation` is split into:

- `arithmetic_checks` — array of `{check_name, status, expected, actual, discrepancy}` objects. `status` is `"PASS"` or `"FAIL"`.
- `items_requiring_clarification` — array of strings, each describing a placeholder, missing detail, or PI clarification item. Empty array when none.
- `missing_justification_flags` — array of strings, each describing a budget category that shows a dollar amount but lacks narrative justification. Empty array when none.

The `final_justification_document` must place the cross-validation notes BELOW a clear "CROSS-VALIDATION NOTES — For the RA's internal review only" heading so an RA can delete everything from that heading down and have a submission-ready document.

### Encoding rules

1. **Monetary structured-data fields are JSON numbers.** Narrative text preserves the document's `$X,XXX.XX` format.
2. **Dates use the document's stated form** (this workflow is not date-heavy).
3. **Booleans are JSON booleans.**
4. **Empty optional fields use `null`** (scalars) or `[]` (arrays). Do not invent values.
5. **Do NOT modify dollar amounts.** Reproduce every financial figure exactly as it appeared in the budget form. If amounts do not sum correctly, flag the discrepancy in `cross_validation.arithmetic_checks` but DO NOT adjust any values.
6. **Do NOT fabricate information.** Preserve placeholder text (`"clarification needed from PI"`, `"not specified in the provided documents"`) and add the item to `items_requiring_clarification`.
7. **Maintain professional tone.** Third-person throughout. Remove first-person language, casual phrasing, conversational tone.

### Output

A single JSON object. No surrounding markdown outside the JSON. The `final_justification_document` field carries the Markdown-formatted narrative as a string value.
