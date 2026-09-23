---
name: nsf-budget-justification-udm
version: 1.0.0
description: Drafts an NSF-format budget justification from a structured budget object. Input is a JSON budget (personnel detail, per-category per-year totals, indirect rate and base, and optional detail for equipment / travel / participant support / subawards / other direct costs). Output is an ordered JSON array of exactly eight section objects — the canonical NSF sections A through H (Senior Personnel, Other Personnel, Fringe Benefits, Equipment, Travel, Participant Support Costs, Other Direct Costs, Indirect Costs) — each with key, title, and a narrative markdown content field. All eight sections are always emitted; zero-value categories produce a single-sentence content stating no funds are requested. Use when pre-award staff need a first-draft budget justification to edit, when an ingest pipeline turns a structured budget into narrative for insertion into a proposal, or when a user wants to go from a budget spreadsheet to NSF-ready prose. First in an anticipated family — NIH, DoE, and foundation variants will ship as separate components; the output's eight-section shape is NSF-specific.
---

# NSF Budget Justification — UDM Skill

Drafts an NSF-format budget justification from a structured budget object. Emits the eight canonical NSF sections (A..H) as an ordered JSON array of section objects, each carrying narrative markdown that a pre-award team can edit into submission form.

## When to use

- Pre-award staff need a first-draft NSF budget justification from a structured budget
- An ingest pipeline converts a budget spreadsheet or form into narrative for a proposal
- The user wants NSF-ready prose organized into the canonical eight sections

For NIH, DoE, and foundation variants, use the sponsor-specific budget-justification component (separate components, TBD).

## Input

A JSON object matching `#/$defs/input` in `schema.json`:

- `project_title`, `project_summary` — optional context
- `project_years` — integer
- `personnel[]` — entries with `name`, `role`, `senior` flag, `effort` (unit + value), `base_salary`, optional `escalation_percent`
- `budget_summary.categories` — annual totals for NSF categories `A` through `G`
- `indirect_cost` — rate, base description, optional off-campus rate, optional rate-agreement citation and notes
- Optional `equipment_items`, `travel_detail`, `participant_support_detail`, `subawards`, `other_direct_costs_detail`

## Output

A JSON array of exactly eight section objects, in order:

| `key` | `title` |
| --- | --- |
| `A` | `Senior Personnel` |
| `B` | `Other Personnel` |
| `C` | `Fringe Benefits` |
| `D` | `Equipment` |
| `E` | `Travel` |
| `F` | `Participant Support Costs` |
| `G` | `Other Direct Costs` |
| `H` | `Indirect Costs` |

Each object carries `key`, `title`, and `content` (markdown narrative). Titles must match the table above verbatim — downstream tooling keys on them.

See `schema.json` in this component for the authoritative definition (`#/$defs/output`).

## Key rules

- **All eight sections, in order.** Zero-value categories get a single-sentence content.
- **No fabricated numbers.** Every dollar figure and percentage in the narrative traces to the input. When the input omits detail (fringe rates, equipment descriptions), say so and defer to the budget form.
- **NSF equipment threshold.** Items are equipment when cost ≥ $5,000 and useful life > 1 year. Below-threshold items are materials and supplies under Section G.
- **Participant support non-substitution.** Section F narrative must state that indirect costs are not charged on participant support and that rebudgeting requires NSF approval.
- **Subawards under G.** Each subaward is a sub-subheading within Section G: institution, scope, year-by-year amounts.
- **Indirect explains rate, not totals.** Section H states the rate, base description, agreement citation, and any step changes. The budget form carries the computed totals; the justification does not recompute them.

## Personnel sectioning

Personnel entries with `senior: true` go under Section A. Entries with `senior: false` go under Section B. Subrecipient personnel belong in `subawards`, not `personnel`, and surface under Section G's Subawards sub-subheading.

## Section G sub-structure

Use NSF's Other Direct Costs sub-categories as markdown sub-subheadings:

- Materials and Supplies
- Publication Costs
- Consultant Services
- Computer Services
- Subawards (one sub-subheading per subrecipient)
- Other (e.g., Tuition Remission)

Include only the sub-subheadings that have non-zero amounts or input detail.

## Quality standards

1. No fabricated numbers — every figure traces to the input.
2. Always eight sections, in order, with fixed titles.
3. NSF-specific framing (Modified Total Direct Costs, participant support, senior personnel) rather than generic grant language.
4. Output validates against `#/$defs/output` in `schema.json`.
