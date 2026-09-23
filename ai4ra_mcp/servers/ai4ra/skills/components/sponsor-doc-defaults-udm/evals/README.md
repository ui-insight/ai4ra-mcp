# Evals — sponsor-doc-defaults-udm

## Structure

Each case lives under `cases/<case-slug>/` with:

- `metadata.yaml` — case identity, features exercised, and (required) `validated_against_version`
- `input.md` — the input sent to the component (short block naming sponsor and optional division)
- `input-source.md` — where the knowledge the expected output is grounded in comes from (sponsor policy document, version, date retrieved)
- `expected.json` — the known-good output, validated by a human reviewer and conforming to `../schema.json`
- `notes.md` — optional observations from validation

Run artifacts go under `runs/` (gitignored).

## Validating `expected.json`

```
check-jsonschema --schemafile components/sponsor-doc-defaults-udm/schema.json \
  components/sponsor-doc-defaults-udm/evals/cases/*/expected.json
```

## Case selection

Prefer cases that each exercise distinct behaviors of the component:

- **Sponsor-specific knowledge recall** — NSF, NIH, DoE, etc. Each case exercises the defaults for one sponsor; combined coverage is the test that the component knows several sponsors.
- **Mechanism-aware page limits** — NIH R01 vs. R21 produce different page limits on the same `code` (`proposal_narrative`). Over time add an R21 case to exercise the difference.
- **Per-person documents** — biosketch, current_pending, and NSF COA must emit `is_per_person: true`.
- **Conditional requirements** — postdoc mentoring, results from prior NSF support, NIH leadership plan, human subjects, vertebrate animals, select agent, inclusion enrollment. Each case should exercise at least some of these.
- **Unknown sponsor fallback** — empty `document_requirements` with an explanatory `knowledge_notes`.
- **Sponsor abbreviation normalization** — input `"NSF"` should normalize to `"National Science Foundation"`.

## Current cases

- `nsf-full-proposal/` — baseline NSF PAPPG defaults. Exercises the canonical NSF document set including conditional postdoc mentoring and the "Results from Prior NSF Support" convention (embedded in Project Description page limit).
- `nih-r01/` — baseline NIH R01 defaults. Exercises the NIH-specific document set (Specific Aims, Research Strategy, DMS, authentication of key resources) and mechanism-aware page limits.
- `unknown-sponsor/` — a fabricated sponsor the model should not attempt to synthesize defaults for. Exercises the empty-array-with-notes rule.
