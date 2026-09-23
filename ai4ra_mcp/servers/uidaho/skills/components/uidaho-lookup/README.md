# UIdaho Lookup

Answers questions about the University of Idaho's sponsored-research facts (F&A and fringe rates, budget rules, policies, contacts) with the uidaho server's tools, quoting each figure or passage with its policy number, revision date or effective period, and page. The rates topic records keyed notes for the budget template inside a workflow.

**Version:** 0.4.0 · **Category:** research · **Status:** experimental · **Output:** Markdown

## Inputs

A question or topic; on- or off-campus.

The skill needs the uidaho server's tools at run time: `uidaho_guidance_index`, `uidaho_guidance_search`, `uidaho_guidance_get` and `uidaho_rates`.

## Outputs

A short answer with figures or policy passages, each with its source, date and page address.

## Evals

See [`evals/`](evals/). None yet.

## Provenance

Written 2026-09-14 for the MindRouter Office add-in, where it carried the page URLs itself and read them with a generic page reader. Rewritten 2026-09-22 for ui-insight/ai4ra-mcp against the uidaho server's tools, which own the URLs and the site's address scheme.
