# Expense Transaction Extraction

Normalizes one expense — receipt, invoice, purchase order, p-card line, or general-ledger detail — into a single structured transaction record covering date, vendor, amount, account coding, description, and documentation status. It is the input-normalization step of the federal cost-allowability analysis workflow.

**Current version:** 0.1.0
**Category:** extraction
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** [`schema.json`](schema.json)
**Contract scope:** repo-local

## Inputs

Expense documentation for a single charge — a receipt, vendor invoice, purchase order, procurement-card statement line, or general-ledger detail row — as pasted text, an attachment, or analyst notes. Reviewer questions may be included and are carried into `notes`.

## Outputs

A single JSON object — see [`schema.json`](schema.json) — with the transaction's identifying and accounting fields. Missing scalars are `null`; missing lists are empty arrays. The component does not assess allowability.

## Contract scope

Repo-local. The expense record is a prompt-library normalization contract consumed by the downstream cost-allowability check components. It is not a shared AI4RA-UDM schema, though its fields align to sponsored-project transaction semantics (vendor, amount, account coding, period).

## Triad integration

- **Evaluation datasets:** none yet — repo-local synthetic coverage planned.
- **Harness notes:** canonical manifestation is `prompt.md`; validation surface is `schema.json`. Invoked as a Step 1 task of the [`cost-allowability-analysis`](https://github.com/AI4RA/prompt-library/tree/main/workflows/cost-allowability-analysis) workflow.
- **Shared UDM relationship:** aligned to sponsored-project transaction semantics; does not define or depend on a shared UDM schema.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt

## Evals

See [`evals/`](evals/).

## Provenance

Created 2026-05-21 as the input-normalization component of the federal cost-allowability analysis component set.
