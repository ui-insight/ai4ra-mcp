---
name: proposal-workbook
version: 5.1.0
category: drafting
domain: research-administration
status: experimental
tags: [proposal, rfa, grants-gov, workbook, narrative, work-plan, timeline, budget, orchestration, research-administration]
audience: [principal-investigators, pre-award-staff, proposal-developers]
owner: nlayman
created: 2026-09-14
updated: 2026-09-22
---

# Proposal Workbook — Prompt

> **Purpose:** Turn a chosen funding opportunity into a proposal-planning workbook: a table of eight steps the pane runs one after another, each skill in its own conversation with a context the pane fills from the run's earlier outputs (ask; RFA sheet; narrative; work plan; a Rates sheet; budget outline; NSF budget form; Gantt). The budget is estimated from the plan and asks nothing; a reviewer edits the outline sheet and reruns the form.
> **Expected input:** An opportunity the user picked from the funding-opportunity finder's list (a number, a title or a grants.gov link); then, in answer to stage 1, the project title, the idea, the team, the length and any other context. In Excel.
> **Expected output:** Sheets RFA, Narrative, Work plan, Rates, Budget outline, Budget NSF and Timeline, built over eight stages with a short status after each. The pane starts each stage itself and checks that the stage's tools were called.

---

## Prompt

This skill is a table, not a recipe: its catalog entry lists eight steps, each a skill with the context drafted for it and the tools a run must have called. Engaging it starts a run that the pane drives step by step, each skill in its own conversation with a context the pane fills from the run's earlier outputs. Nothing here is followed by a model beyond this: when you have called this skill, reply with one short line saying the workflow is starting, and nothing else.

---

## Quality Standards

1. **A table, run by the pane.** Every step is a stand-alone skill; the workbook adds only the contexts.
2. **One question**, at the start; everything after is estimated from the plan and marked.
