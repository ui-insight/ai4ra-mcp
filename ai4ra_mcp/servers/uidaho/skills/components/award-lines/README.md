# Award Lines

Mirrors a Banner Grant Inception to Date export (FRIGITD) on a Lines sheet by formula: the pane fills the export's tab name into one cell and the sheet reads code, description, budget, spent and committed from that tab, with an Account column rolling each code up by a formula built from General Accounting's expense code list and the chart of accounts. The model writes nothing and reports the checks.

**Version:** 3.0.0 · **Category:** post-award · **Status:** experimental · **Output:** a spreadsheet sheet

## Inputs

The FRIGITD export on any tab of the workbook (Tools > Export from the page, Account Summary at All Levels), found by its headers. `dev/examples/award-example.xlsx` has one.

## Outputs

A Lines sheet (template.json, from make_template.py: the header, the Account formula in C, I1 rows written, I2 codes the chart lacks, asserted to be 0) so an Award status sheet can list the award's accounts and sum spending under each. A new code is a new FTVACCT export and a regenerated template.

## Evals

See [`evals/`](evals/). None yet.
