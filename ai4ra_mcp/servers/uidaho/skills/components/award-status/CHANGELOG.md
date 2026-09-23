# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-09-15

- First version: template with SUMIF over the Ledger, flags against time elapsed, burn rate, runway, projection and reconciliation.

## [0.2.0] — 2026-09-15

- Reads a Lines sheet from a FRIGITD export instead of a transaction Ledger: budget, spent and committed come from the export, so the request supplies only the award's facts; a Committed column and the available balance; no outside-the-period row (the export has no dates).

## [0.2.1] — 2026-09-15

- The ten categories are the University of Idaho's budget pools (Salaries, Fringe Benefits, Travel, Other Expense, Subcontracts, Participant Support, Capital Outlay, Non-Capital Outlay, Overhead, Trustee/Benefits).

## [0.3.0] — 2026-09-15

- Three formula blocks added: the F&A check (expected indirect on the MTDC base at the rate in B31 against the overhead posted), the rebudget each pool's pace implies with the moves that need the sponsor, and the closeout figures.

## [0.3.1] — 2026-09-15

- Dates are taken as the export writes them ("9/15/2024 12:00:00 AM") and held as dates in C4:C5; the threshold and the rate are locked to the model after a run rewrote B27 with its own value.

## [0.4.0] — 2026-09-15

- The F&A rate is the template's 50% default, the award's own rate to be typed in Excel (rates are fixed at execution, so no lookup applies); the check shows the effective rate posted.

## [1.0.0] — 2026-09-15

- Lists the award's own accounts from the Lines sheet by formula (up to 15) instead of ten fixed pool names; the F&A base is a rule on account codes (32, 40, 60, and 31 above $25,000); a row for charges whose account the award has no row for.

## [1.1.0] — 2026-09-15

- A budget pools block (rows 68-75): Banner checks availability at the pool, all personnel together, so charges whose account the award has no row for are counted in their pool.

## [1.1.1] — 2026-09-15

- No helper column: the account lookups are folded into their cells.

## [1.1.2] — 2026-09-15

- Account slots ignore zero codes; the export line count reads the Lines check cell.

## [1.2.0] — 2026-09-15

- The prompt is a list of ten lines to reply with, each naming its cells: a run read the sheet and then said it had no instructions.

## [1.2.1] — 2026-09-15

- The pools block read #VALUE! because empty account slots hold text; amounts are now a separate SUMPRODUCT argument.

## [1.3.0] — 2026-09-15

- Flagged account rows, the no-row line, a failed F&A check and rebudget rows needing approval turn light yellow (conditional formats in the template).

## [1.3.1] — 2026-09-15

- The Flag column says why: over budget, ahead of or behind the clock by how many points, unbudgeted; the no-row line says it draws on its pool.

## [1.3.2] — 2026-09-15

- Flags in plain words: "90% spent, 40% of the time gone", "145% spent, over budget", "Spending with no budget".

## [1.4.0] — 2026-09-15

- An Email lines block (rows 77-117): every sentence of the memo built by formula, including the decisions, so the memo skill interprets nothing.

## [1.4.1] — 2026-09-15

- The email lines and the timing line state facts only: no decisions block, no 'consider' clauses.

## [1.4.2] — 2026-09-15

- Row 28 lists the codes behind the no-line amount (code, description, amount, the account it rolls up to) in B28, and the email line names them.

## [1.4.3] — 2026-09-15

- The no-line sentence says the spending is checked against its budget pool instead of citing sheet rows the PI never sees.

## [1.4.4] — 2026-09-15

- Fixed column widths and no wrap, instead of autofit, which had widened columns to the longest note and pushed the sheet off the screen.

## [1.4.5] — 2026-09-15

- The no-line code list skips blank rows.

## [1.4.6] — 2026-09-15

- The no-line sentence names the codes with their Lines rows only; the pace sentences cover flagged accounts only, so the email is not a table.
