# Budget NSF

Fills the NSF budget form (lines A to M) from a Budget outline sheet. Ships a template for the Budget NSF sheet with every total a formula and its labels and formulas locked; the skill maps the outline's rows into the input cells. Other sponsors get their own template skills.

**Version:** 3.2.0 · **Status:** experimental · **Output:** a spreadsheet sheet

## Inputs

A Budget outline sheet (from the budget-outline skill) and the rates: from a sheet named Rates when the workbook has one (an institution's rates skill writes it with a Source line; the University of Idaho's is uidaho-rates-sheet), else from the request.

## Outputs

The Budget NSF sheet: inputs and every non-personnel line filled from the outline, the rates from the Rates sheet with its Source line beside them, a template team in the personnel rows with the outline's year-1 personnel amounts beside them for the research administrator to fill against, the NSF lines by year with a Total column, the ceiling check, the two-month rule and the share of the ceiling.

## Evals

See [`evals/`](evals/). None yet.
