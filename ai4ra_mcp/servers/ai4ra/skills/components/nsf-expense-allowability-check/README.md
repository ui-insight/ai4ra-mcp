# NSF Expense Allowability Check

Reviews a single expense against NSF award terms, supplied budget evidence, and general sponsored-programs allowability criteria. The component turns the original checklist-style "Expense-Allowability Check" prompt into an evidence-grounded chat review with explicit rule checks, budget alignment, citations, follow-up actions, and a conservative final decision.

**Current version:** 1.0.0
**Category:** review
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt
**Output contract:** human-readable Markdown allowability review
**Contract scope:** repo-local post-award expense review guidance aligned to NSF sponsored-project semantics

## Inputs

- Required: one expense snapshot, including at least enough detail to identify the expense. The prompt accepts file ID, date, vendor, amount, GL or cost code, description, invoice/receipt details, and user notes.
- Recommended: award notice, approved budget, budget justification, terms and conditions, participant-support rules, indirect-cost terms, institutional policy notes, or budget-balance evidence.
- Optional: a proposed budget line, known preapproval, documentation status, or a specific reviewer question.

## Outputs

A concise Markdown response for a traditional chat interface:

- decision label: Allowable, Potential issue, Missing info, or Not allowable
- bottom-line explanation
- expense reviewed
- budget alignment
- rule-check bullets
- evidence used
- next steps
- confidence

The component is designed for decision support. It does not replace institutional approval, sponsor prior approval, or final accounting authority.

## Contract Scope

Repo-local, human-readable review guidance. The component uses sponsored-project concepts such as award identifier, sponsor, budget category, participant support, indirect-cost treatment, and evidence-backed policy findings, but it does not define a JSON schema or a shared AI4RA-UDM contract.

## Triad Integration

- **Evaluation datasets:** none yet; current coverage is repo-local synthetic eval data.
- **Harness notes:** invoke with a single expense and supporting evidence. Score the chat response against `expected.md` golden cases for decision label, budget alignment, rule-check coverage, evidence grounding, and non-fabrication. Golden cases should exercise each decision state and verify that unsupported award-specific caps are not fabricated.
- **Shared UDM relationship:** aligns to sponsored-project award and budget semantics but does not define or depend on a shared UDM schema.

## Manifestations

- [`prompt.md`](prompt.md) - canonical prompt
- [`workflows/nsf-expense-allowability-check`](https://github.com/AI4RA/prompt-library/tree/main/workflows/nsf-expense-allowability-check) - one-step Vandalizer workflow manifestation

## Evals

See [`evals/`](evals/). The initial case is a synthetic travel-cap overage for NSF-2427549-style evidence: the expense maps to Travel and is project-related, but exceeds the supplied per-person cap, so the correct decision is `not_allowable` unless revised or separately approved.

## Provenance

Created 2026-04-29 from an operator-authored Vandalizer checklist titled "Expense-Allowability Check." The registered component improves the original template by making the output evidence-cited, conservative about missing policy support, and reusable across NSF awards when award-specific evidence is supplied.
