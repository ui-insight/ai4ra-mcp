# Sponsor Document Defaults — UDM

Given a sponsor organization (and optional division), emit the default set of documents that sponsor typically requires for a standard full proposal — as a structured list with page limits, format specs, required vs. optional flags, per-person indicators, and conditional triggers.

**Current version:** 1.0.0
**Category:** research
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt, skill
**Output contract:** see [`schema.json`](schema.json)

## Inputs

A short block naming the sponsor and (optionally) the division or institute. Either natural language or a `sponsor_name: …` / `sponsor_division: …` key-value block works; the prompt keys on the sponsor identity, not the syntax.

The component answers the **baseline** question: "What does this sponsor require by default for a standard full proposal?" Solicitation-specific modifications (e.g., a program that shortens a page limit or adds a program-specific supplementary document) are the job of the sibling component `solicitation-doc-modifications-udm`.

## Outputs

One JSON object with:

- `sponsor_name` — the sponsor as interpreted (may be a canonical normalization of the input)
- `sponsor_division` — division or institute when the caller provided one, else null
- `knowledge_notes` — caveats, the policy version the defaults are drawn from (e.g., "NSF PAPPG effective May 2024"), or an explanation when the sponsor is not in the model's knowledge base
- `document_requirements` — array of document requirement objects; may be empty when the sponsor is unrecognized

Each requirement object carries `code`, `label`, `description`, `page_limit`, `format_spec`, `is_required`, `is_per_person`, and an optional `conditional_on` string. See [`schema.json`](schema.json) for the authoritative definition.

## Controlled `code` vocabulary

The `code` field uses an enum shared with sibling prompt-library components so downstream extractors and reviewers can dispatch on it. Current codes:

`cover_sheet`, `cover_letter`, `project_summary`, `project_narrative`, `proposal_narrative`, `specific_aims`, `references_cited`, `biosketch`, `current_pending`, `collaborators_and_affiliations`, `facilities`, `equipment`, `budget`, `budget_justification`, `data_mgmt`, `postdoc_mentoring`, `mentoring_plan`, `results_prior_support`, `resource_sharing`, `authentication_key_resources`, `leadership_plan`, `human_subjects`, `vertebrate_animals`, `select_agent`, `inclusion_enrollment_report`, `letter_support`, `letter_collaboration`, `letter_of_intent`, `other`.

Adding a new code is a MINOR change; removing or renaming one is MAJOR.

## Unknown sponsors

When the sponsor is not one the model has defaults for, emit `document_requirements: []` and put the explanation in `knowledge_notes`. Do not synthesize a generic "federal default" list — downstream routing treats an empty defaults set as a signal to fall back to solicitation-only requirements.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt
- [`skill/SKILL.md`](skill/SKILL.md) — Claude Skill form

## Schema

[`schema.json`](schema.json) is a JSON Schema (draft 2020-12) defining the full output contract.

## Relationship to other components

| Component | Role |
| --- | --- |
| `document-type-classifier-udm` | Upstream: classifies an incoming document into the same code vocabulary |
| `sponsor-doc-defaults-udm` (this) | Emits the default set of required documents for a sponsor |
| `solicitation-doc-modifications-udm` | Pairs with this: given a solicitation + these defaults, emits overrides + net-new documents |
| `proposal-completeness-review-udm` | Consumes the merged defaults + modifications to check a draft proposal |

## Evals

See [`evals/`](evals/) for reference inputs and known-good outputs. The initial set covers NSF (PAPPG defaults), NIH (R01 mechanism defaults), and an unknown sponsor to exercise the empty-requirements rule.

## Provenance

Designed 2026-04-18 in response to issue [#2](https://github.com/AI4RA/prompt-library/issues/2). Vocabulary chosen to cover the highest-frequency required documents across NSF, NIH, and DoE, with conditional items (postdoc mentoring, prior-support results, leadership plan, human subjects) expressed via the `conditional_on` field rather than a secondary flag.
