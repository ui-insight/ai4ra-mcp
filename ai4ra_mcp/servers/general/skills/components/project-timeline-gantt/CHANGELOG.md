# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.5.1] — 2026-09-14

- Task labels are action phrases of at most four words written from the description, which is kept in column D; grouping by aim is offered when the list has a phase or aim column or more than twelve rows.

## [0.5.0] — 2026-09-14

- Back to the simple chart: months, three columns, add_chart BarStacked, one edit_chart. The add_gantt tool, the table form, dates, grouping and read-backs are gone.

## [0.4.1] — 2026-09-14

- The tool is pointed at the existing table with column letters and reads months, dates and text ranges like 1-6 itself; the skill writes a block only for tasks that came from a narrative.

## [0.4.0] — 2026-09-14

- The timeline is built by the new add_gantt tool from a Task | Start | End block in months (no start date needed); the skill only prepares the block. Both forms come from the tool.

## [0.3.4] — 2026-09-14

- Chart form: the Start column is shown as General while the chart is built, so Excel takes it as a series rather than a second category level; horizontal task labels and a taller, wider chart.

## [0.3.3] — 2026-09-14

- Follow the recipe as written, one call per turn, rebuild on an existing Timeline sheet; the chart is edited by its name from the add result with series_by Columns set explicitly.

## [0.3.2] — 2026-09-14

- Dates are written as =DATE() formulas and verified as serials before charting; a text date turned the Start column into category labels, put the header row in as a task, and made the axis count days.

## [0.3.1] — 2026-09-14

- Row labels are condensed task descriptions (a short verb phrase); longer wording goes in a Notes column.

## [0.3.0] — 2026-09-14

- Two forms: the filled-cell table (default; spans marked by formulas, read back, then filled by phase colour; pastes into Word as a table) and the chart. The skill picks from context or asks once.

## [0.2.0] — 2026-09-14

- The chart is a real Gantt chart: a BarStacked chart of Task | Start | Duration | Milestone with the Start series hidden, categories reversed and a date axis, using the add-in's new per-series fill and BarStacked support. The character grid is gone; a text timeline remains only as the no-spreadsheet fallback.

## [0.1.1] — 2026-09-14

- Before building a long or narrative-derived list, ask whether to group tasks under milestones or phases; group rows take their dates from their tasks by formula.

## [0.1.0] — 2026-09-14

- Initial version: task list or narrative in, formula-drawn Gantt grid on a new sheet out, with milestones, phase colours and resolution chosen from the span.
