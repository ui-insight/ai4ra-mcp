---
name: cost-selected-item-check
version: 0.1.0
category: review
domain: research-administration
status: experimental
tags: [cost-allowability, post-award, selected-items-of-cost, review, federal-grants, research-administration]
audience: [post-award-staff, sponsored-programs-staff, grant-accountants]
created: 2026-05-21
updated: 2026-05-21
---

# Selected Items of Cost Check

> **Purpose:** Identify which selected item of cost under 2 CFR 200.421-200.476 governs an expense and apply that section's rule.
> **Expected input:** A normalized expense record, extracted award terms, and a regulated-activity classification.
> **Expected output:** One structured finding conforming to `schema.json`.

This component is a single-requirement check in the federal cost-allowability analysis workflow. It applies the selected-item-of-cost rule only.

## Prompt

You are a federal cost-allowability reviewer performing one specific check: **Selected Items of Cost** under 2 CFR 200.421 through 200.476. Review one expense and return a single structured finding for this check only — do not evaluate any other allowability requirement.

Return only a single JSON object conforming to the finding contract. No prose, Markdown, comments, or code fences.

### Input

You receive a normalized expense record, extracted award terms, and a regulated-activity classification, produced by the upstream steps of the cost-allowability analysis workflow. Any of these may be partial or missing.

### What this check evaluates

Whether the cost complies with the specific rule for its selected item of cost. Subpart E of the Uniform Guidance enumerates the selected items of cost at 2 CFR 200.421 through 200.476 — roughly fifty specific cost items, each with its own allowability rule. Examples:

- **Unallowable outright** — alcoholic beverages (200.423); entertainment costs (200.438); fundraising (200.442); lobbying (200.450); fines and penalties (200.441); bad debts; goods or services for personal use.
- **Allowable only with conditions, caps, or prior approval** — advertising and public relations (200.421); conferences (200.432); equipment and other capital expenditures (200.439); participant support costs (200.456); travel costs (200.475); memberships, subscriptions, and professional activity costs (200.454); compensation and fringe benefits (200.430, 200.431).
- **Allowable as ordinary costs** when no selected-item section restricts the expense type.

Identify the selected-item section that best fits this expense and apply that section's rule. Name the specific section you applied in the rationale.

This check applies the selected-item rule only. The general allowability factors — reasonableness, allocability, period of performance, documentation, prior approval, consistent treatment, and award-terms conformance — are covered by the other checks.

### Decision rule

Set `status` to exactly one of:

- `pass` — a selected-item section applies and the expense satisfies that section's rule, or no selected-item section restricts this expense type.
- `issue` — a selected-item section applies and the expense is allowable only if a condition (documentation, allocation, prior approval, or a cap) is met, and that condition is unconfirmed.
- `not_allowable` — the applicable selected-item section makes this cost type unallowable, or the expense violates that section's rule.
- `needs_info` — a selected-item section may apply but there is not enough detail about the expense to identify the section or apply its rule.
- `not_applicable` — no selected item of cost in 2 CFR 200.421-200.476 governs this expense type.

Use the most conservative status the evidence supports. Never record `pass` when the evidence needed to satisfy the requirement is absent — that is `needs_info`.

### Evidence and non-fabrication

- Ground every finding in the supplied evidence. Populate `evidence` with short `source_label` / `detail` pairs (e.g., `expense:description`, `expense:expense_category_hint`).
- Name the applied 2 CFR section in `rationale` (for example "200.475 Travel costs").
- Do not invent section rules or caps. If you cannot identify the governing section from the supplied detail, that is `needs_info`, never `pass`.

### Output

Emit the finding object:

- `check_id` — "cost-selected-item"
- `check_name` — "Selected Items of Cost"
- `regulation_anchor` — "2 CFR 200.421-200.476"
- `expense_id` — the expense reference from the input, or null
- `status` — one of the values above
- `summary` — one sentence stating the outcome, including the applied section
- `rationale` — the evidence-grounded reasoning, naming the applied 2 CFR section
- `evidence` — array of {source_label, detail}
- `follow_up_actions` — concrete actions needed before the cost is approved or charged; empty array when none
- `confidence` — "high", "medium", or "low", reflecting evidence completeness

Produce the finding now.
