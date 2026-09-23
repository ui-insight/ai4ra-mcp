# Project Timeline (Gantt)

Draws a Gantt chart of a project's tasks in months, the way the pane's first hand-made one was built: a Timeline sheet with Task, Start month and Duration in months, a stacked bar chart of those three columns, and one edit that hides the start series and reverses the categories so the first task is at the top. Three tool calls. No dates, helper columns or fills.

**Version:** 0.5.1 · **Category:** drafting · **Status:** experimental · **Output:** a chart

## Inputs

Tasks with a start month and a duration in months, from selected cells, an activities table or the user's description. A "1-6" range is start 1, duration 5; a milestone is duration 0.

## Outputs

A "Timeline" sheet holding the task rows (a short action label, start month, duration, and the full description) and the chart. When the source has an aim or phase column, or more than twelve rows, the skill first offers one bar per aim instead of one per task.

## Evals

See [`evals/`](evals/). None yet.
