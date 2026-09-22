# Funding History

Assembles a named investigator's federal research support from NIH RePORTER and NSF Award Search, in the shape a current-and-pending support section needs: each award with its number, title, sponsor, dates, total, the person's role and a source link, and a plain statement of what was searched and what was not found.

**Version:** 0.1.0 · **Category:** research · **Status:** experimental · **Output:** Markdown

## Inputs

A person's name; optionally their institution, the years wanted, or one sponsor only.

The skill needs the nih server's tools at run time (`nih_index`, `nih_projects_search`, `nih_project`) and the nsf server's (`nsf_awards_search`, `nsf_award`).

## Outputs

A list of awards, active then completed, each with number, title, sponsor and institute or directorate, project period, total, role and link; then one line naming the searches run and the gaps, including sponsors these databases do not cover.

## Evals

See [`evals/`](evals/). None yet.

## Provenance

Written 2026-09-22 for ui-insight/ai4ra-mcp as the first skill of the nih server, alongside the nsf server it pairs with.
