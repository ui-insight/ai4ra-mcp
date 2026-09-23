# Lakehouse Answer

Answers a question from the University of Idaho data lakehouse: discovers the streams the client may query, reads each candidate stream's schema, then queries the table that holds the answer with the question's facts as filters, or as a grouped aggregate for a count or a total. Every figure carries its stream, table, filters and the date of the call.

**Version:** 0.1.0 · **Category:** research · **Status:** experimental · **Output:** the reply

## Inputs

A question, with any names, numbers or years that narrow it.

## Outputs

The answer as a short table or figures in the reply, with one source line per table read; or a statement of what was checked when nothing holds it.

## Evals

See [`evals/`](evals/). None yet.
