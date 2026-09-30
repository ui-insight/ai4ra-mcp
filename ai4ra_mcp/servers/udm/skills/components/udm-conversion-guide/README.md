# UDM Conversion Guide

The way records are converted to one table of the AI4RA Unified Data Model, written once as text for a model to follow: look at the data before the schema and say what one row is; fetch the table with `udm_schema`; decide each source column's one operation (rename, split or extract, combine or coalesce, transform, recode or blank, default, derive, resolve, route, generate, drop, or keep flagged) from its name, the synonyms, the description and above all the values; conform dates, booleans, vocabularies, amounts and text; fill provenance; lay the decisions out once with at most three questions; report. And what it never does: the output has exactly one row per source row, in the source's order.

**Version:** 0.2.0 · **Category:** guide · **Status:** experimental · **Output:** the converted records and a report, placed however the caller places output

Served as the `udm_guide` tool and as an MCP prompt. Names no client: a person in a spreadsheet writes a sheet from it, a person with a CSV writes a CSV. The synonyms in the schema are examples of what a column has been called elsewhere, not a closed list; the mapping is the model's judgment over the data it can see.

## Evals

See [`evals/`](evals/). None yet.
