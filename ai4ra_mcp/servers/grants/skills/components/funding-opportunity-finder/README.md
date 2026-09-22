# Funding Opportunity Finder

Turns a project idea, topic, sponsor or opportunity number into a short ranked list of current federal funding opportunities on grants.gov, each as a clickable link, and hands the chosen one on: a summary of the record with its attachment links, the full announcement read in pages, or the budget worksheet skill. It is chat-first but also works as a step for another task, where it returns the best three hits in the shortest form.

**Version:** 0.2.0 · **Category:** research · **Status:** experimental · **Output:** Markdown

## Inputs

A few words to a paragraph describing the research idea, field, target sponsor or program, or an opportunity number or title; optional constraints on sponsor, deadline, award size or eligibility.

The skill needs the grants server's two tools at run time, `grants_gov_search` (keyword, status, agency and category filters, paging) and `grants_gov_opportunity` (one record by id with its attachment links), and `fetch_document` on the ai4ra server to read an attachment.

## Outputs

A numbered list of at most ten opportunities ordered by fit, each with the title as a link to its grants.gov page, the number, agency, status, close date and one line on fit; the searches run with their hit counts; and a one-line offer of next steps. When the user picks one: a summary block of purpose, ceiling, floor, expected awards, close date, cost sharing, eligibility and attachment links, keeping the page link. When called by another task: the best three hits with links and the searches used.

## Evals

See [`evals/`](evals/). None yet. Live grants.gov results change daily, so cases would pin recorded tool responses and score presentation: every entry linked, no invented fields, forecasts labelled, at most ten.

## Provenance

Authored 2026-09-14 for the MindRouter Office add-in as the front end of the pre-award chain: find the announcement, read it, then build the budget with `narrative-to-budget-worksheet`. Moved to ui-insight/ai4ra-mcp 2026-09-22 as a skill of the grants server.
