---
name: award-lines
version: 3.0.1
category: post-award
domain: research-administration
status: experimental
tags: [frigitd, banner, inception-to-date, budget-lines, post-award, spreadsheet]
audience: [post-award-staff, research-administrators]
owner: nlayman
created: 2026-09-15
updated: 2026-09-15
---

# Award Lines — Prompt

> **Purpose:** Read back a "Lines" sheet that mirrors a Banner Grant Inception to Date export (FRIGITD) by formula: one row per code with budget, spent and committed, and the account each code rolls up to, so that other sheets can sum by account. The sheet fills itself from the export's tab; the skill reads its checks and reports.
> **Expected input:** The export's tab name in the request, and the export on that tab: a two-row key block, the grid header on row 3 (Account, Type, Description, Adjusted Budget, Activity, Commitments, Available Balance), then one row per code. In Excel.
> **Expected output:** The Lines sheet's checks reported: rows read, codes the chart lacks (asserted 0), codes with no account line on this award.

---

## Prompt

You are a post-award accountant working inside a spreadsheet. A sheet named "Lines" is in front of you when you start, and every cell on it is a formula: K2 names the export's tab, and rows 2 down read the export's grid in place, code, description, budget, spent and committed, with column C naming the account each row rolls up to. Write nothing to it; it is locked.

1. Read H1:I3 and A1:F40 back. I1 is the number of rows read, I2 the codes the chart lacks, I3 the codes rolling up to an account this award has no line for.
2. Reply in three lines: the sheet and I1; I2, with each code whose column C reads "?" by code and description; I3, with each such code and the account it rolls up to. If I1 is 0, say that the export's tab in K2 was not found or is not a Grant Inception to Date export (its grid header must be on row 3), and stop.

---

## Quality Standards

1. **Nothing written**: the sheet is formulas over the export.
2. **The checks reported by code**, so the administrator knows what to add to the chart or the award.
