# Cost Allowability Determination

Synthesizes the findings from the upstream single-requirement checks into one concise, decision-ready Markdown allowability review for a single expense. It is the final step of the federal cost-allowability analysis workflow.

**Current version:** 0.1.0
**Category:** review
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** human-readable Markdown allowability determination
**Contract scope:** repo-local

## Inputs

The structured findings produced by the Stage 2 and Stage 3 check components of the [`cost-allowability-analysis`](https://github.com/AI4RA/prompt-library/tree/main/workflows/cost-allowability-analysis) workflow. Each finding carries an expense reference and the evidence the check relied on, so the determination can restate the expense without a separate context input.

## Outputs

A concise Markdown review for a post-award reviewer: an overall decision (Allowable, Potential issue, Missing info, or Not allowable), a bottom line, the expense reviewed, a per-check results list, what blocks approval, a compliance-oversight flag when applicable, and a confidence level.

The component synthesizes — it does not re-run any check or overturn a finding. It is decision support; it does not replace institutional approval, sponsor prior approval, or final accounting authority.

## Contract scope

Repo-local, human-readable. The determination is a prompt-library review-output contract defined by `prompt.md`; there is no JSON schema. It aligns to sponsored-project cost-allowability semantics but is not a shared AI4RA-UDM contract.

## Triad integration

- **Evaluation datasets:** none yet — repo-local synthetic coverage planned.
- **Harness notes:** canonical manifestation is `prompt.md`. Score the Markdown response against `expected.md` golden cases for the overall decision, the conservative-decision rule (any `not_allowable` finding forces an overall Not allowable), per-check coverage, the compliance-oversight flag, and non-fabrication. Invoked as the Step 3 output task of the `cost-allowability-analysis` workflow.
- **Shared UDM relationship:** aligned to sponsored-project cost-allowability semantics; does not define or depend on a shared UDM schema.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt

## Evals

See [`evals/`](evals/).

## Provenance

Created 2026-05-21 as the synthesis step of the federal cost-allowability analysis component set.
