# Input source

The input in `input.md` is a structured block specifying NIH as the sponsor, NIAID as the division, and R01 as the mechanism. The mechanism field is not part of the component's schema input but the prompt is designed to honor it; passing it here exercises the mechanism-aware page-limit rule.

The expected output is grounded in NIH's Application Instructions (G.400 series for Research) and the NIH Grants Policy Statement. Both are public NIH documents; the policy statement is updated roughly annually. When the NIH application instructions change in ways that affect baseline defaults (new required documents, page limit changes, mechanism changes), update `expected.json` and bump `validated_against_version` accordingly.

No sensitive or identifying content is present.
