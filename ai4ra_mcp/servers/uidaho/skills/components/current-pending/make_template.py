#!/usr/bin/env python3
"""Generates template.json for the current-pending skill: a "Current and pending" sheet, one row per award of a PI,
sponsor-neutral so it feeds NSF's SciENcv entry and NIH's Other Support alike. Columns A:I are facts Banner holds
(FRIPSTG for the list, each award's FRIGITD key block for sponsor, dates and the budget); J:K are the PI's (person-months,
overlap), yellow; L names the tab the facts came from. A fact cell left empty beside a listed award turns light yellow
by conditional format: an export not yet provided. Checks in N1:N2: awards listed (asserted at least 1), awards with dates."""
import json, os

COLS = 14; SLOTS = 20; R0, R1 = 5, 24
v = [[None] * COLS for _ in range(R1)]
v[0][0] = "Current and pending support"; v[0][1] = ""
v[1][0] = "Yellow cells are the PI's: Banner does not hold person-months or overlap. A pale cell beside an award is a fact its FRIGITD export would supply."
for c, h in enumerate(["Grant", "Title", "Sponsor", "Sponsor's award number", "Role", "Status", "Start", "End", "Total award", "Person-months per year", "Overlap with this proposal", "From tab"]): v[3][c] = h
v[0][12] = "Awards listed"; v[0][13] = '=SUMPRODUCT(--(A%d:A%d<>""))' % (R0, R1)
v[1][12] = "Awards with dates"; v[1][13] = '=SUMPRODUCT((A%d:A%d<>"")*(G%d:G%d<>""))' % (R0, R1, R0, R1)
template = {"sheet": "Current and pending", "values": v,
            "formats": [{"address": "I%d:I%d" % (R0, R1), "number_format": "$#,##0"}, {"address": "J%d:K%d" % (R0, R1), "fill_color": "#FFFF00"},
                        {"address": "C%d:I%d" % (R0, R1), "highlight_when": '=AND($A%d<>"",C%d="")' % (R0, R0), "fill_color": "#FFF9C4"},
                        {"address": "B%d:B%d" % (R0, R1), "wrap_text": True}, {"address": "K%d:K%d" % (R0, R1), "wrap_text": True}, {"address": "A4:L4", "bold": True}, {"address": "A1:L4", "autofit_columns": True}],
            "locked": ["A1:A2", "A4:L4", "M1:N2"],
            "from_context": {"B1": "pi"},
            "notes": "B1 the PI from the request. One award per row from row 5: A:B and F, L from the awards list; C, G, H from the award's FRIGITD key block and I a SUM over that tab's Adjusted Budget column, when the tab is in the workbook; D, E, J, K are the PI's or the administrator's. N1 awards listed, asserted at least 1; N2 awards with dates."}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.json")
json.dump(template, open(out, "w"), indent=0)
print("wrote", out, len(v), "rows")
