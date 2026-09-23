# Current and Pending

Fills a Current and pending sheet, one row per award of a PI: grant and title from the awards list, sponsor, period and total award from each award's FRIGITD export when it is in the workbook, and yellow cells for what Banner does not hold. Sponsor-neutral, for SciENcv and NIH Other Support alike.

**Version:** 0.1.0 · **Category:** pre-award · **Status:** experimental · **Output:** a spreadsheet sheet

## Inputs

The awards list (the pi-awards skill's reply) and one FRIGITD export tab per award, as many as you have. `dev/examples/current-pending-example.xlsx` has the list and one export.

## Getting the input

1. Go to apps.uidaho.edu and open Banner Admin (Application Navigator).
2. In the search box type the page name, FRIGITD, and press Enter.
3. Enter the grant code, leave Account Summary at All Levels, and click Go.
4. Click Tools (top right) and Export. The download is a CSV named after the page.
5. Open the CSV in Excel, and copy its tab into the workbook that holds the FRIPSTG export (right-click the tab, Move or Copy). Then say what you want in the pane.

## Outputs

The Current and pending sheet (template.json, from make_template.py): A:I facts, J:K the PI's, L the source tab, N1:N2 checks.

## Evals

See [`evals/`](evals/). None yet.
