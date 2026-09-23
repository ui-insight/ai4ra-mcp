# Evals — project-timeline-gantt

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml` (with `validated_against_version`), `input.md` (the task list or narrative and any answers), and `expected.md` describing the sheet: the task table with its formulas, the chart's type and source block, the series fills, the axis bounds and format, which rows are milestones.

## Case selection

- A 12-task list with calendar dates over 18 months: monthly axis units, bars and two milestones.
- A five-year proposal narrative with three aims and no dates: proposed tasks by year and quarter, listed as assumptions.
- A five-year span: quarterly axis units and a "mmm yy" axis format.
- Tasks with duration instead of end date: end computed as a formula.

No cases yet.
