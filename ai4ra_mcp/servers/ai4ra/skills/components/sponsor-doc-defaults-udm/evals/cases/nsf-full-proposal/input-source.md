# Input source

The input in `input.md` is a minimal structured block requesting NSF defaults using the "NSF" abbreviation. The purpose of the minimal input is to exercise the component's normalization rule (abbreviation to canonical sponsor name).

The expected output is grounded in the NSF Proposal & Award Policies & Procedures Guide (PAPPG) in its current form at the time of case creation (2026-04-18). The PAPPG is a public NSF document updated on a roughly annual cadence; when the PAPPG changes in ways that affect baseline defaults (page limits, required subsections, new document types), update `expected.json` and bump `validated_against_version` accordingly.

No sensitive or identifying content is present.
