---
name: sponsor-doc-defaults-udm
version: 1.0.0
description: Emits the default set of documents a named research-funding sponsor requires for a standard full proposal — as a structured JSON list with per-document page limits, format specs, required vs. optional flags, per-person indicators, and conditional triggers. Use when a pre-award team needs to seed a proposal checklist before any solicitation-specific text is analyzed, when an ingest pipeline needs to know what NSF / NIH / DoE expects by default, or when a user asks "what documents do I need to submit for an NSF full proposal?". Input is a short block naming the sponsor (and optionally a division or institute); both natural language and a structured key-value block work. Output is one JSON object containing sponsor_name, sponsor_division, a knowledge_notes caveat string, and a document_requirements array of requirement objects. Uses a controlled 29-code vocabulary shared with sibling prompt-library components so downstream extractors and reviewers can dispatch on the code directly. For solicitation-specific modifications (overrides or net-new documents a specific program introduces), use solicitation-doc-modifications-udm with this component's output as input. When the sponsor is unrecognized, emits an empty requirements array and explains in knowledge_notes — never synthesizes a generic default list.
---

# Sponsor Document Defaults — UDM Skill

Emits the default set of documents a named sponsor requires for a standard full proposal. Output is a small JSON object — the checklist a pre-award team can start from before any solicitation text narrows or expands it.

## When to use

- A pre-award team needs a baseline checklist for an NSF / NIH / DoE / DoD / etc. full proposal
- An ingest pipeline needs to know what documents to expect from a sponsor before a specific solicitation is analyzed
- The user asks "what does sponsor X require?" or "what's the default document list for NIH R01?"
- The output will feed into `solicitation-doc-modifications-udm` to be overridden / extended with solicitation-specific rules

For solicitation-specific requirements (overrides, net-new documents from a specific program), use `solicitation-doc-modifications-udm` with this component's output as its prior.

## Output contract

Emit exactly one JSON object. No preamble, no commentary, no markdown outside the JSON itself.

The object contains:

- `sponsor_name` — sponsor as interpreted (may be a canonical normalization of the input)
- `sponsor_division` — division / institute when the caller provided one, else null
- `knowledge_notes` — policy-version citations, mechanism caveats, or an explanation when the sponsor is unrecognized
- `document_requirements` — array of requirement objects; empty array when the sponsor is unrecognized

See `schema.json` in this component for the authoritative definition.

## Controlled `code` vocabulary

`cover_sheet`, `cover_letter`, `project_summary`, `project_narrative`, `proposal_narrative`, `specific_aims`, `references_cited`, `biosketch`, `current_pending`, `collaborators_and_affiliations`, `facilities`, `equipment`, `budget`, `budget_justification`, `data_mgmt`, `postdoc_mentoring`, `mentoring_plan`, `results_prior_support`, `resource_sharing`, `authentication_key_resources`, `leadership_plan`, `human_subjects`, `vertebrate_animals`, `select_agent`, `inclusion_enrollment_report`, `letter_support`, `letter_collaboration`, `letter_of_intent`, `other`.

These codes are shared with `document-type-classifier-udm`, `solicitation-doc-modifications-udm`, and `proposal-completeness-review-udm`.

## Key rules

- **Normalize sponsor abbreviations.** `NSF` → `National Science Foundation`, `NIH` → `National Institutes of Health`, `DOE` → `U.S. Department of Energy`.
- **Mechanism-aware page limits.** NIH Research Strategy is 12 pages for R01 and 6 pages for R21 — when the mechanism isn't specified, default to R01 and state the mechanism in `knowledge_notes`.
- **Conditional ≠ optional.** A requirement with `is_required: true` and `conditional_on: "<condition>"` becomes mandatory when the condition is met. `is_required: false` is reserved for truly optional documents (e.g., NIH cover letter).
- **Per-person documents.** Biosketch, current_pending, and NSF collaborators_and_affiliations are per-senior-person. Set `is_per_person: true`.
- **Unknown sponsor → empty array.** When you don't have reliable default knowledge for the sponsor, emit `document_requirements: []` and explain in `knowledge_notes`. Do not synthesize a generic "federal default" list.
- **Convention ordering.** Cover / administrative, then proposal body, then per-person, then facilities / budget, then plans, then conditional compliance, then letters.

## NSF defaults (PAPPG)

- Cover Sheet (system-generated)
- Project Summary (1 page; Overview / Intellectual Merit / Broader Impacts subheadings)
- Project Description i.e. `proposal_narrative` (15 pages)
- Results from Prior NSF Support — embedded in the Project Description page limit, conditional on PI/co-PI having received NSF support within the last 5 years
- References Cited (no page limit)
- Biographical Sketch — per person (3 pages, NSF/SciENcv format)
- Current and Pending (Other) Support — per person
- Collaborators and Other Affiliations — per person (NSF COA spreadsheet template)
- Facilities, Equipment, and Other Resources
- Budget (system form)
- Budget Justification (5 pages, plus 5 per subawardee)
- Data Management Plan (2 pages)
- Postdoc Mentoring Plan (1 page; conditional on postdocs in budget)
- Collaboration letters (NSF single-sentence template; when collaborators exist)

## NIH defaults (R01, canonical)

- Cover Letter (optional)
- Project Summary/Abstract (30 lines)
- Project Narrative (public-facing relevance; 2–3 sentences)
- Specific Aims (1 page)
- Research Strategy i.e. `proposal_narrative` (12 pages for R01; 6 for R21 — name the mechanism in `knowledge_notes`)
- Bibliography & References Cited
- Biographical Sketch — per person (NIH format, 5 pages)
- Other Support i.e. `current_pending` — per person
- Facilities and Other Resources
- Equipment (separate section in NIH template)
- Budget (modular or detailed depending on total direct costs)
- Budget Justification
- Data Management and Sharing Plan (2 pages)
- Resource Sharing Plans (model organism, GDS when applicable)
- Authentication of Key Biological and/or Chemical Resources (1 page; when applicable)
- Multiple PD/PI Leadership Plan (conditional)
- Protection of Human Subjects / Vertebrate Animals / Select Agent / Inclusion Enrollment (conditional)

## Other federal sponsors

Emit a conservative default set (cover_sheet, proposal_narrative, biosketch, current_pending, facilities, budget, budget_justification) and note in `knowledge_notes` that solicitation-specific requirements must be resolved by the solicitation modifications component.

## Quality standards

1. Policy-grounded — cite the PAPPG or NIHGPS version in `knowledge_notes` when known.
2. Mechanism-aware — name the mechanism assumed when page limits vary.
3. Conditional requirements use `is_required: true` + `conditional_on: "<condition>"`, not `is_required: false`.
4. Per-person flag set precisely.
5. Empty array on unknown sponsor; never synthesize generic defaults.
6. Schema conformance — output validates against `schema.json`.
