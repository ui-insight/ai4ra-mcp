# Lakehouse Answer

Answers a question from the University of Idaho data lakehouse: discovers the streams the client may query, reads each candidate stream's schema, then queries the table that holds the answer with the question's facts as filters, or as an aggregate (grouped or one row of totals) for a count or a total; row counts across many tables come from the stream's `_stats` table or one `UNION ALL` statement, never one call per table. Every figure carries its stream, table, filters and the date of the call.

**Version:** 0.3.0 · **Category:** research · **Status:** experimental · **Output:** the reply

## Inputs

A question, with any names, numbers or years that narrow it. As an MCP prompt it takes one optional argument, appended to the text when given: `question`.

## Outputs

The answer as a short table or figures in the reply, with one source line per table read; or a statement of what was checked when nothing holds it.

## Evals

See [`evals/`](evals/). None yet.
