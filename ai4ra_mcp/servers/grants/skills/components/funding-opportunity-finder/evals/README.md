# Evals — funding-opportunity-finder

Each case lives under `cases/<case-slug>/` with at minimum:

- `metadata.yaml` — case identity plus **`validated_against_version`** (required)
- `input.md` — the user's request
- `tool-responses.json` — recorded grants.gov search and fetch results the harness replays, since live results change daily
- `expected.md` — the known-good reply: the list, its order, the fit lines, the next-steps line

Run artifacts go under `runs/` (gitignored).

## Case selection

- A topic with many hits: narrowing by agency facet is applied and named.
- A topic with no hits: the fallback search and the "nothing fits" reply.
- An opportunity number: direct fetch and the summary block with attachment links.
- A forecasted-only result: labelled as a forecast, not an open call.
- Called by another task: three hits, links, searches used, nothing else.

No cases yet.
