# eCFR Research Administration

Answers research-administration questions from the Code of Federal Regulations by fetching the regulatory text with the ecfr server's tools: search or cite, validate the date, read, then answer in plain language with the section and its effective date.

**Version:** 1.0.0 · **Category:** research · **Status:** experimental · **Output:** Markdown

## Inputs

A question about federal regulations governing research, a citation to look up, or a change to trace between two dates.

The skill needs the ecfr server's tools at run time: `ecfr_regulatory_index` first, then `ecfr_search`, `ecfr_get_title_versions` and `ecfr_get_regulation`; `ecfr_compare_regulations` and `ecfr_get_title_structure` for history and browsing.

## Outputs

A plain-language answer, then the exact section and its effective date with an excerpt. Interpretive limits are stated, and the reader is pointed to counsel or the compliance office where agency guidance or institutional policy may be stricter than the CFR.

## Evals

See [`evals/`](evals/). None yet.

## Provenance

Written 2026-04-20 as the `SKILL.md` of AI4RA/mcp-ecfr for the Claude connector. Moved here 2026-09-22 as a catalogued component so the same text serves as an MCP prompt and as a library entry for the Office add-in; the tool table gained `ecfr_regulatory_index`, which is now a tool as well as a resource.
