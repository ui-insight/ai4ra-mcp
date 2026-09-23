# Consistent Cost Treatment Check

Checks whether a single expense is accorded consistent treatment under 2 CFR 200.403(d) and 200.405(c) — that it is not direct-charged to the award when costs incurred for the same purpose in like circumstances are recovered as indirect (F&A) costs. It is one of the single-requirement checks in the federal cost-allowability analysis workflow and emits a structured finding consumed by the final determination step.

**Current version:** 0.1.0
**Category:** review
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** [`schema.json`](schema.json)
**Contract scope:** repo-local

## Inputs

A normalized expense record, extracted award terms, and a regulated-activity classification from the Stage 1 components of the [`cost-allowability-analysis`](https://github.com/AI4RA/prompt-library/tree/main/workflows/cost-allowability-analysis) workflow. Any may be partial.

## Outputs

A single structured finding — see [`schema.json`](schema.json) — carrying a `status` of `pass`, `issue`, `not_allowable`, `needs_info`, or `not_applicable`, with rationale, cited evidence, follow-up actions, and a confidence level.

## The check

Identifies cost types normally recovered through the indirect rate — administrative and clerical effort, office supplies, postage, local telephone, memberships — and tests whether direct-charging them here is consistent and free of double recovery, applying the 2 CFR 200.413(c) conditions for direct-charged administrative or clerical salaries. Unambiguous direct project costs return `not_applicable`.

## Contract scope

Repo-local. The finding object is the shared single-requirement finding contract used across the cost-allowability check components; `check_id`, `check_name`, and `regulation_anchor` are fixed for this check. It is not a shared AI4RA-UDM schema.

## Triad integration

- **Evaluation datasets:** none yet — repo-local synthetic coverage planned.
- **Harness notes:** canonical manifestation is `prompt.md`; validation surface is `schema.json`. Invoked as a Step 2 task of the `cost-allowability-analysis` workflow.
- **Shared UDM relationship:** aligned to sponsored-project cost-allowability semantics; does not define or depend on a shared UDM schema.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt

## Evals

See [`evals/`](evals/).

## Provenance

Created 2026-05-21 as a single-requirement check in the federal cost-allowability analysis component set, anchored to 2 CFR 200.403(d) and 200.405(c).
