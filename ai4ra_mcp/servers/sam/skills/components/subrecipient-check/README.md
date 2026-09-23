# Subrecipient Check

Checks a prospective subrecipient or vendor against SAM.gov (registration, exclusions) and the Federal Audit Clearinghouse (latest single audit and its findings) and reports what the public record shows, fact by fact with source and date, mapped to the items of a 2 CFR 200.332 risk assessment it covers and does not.

**Version:** 0.3.0 · **Category:** review · **Status:** experimental · **Output:** Markdown

## Inputs

An entity's name or UEI; optionally the award or program it would be under.

The skill needs the sam server's tools at run time (`sam_index`, `sam_entity`, `sam_exclusions_search`) and the fac server's (`fac_audits_search`, `fac_findings`). Both servers need keys; a step whose server has none is reported as not checked.

## Outputs

Four blocks: registration, exclusions, single audit with findings, and the 2 CFR 200.332 mapping; then one line with the date of the checks and the record links. No recommendation.

## Evals

See [`evals/`](evals/). None yet.

## Provenance

Written 2026-09-22 for ui-insight/ai4ra-mcp as the first skill of the sam server, pairing it with the fac server.
