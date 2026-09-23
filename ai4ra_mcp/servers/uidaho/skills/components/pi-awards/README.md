# PI Awards

Lists a PI's active awards off a Banner Grant Personnel Inquiry export (FRIPSTG), one per line with grant, title, proposal number and maximum amount. Reading only.

**Version:** 0.1.0 · **Category:** pre-award · **Status:** experimental · **Output:** lines in the reply

## Inputs

The FRIPSTG export on any tab of the workbook. `dev/examples/FRIPSTG.csv` is one.

## Getting the input

1. Go to apps.uidaho.edu and open Banner Admin (Application Navigator).
2. In the search box type the page name, FRIPSTG, and press Enter.
3. Enter the PI's personnel ID (or click the three dots beside it to search by name) and click Go.
4. Click Tools (top right) and Export. The download is a CSV named after the page.
5. Open the CSV in Excel. Then say what you want in the pane.

## Outputs

The PI, one line per active award, the inactive count.

## Evals

See [`evals/`](evals/). None yet.
