---
name: award-review
version: 4.0.0
category: post-award
domain: research-administration
status: experimental
tags: [award-review, burn-rate, ledger, memo, post-award, workflow]
audience: [post-award-staff, research-administrators]
owner: nlayman
created: 2026-09-15
updated: 2026-09-15
---

# Award Review — Prompt

> **Purpose:** A monthly award review from a Banner Grant Inception to Date export (FRIGITD) opened in Excel: a Lines sheet, an Award status sheet (budget, spent and committed by pool, flags, runway, projection, F&A check, rebudget at pace, closeout) and a memo to the PI.
> **Expected input:** The FRIGITD export (its key block carries the title, sponsor, PI and project period) on the tab the request names, else the only tab that looks like the export, else the one the user is on; nothing is asked. In Excel.
> **Expected output:** Lines, Award status and Memo sheets.

---

## Prompt

This skill is a table, not a recipe: its catalog entry lists four steps, each a skill with the context drafted for it and the tools a run must have called. When you have called this skill, reply with one short line saying the review is starting, and nothing else.

---

## Quality Standards

1. **Four steps, in order**: facts, lines, status, memo; no question.
