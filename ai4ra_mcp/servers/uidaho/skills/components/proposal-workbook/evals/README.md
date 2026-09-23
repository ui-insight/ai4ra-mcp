# Evals — proposal-workbook

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml` (with `validated_against_version`), `input.md` (the picked opportunity, the four answers, and the answers to the budget skill's questions, one per turn), `tool-responses.json` (recorded grants.gov and announcement fetches), and `expected.md` describing each sheet.

## Case selection

- An NSF opportunity with a PDF announcement: caps and page limits land on the RFA sheet.
- An opportunity with no ceiling stated: the check row reads "not stated", not "OK".
- The user skips every question: assumptions listed and yellow throughout.
- Stage rerun: rerunning Stage 3 replaces Timeline without touching the other sheets.

No cases yet.
