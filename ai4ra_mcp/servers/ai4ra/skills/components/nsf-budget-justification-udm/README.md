# NSF Budget Justification — UDM

Drafts an NSF-format budget justification narrative from a structured budget object. Output is the eight canonical NSF sections (A..H) as an ordered array of section objects — one per section, each with a `key`, a fixed `title`, and `content` in narrative markdown. All eight sections are always emitted; zero-value categories produce a single-sentence content.

**Current version:** 1.0.0
**Category:** drafting
**Domain:** research-administration
**Status:** experimental
**Manifestations:** prompt, skill
**Input and output contracts:** see [`schema.json`](schema.json) (`#/$defs/input` and `#/$defs/output`)

## Inputs

A JSON object with:

- `project_title`, `project_summary` — optional context used for phrasing.
- `project_years` — integer, the number of project years. All year-indexed arrays in the input have this length.
- `personnel` — prime-institution personnel entries. `senior: true` routes to Section A; `senior: false` routes to Section B.
- `budget_summary.categories` — annual totals in USD for NSF categories `A` through `G`.
- `indirect_cost` — negotiated F&A rate, base description, optional off-campus rate, optional rate-agreement citation and notes (including step changes across project years).
- Optional detail: `equipment_items`, `travel_detail`, `participant_support_detail`, `subawards`, `other_direct_costs_detail`.

Subrecipient personnel belong in `subawards`, not `personnel`; they appear in the narrative under Section G's Subawards sub-subheading rather than A or B.

## Outputs

A JSON array of exactly eight objects, in A..H order. Fixed titles (use verbatim — downstream tooling keys on them):

| `key` | `title` | What it covers |
| --- | --- | --- |
| `A` | `Senior Personnel` | Each senior person: role, effort, base salary, escalation, responsibilities |
| `B` | `Other Personnel` | Postdocs, graduate students, undergraduates, hourly staff |
| `C` | `Fringe Benefits` | Rate(s) applied by personnel category, institutional basis |
| `D` | `Equipment` | Items ≥ $5,000 with useful life > 1 year, one per item |
| `E` | `Travel` | Domestic and international purposes, destinations, who travels |
| `F` | `Participant Support Costs` | Stipends, travel, subsistence, fees for non-employee participants |
| `G` | `Other Direct Costs` | Materials, publication, consultant, computer services, subawards, other |
| `H` | `Indirect Costs` | Rate, base, agreement citation, step changes |

Each object carries `key`, `title`, and `content`. `content` is narrative markdown and may include sub-subheadings (especially in Section G). See [`schema.json`](schema.json) for the authoritative definition.

## NSF policy grounding

The prompt encodes these NSF rules so the narrative is policy-consistent:

- **Senior vs. Other Personnel** — Senior = PI, co-PIs, faculty, and others with intellectual direction per PAPPG. Postdocs, graduate students, undergraduates, hourly staff are Other regardless of salary.
- **Equipment threshold** — Acquisition cost ≥ $5,000 AND useful life > 1 year. Below-threshold items are materials and supplies (Section G).
- **Participant support non-substitution** — Indirect costs are not charged on Section F, and rebudgeting out of F requires NSF approval. Narrative states this explicitly.
- **Subawards under G** — Each subrecipient gets a sub-subheading: institution, scope, year-by-year amounts. The justification does not restate MTDC arithmetic.
- **Indirect cost narrative** — State the rate, base description, agreement citation, and step changes. Do not recompute totals.

## First in a family

This is the first component in an anticipated family of sponsor-specific budget-justification drafters. Planned siblings (tracked as separate follow-up issues):

- `nih-budget-justification-udm` — NIH modular vs. detailed budget justifications, NIH-specific category treatment.
- `doe-budget-justification-udm` — DoE Office of Science / ARPA-E budget justification conventions.
- Foundation variants as needed.

The output shape (eight NSF sections) is **NSF-specific**; siblings define their own sponsor-specific section schemes. The input schema pattern (personnel + per-category per-year totals + indirect cost + optional detail) is likely reusable, and may be factored into a shared `$defs` file in a future refactor once two or more sibling components exist.

## Manifestations

- [`prompt.md`](prompt.md) — canonical, LLM-agnostic prompt
- [`skill/SKILL.md`](skill/SKILL.md) — Claude Skill form

## Schema

[`schema.json`](schema.json) is a JSON Schema (draft 2020-12) with two named definitions:

- `#/$defs/input` — validate structured budgets against this before invoking the component
- `#/$defs/output` — validate generated narratives against this

## Relationship to other components

| Component | Role |
| --- | --- |
| `sponsor-doc-defaults-udm` | Upstream (indirect): names the `budget_justification` document as a required NSF deliverable |
| `solicitation-doc-modifications-udm` | Upstream (indirect): may tighten page limits or require specific subheadings in the justification |
| `nsf-budget-justification-udm` (this) | Produces the justification narrative from a structured budget |
| `proposal-completeness-review-udm` | Downstream (future): reviews the produced justification against the merged requirements |

## Evals

See [`evals/`](evals/) for reference inputs and known-good outputs. The initial set covers a realistic multi-year NSF budget that exercises senior personnel, equipment, travel, subawards, and participant support in a single case.

## Provenance

Designed 2026-04-19 in response to issue [#4](https://github.com/AI4RA/prompt-library/issues/4). The eight-section output shape follows NSF's Chapter II budget-justification convention (A Senior Personnel through H Indirect Costs, omitting the informational totals rows J / K / L / M which do not require narrative justification).
