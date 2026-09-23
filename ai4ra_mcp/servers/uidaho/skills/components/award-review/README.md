# Award Review

A staged skill: a monthly award review from a Banner Grant Inception to Date export (FRIGITD) opened in Excel. Four steps run by the pane, no question: the award's facts from the export's key block (award-facts), which also names the tab it read (the request's, the only export, or the one the user is on), a Lines sheet that mirrors the export by formula (award-lines), an Award status sheet (award-status), and a memo to the PI (pi-memo).

**Version:** 5.0.0 · **Category:** post-award · **Status:** experimental · **Output:** three sheets

## Inputs

The export opened in Excel (`dev/examples/FRIGITD.csv`, or `award-example.xlsx` which is that file as Excel opens it).

## Getting the input

1. Go to apps.uidaho.edu and open Banner Admin (Application Navigator).
2. In the search box type the page name, FRIGITD, and press Enter.
3. Enter the grant code, leave Account Summary at All Levels, and click Go.
4. Click Tools (top right) and Export. The download is a CSV named after the page.
5. Open the CSV in Excel. Then say what you want in the pane.

## Outputs

Lines, Award status and Memo sheets.

## Evals

See [`evals/`](evals/). None yet.
