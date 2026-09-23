# Award Allowability Terms Extraction

Extracts the federal award terms that govern cost allowability — period of performance, approved budget categories, caps and exclusions, sponsor prior-approval triggers, indirect-cost treatment, and institutional compliance-approval requirements — into one structured record. It is an input-normalization step of the federal cost-allowability analysis workflow.

**Current version:** 0.1.0
**Category:** extraction
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** [`schema.json`](schema.json)
**Contract scope:** repo-local

## Inputs

A federal award notice, agreement, or terms-and-conditions document, as pasted text, an attachment, or a URL.

## Outputs

A single JSON object — see [`schema.json`](schema.json) — capturing the award-side constraints on allowability. Missing scalars are `null`; missing lists are empty arrays. The component records terms only; it does not review an expense.

## Contract scope

Repo-local. The record is a prompt-library normalization contract consumed by the downstream cost-allowability check components. It deliberately separates `prior_approval_triggers` (federal sponsor prior approval, 2 CFR 200.407-style) from `compliance_approval_requirements` (institutional IRB / IACUC / IBC approvals), because the two are distinct regulatory regimes. It is not a shared AI4RA-UDM schema.

## Triad integration

- **Evaluation datasets:** none yet — repo-local synthetic coverage planned.
- **Harness notes:** canonical manifestation is `prompt.md`; validation surface is `schema.json`. Invoked as a Step 1 task of the [`cost-allowability-analysis`](https://github.com/AI4RA/prompt-library/tree/main/workflows/cost-allowability-analysis) workflow.
- **Shared UDM relationship:** aligned to sponsored-project award and budget semantics; does not define or depend on a shared UDM schema.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt

## Evals

See [`evals/`](evals/).

## Provenance

Created 2026-05-21 as an input-normalization component of the federal cost-allowability analysis component set.
