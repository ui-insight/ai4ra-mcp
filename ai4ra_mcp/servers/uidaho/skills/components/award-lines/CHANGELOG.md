# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-09-15

- First version: the first working step of the award-review workflow, usable alone on any FRIGITD export.

## [0.2.0] — 2026-09-15

- The export is found by its headers on any tab, not taken from the sheet the user is on.

## [0.2.1] — 2026-09-15

- The tab named in the request comes first; the headers decide only when none is named.

## [0.3.0] — 2026-09-15

- Matches the University of Idaho's export: a key block above the grid, quoted headers, budget on pooled accounts and spending on detail accounts; the ten categories are the ten budget pools.

## [0.4.0] — 2026-09-15

- Ships a template: the header, the ten pool names, and a check that every Category is a pool, asserted; a run had used its own category words and the status sheet summed only part of the award.

## [0.4.1] — 2026-09-15

- Says outright that detail rows get the pool they are charged against as their Category: a run left them blank and categorised only the pool rows.

## [1.0.0] — 2026-09-15

- The pool is a formula from the account code's prefix, looked up in a table of the university's chart of accounts that ships in the template; the model copies five columns and classifies nothing. Two runs had left the detail rows unclassified.

## [1.1.0] — 2026-09-15

- Rolls up to account codes, not pool names: an account row (numeric code) rolls up to itself, an expense code to the account its prefix maps to; a Kind column tells the two apart by formula. The status sheet lists whatever accounts the award has.

## [1.2.0] — 2026-09-15

- The roll-up table is derived from the university's chart of accounts (FTVACCT): the chart's Type gives each expense code's family, the split inside a family is a rule in make_template.py, and the 44 prefixes reproduce all 439 active codes. Tuition rolls up to 70 Trustee/Benefits, temporary help to 12, participant support to 32.

## [1.2.1] — 2026-09-15

- When several tabs look like the export and none is named, the one the user is on.

## [2.0.0] — 2026-09-15

- Six columns and two check cells, nothing else: the roll-up table moved inside the Account formula and the Kind column went, so the sheet carries only the award's rows.

## [2.0.1] — 2026-09-15

- Values, never formulas pointing at the export, and exactly the grid's rows: a run filled 299 rows with references and the zeros below the data read as unknown codes. The Account formula and the row count now ignore blanks and zeros.

## [2.1.0] — 2026-09-15

- References to the export's cells are as welcome as values, since the model prefers them and a Lines sheet that follows the export is no worse.

## [2.2.0] — 2026-09-15

- Rows turn light yellow when the code is one the chart lacks or one rolling up to an account the award has no line for, with a third check cell counting the latter; the same rows the status sheet's no-line row counts.

## [2.3.0] — 2026-09-15

- The roll-up comes first from General Accounting's expense code list (2019), which places every one of the example award's codes as the rules did and differs from them on eight codes elsewhere; the chart and the rules cover the 97 codes added since.

## [3.0.0] — 2026-09-15

- The sheet reads the export in place: the pane fills the tab name into K2 and every row is a formula over that tab. The model writes nothing. A run had written lookups that failed on every expense code and left the status sheet #N/A.

## [3.0.1] — 2026-09-15

- Rows below the export's data read blank, not 0 (INDEX of an empty cell gives 0), so lists built over the sheet stop at the data.
