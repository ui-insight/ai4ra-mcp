# Award Terms Conformance Check

Checks whether a single expense conforms to the limitations and exclusions in the Federal award and the cost principles, under 2 CFR 200.403(b). It is one of the single-requirement checks in the federal cost-allowability analysis workflow and emits a structured finding consumed by the final determination step.

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

Compares the expense against the award's dollar caps, exclusions, prohibited-cost terms, category restrictions, and special conditions, and surfaces conflicts with cost-sharing use (2 CFR 200.403(f)) and applicable credits (2 CFR 200.406). When the award terms needed to run the check are not supplied, it returns `needs_info` rather than assuming conformance.

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

Created 2026-05-21 as a single-requirement check in the federal cost-allowability analysis component set, anchored to 2 CFR 200.403(b).
