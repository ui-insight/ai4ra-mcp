---
name: project-timeline-gantt
version: 0.5.6
category: drafting
domain: research-administration
status: experimental
tags: [gantt, timeline, project-plan, chart, research-administration]
audience: [principal-investigators, pre-award-staff, project-managers]
owner: nlayman
created: 2026-09-14
updated: 2026-09-14
---

# Project Timeline (Gantt) — Prompt

> **Purpose:** Draw a Gantt chart of a project's tasks in months: a stacked bar chart whose start series is hidden, so each bar runs from the task's start month for its duration.
> **Expected input:** Tasks with a start month and a duration in months, from the sheet the request names, the selected cells, or the request itself. A range written as "1-6" is start 1, duration 5; a task with no months gets an estimate, marked in the reply.
> **Expected output:** A "Timeline" sheet with Task (a short action label), Start (month), Duration (months) and Description, and the Gantt chart beside them, one bar per task or per aim.

---

## Prompt

Build the Gantt chart in three tool calls and nothing else, after one question when there is something to group.

**Offer grouping first** when the task list has a phase or aim column (Related Aim, Phase, Objective, Work package) or more than twelve rows. Ask once, in one line ending with a question mark: one bar per task, or one bar per aim with its tasks' months merged (start = earliest start, end = latest end)? Show the aim names and the row count each way. "Group", "keep all", or an edited list are answers; an empty reply means group. Skip the question for a short list with nothing to group by, and when the request has already decided (one bar per task, or grouped) or says there are no questions.

1. Add a sheet named "Timeline" (or reuse an empty one) and write, from A1, a header row and one row per task (or per group), rows in order of start month (earliest first; milestones take their place by month, not at the end), so that with the axis reversed the chart reads top to bottom in time: A Task, B Start month as a number, C Duration in months as a number, D Description (the original text, in full). The Task cell is an action label you write, not the description copied: a verb and its object in at most four words, made from the description, for example "Design & install sensors" for "Design and install integrated sensor suite (soil moisture, temperature, gas flux) in the chambers", "Develop data pipeline", "Collect baseline dataset", "Train supervised models". A grouped row's label is the aim's name. Take the numbers from the tasks as given; a range like "1-6" means start 1 and duration 5. A milestone (a single event, given as duration 0 or with no duration) is written with duration 0.5 so that it shows as a short mark on the chart; a task with no duration that is not a milestone gets 1. Do not use dates or formulas here.
2. Call add_chart with type BarStacked, source A1:C<last row>, series_by Columns, title "Project timeline".
3. Call edit_chart on that chart with: series index 1 fill "none"; series index 2 fill "#1F4E79" and gap_width 40; axes.category.reverse true; axes.value.title "Month"; legend "none"; size width 800 and height 22 points per task plus 80.

Then reply in two lines: the sheet and chart names, and the span in months, noting that milestones are drawn as half-month marks. If the tasks came from your own reading of a narrative rather than the user's numbers, list the months you assumed.

---

## Quality Standards

1. Three tool calls; no dates, no helper columns, no fills.
2. Start and Duration are numbers the user gave or that were read straight from the task list.
3. Labels are actions: a verb and an object, at most four words; the full description lives in column D.
