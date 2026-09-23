# Current and Pending Support

A staged skill: a PI's current and pending support from Banner exports. Two steps run by the pane: the award list from the FRIPSTG export (pi-awards), then the Current and pending sheet filled from each award's FRIGITD export where the workbook has one (current-pending). Nothing is asked; the reply names the exports still to fetch.

**Version:** 1.0.0 · **Category:** pre-award · **Status:** experimental · **Output:** one sheet

## Inputs

A workbook with the FRIPSTG export for the PI on one tab and a FRIGITD export per active award on other tabs, as many as you have gathered. `dev/examples/current-pending-example.xlsx` to try it.

## Getting the input

1. Go to apps.uidaho.edu and open Banner Admin (Application Navigator).
2. In the search box type the page name, FRIPSTG for the award list, then FRIGITD for each active award, and press Enter.
3. For FRIPSTG enter the PI's personnel ID (or search by name with the three dots) and click Go; for FRIGITD enter the grant code and click Go.
4. Click Tools (top right) and Export. The download is a CSV named after the page.
5. Open the CSV in Excel. Copy every export's tab into one workbook (right-click a tab, Move or Copy). Then say what you want in the pane.

## Outputs

A Current and pending sheet. Person-months and overlap are the PI's to fill; awards with no export yet show pale cells and are named in the reply.

## Evals

See [`evals/`](evals/). None yet.
