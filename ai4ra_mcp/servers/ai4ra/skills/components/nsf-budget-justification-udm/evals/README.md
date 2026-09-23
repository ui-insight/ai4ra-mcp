# Evals — nsf-budget-justification-udm

## Structure

Each case lives under `cases/<case-slug>/` with:

- `metadata.yaml` — case identity, features exercised, and (required) `validated_against_version`
- `input.md` — the structured budget JSON passed to the component (wrapped in a single ` ```json ... ``` ` block)
- `input-source.md` — provenance of the budget (synthetic, anonymized real proposal, or composite)
- `expected.json` — the known-good output, validated by a human reviewer and conforming to `../schema.json` at `#/$defs/output`
- `notes.md` — optional observations from validation

Run artifacts go under `runs/` (gitignored).

## Input convention

`input.md` contains one fenced ` ```json ... ``` ` block with the structured budget object. The object must validate against `#/$defs/input` in `../schema.json`. Runners pass the block contents through to the model as the sole input.

## Validating input and expected

```
python3 - <<'PY'
import json, jsonschema, re
from pathlib import Path
schema = json.loads(Path('components/nsf-budget-justification-udm/schema.json').read_text())
resolver = jsonschema.validators.Draft202012Validator

for case in Path('components/nsf-budget-justification-udm/evals/cases').iterdir():
    if not case.is_dir(): continue
    # Validate input
    text = (case/'input.md').read_text()
    m = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
    input_data = json.loads(m.group(1))
    jsonschema.validate(input_data, {'$ref': '#/$defs/input', '$defs': schema['$defs']})
    # Validate expected
    expected = json.loads((case/'expected.json').read_text())
    jsonschema.validate(expected, {'$ref': '#/$defs/output', '$defs': schema['$defs']})
    print(f'OK {case.name}')
PY
```

## Case selection

Prefer cases that each exercise distinct behaviors of the component:

- **Full-coverage multi-year case** — non-zero amounts in every NSF category (A..H), with item-level detail provided for equipment, travel, participant support, and subawards. Exercises every section's "happy path" and the ordering constraint.
- **Empty categories** (future) — a bare-bones budget with zero Equipment, zero Participant Support, no subawards. Exercises the single-sentence zero-category content rule.
- **Missing-detail fallback** (future) — a case where `equipment_items` and `travel_detail` are null but the budget_summary is non-zero. Exercises the "defer to the budget form" fallback language.
- **Step-change indirect rate** — a case where `indirect_cost.notes` describes a rate change across project years. Exercises Section H narration of step changes.

## Current cases

- `multi-year-field-science/` — a three-year NSF proposal for a field-science project. Senior personnel (PI + co-PI), other personnel (postdoc + two graduate students + undergraduate), Year-1 equipment (field spectroradiometer), domestic travel (AGU + field-site trips), a two-year REU-style participant support program, a subaward to a collaborating institution, and an indirect-cost note describing a step change. Exercises non-zero content in all eight sections simultaneously.
