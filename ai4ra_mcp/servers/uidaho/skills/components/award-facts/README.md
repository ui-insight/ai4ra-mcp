# Award Facts

Reads an award's facts off the key block at the top of a Banner Grant Inception to Date export (FRIGITD): grant code, title, sponsor, PI, project start and end dates. Reading only.

**Version:** 0.3.0 · **Category:** post-award · **Status:** experimental · **Output:** seven lines in the reply

## Inputs

A workbook with the FRIGITD export on any tab. `dev/examples/award-example.xlsx` is one.

## Outputs

Seven "label: value" lines, the tab read first.

## Evals

See [`evals/`](evals/). None yet.
