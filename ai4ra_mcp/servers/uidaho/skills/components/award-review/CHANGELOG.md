# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [1.0.0] — 2026-09-15

- First version: four steps.

## [1.1.0] — 2026-09-15

- Runs from a FRIGITD export, which carries the budget, spent and committed per account: the Lines step replaces the Ledger, and the question asks only for the award's title, sponsor, PI and dates.

## [2.0.0] — 2026-09-15

- No question: the award's facts come from a FRAGRNT export in the workbook (award-facts). Both exports are found by their headers, on tabs of any name.

## [2.1.0] — 2026-09-15

- Two steps in front: the tabs are named from the request or recognised by their headers (award-tabs), and the user confirms them before anything is read.

## [2.2.0] — 2026-09-15

- One export: the FRIGITD export's key block carries the award's facts, so no Grant Maintenance export is needed. Categories are the University of Idaho's budget pools.

## [2.3.0] — 2026-09-15

- A Rates step (uidaho-lookup) supplies the F&A rate; the status sheet gains the F&A check, the rebudget at pace and the closeout blocks; the memo carries them.

## [2.3.3] — 2026-09-15

- The Lines step requires write_values only, since the pane lays the sheet down (a run was told it had not called add_sheet and added a stray sheet); the confirm question is in the user's voice.

## [2.4.0] — 2026-09-15

- award-lines 1.0.0: the pool is a formula from the account prefix table; the model classifies nothing.

## [3.0.0] — 2026-09-15

- No Rates step: an award's F&A rate is fixed when it is executed, so the current negotiated rate does not apply; the status sheet defaults to 50% and shows the effective rate posted.

## [3.1.0] — 2026-09-15

- The status sheet lists the award's own accounts, however many, with the spending rolled up from expense codes by formula; nothing is classified by the model.

## [3.1.1] — 2026-09-15

- award-lines 1.2.0: the roll-up table comes from the university's chart of accounts.

## [3.2.0] — 2026-09-15

- The status sheet shows the budget pools beside the accounts; temporary pay to 12 confirmed by General Accounting.

## [4.0.0] — 2026-09-15

- No question: the tabs and confirm steps are gone. The export is the tab the request names, else the only tab that looks like it, else the one the user is on; the facts step says which it read.

## [4.1.0] — 2026-09-15

- The Lines sheet is a plain six-column table and the status sheet has no helper column: nothing on either that is not the award's.

## [4.2.0] — 2026-09-15

- First run end to end on the formula sheets. The status skill's report is a ten-line list; the Lines step accepts references and is gated by its assertions alone.

## [4.4.0] — 2026-09-15

- The memo is an email: subject and body in two cells.

## [5.0.0] — 2026-09-15

- The Lines step is formulas over the export (award-lines 3.0.0); the model writes nothing in any step but the memo. The summary names the phrases that should reach it (award check, award review) after a run picked award-facts instead.

## [5.1.0] — 2026-09-15

- The memo is assembled from sentences the status sheet builds by formula; the model interprets nothing.
