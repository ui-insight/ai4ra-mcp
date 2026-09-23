#!/usr/bin/env python3
"""Generates template.json for the budget-nsf skill: the NSF budget form (lines A to M) with every total a formula.

Layout: rows 1-3 title and legend; 5-15 the Inputs block (rates, ceiling, cost sharing); 17 the year index; 18-24 the
Personnel block (A name, B role, C class, D annual salary, E months per year typed; F fringe rate, G-K salary by year,
L NSF line as formulas); 25 the outline's personnel amounts for year 1; 26-36 the other lines, typed per year in G-K;
38-58 the NSF lines A to M; 60-62 the checks. Every amount is typed or filled from the request; nothing is derived
from a count or a unit cost."""
import json, os

COLS = 12
A, B, C, D, E, F, G, H, I, J, K, L = range(12)
YEARS = list(zip([G, H, I, J, K], "GHIJK"))
v = []
def setc(r, c, val):
    while len(v) < r: v.append([None] * COLS)
    v[r - 1][c] = val

setc(1, A, "Budget NSF"); setc(2, A, "Sponsor / program"); setc(3, A, "Yellow cells came from the request or a Rates sheet, or are estimates; replace them and every total recalculates.")
for c, val in zip([A, B, C, D], ["Inputs", "Value", "Origin", "Note"]): setc(5, c, val)
inputs = [
    (6, "Project years", 3, "estimate", "Whole number of years; salaries beyond it come out as zero. Estimate: the announcement's maximum."),
    (7, "Escalation rate", 0.03, "estimate", "Salary growth per year"),
    (8, "Fringe faculty", 0, "not set", "From the Rates sheet or the request; a fraction"),
    (9, "Fringe staff", 0, "not set", "From the Rates sheet or the request; postdocs are staff"),
    (10, "Fringe students", 0, "not set", "From the Rates sheet or the request; graduate assistants are students"),
    (11, "Fringe temporary", 0, "not set", "From the Rates sheet or the request; hourly workers"),
    (12, "F&A rate", 0, "not set", "From the Rates sheet or the request; its source and effective period go here"),
    (13, "F&A base", "MTDC", "institution", "MTDC excludes equipment, participant support, tuition and the part of each subaward above $25,000 (applied per year here)"),
    (14, "Award ceiling", "not stated", "sponsor", "The chosen track's amount from the announcement; when none is stated, program funding divided by expected awards (say 'typical award' here)"),
    (15, "Cost sharing required", "No", "sponsor", None)]
for r, label, val, org, note in inputs:
    setc(r, A, label); setc(r, B, val); setc(r, C, org); setc(r, D, note)
for i, (c, _) in enumerate(YEARS): setc(17, c, i + 1)
for c, val in zip(range(12), ["Name", "Role", "Class", "Base salary", "Months per year", "Fringe rate", "Salary Y1", "Salary Y2", "Salary Y3", "Salary Y4", "Salary Y5", "NSF line"]): setc(18, c, val)
P1, P2 = 19, 24
for r in range(P1, P2 + 1):
    setc(r, F, '=IF($C%d="","",IF($C%d="faculty",$B$8,IF($C%d="staff",$B$9,IF($C%d="students",$B$10,$B$11))))' % (r, r, r, r))
    for c, col in YEARS:
        setc(r, c, '=IF($A%d="",0,IF(%s$17<=$B$6,$D%d*$E%d/12*(1+$B$7)^(%s$17-1),0))' % (r, col, r, r, col))
    setc(r, L, '=IF($C%d="","",IF($C%d="faculty","A","B"))' % (r, r))
# a template team, yellow estimates, so a skipped budget still computes; the administrator replaces it in Excel
setc(19, A, "PI (to be named)"); setc(19, B, "Principal investigator"); setc(19, C, "faculty"); setc(19, D, 120000); setc(19, E, 1)
setc(20, A, "Graduate student"); setc(20, B, "Graduate research assistant"); setc(20, C, "students"); setc(20, D, 35000); setc(20, E, 12)
setc(25, A, "Outline, year 1: senior personnel"); setc(25, B, 0); setc(25, D, "other personnel"); setc(25, E, 0); setc(25, G, "Fill the people above to about these amounts; the form does the rest.")
setc(26, A, "Other lines (per year, from the outline)")
for i, (c, _) in enumerate(YEARS): setc(26, c, "Year %d" % (i + 1))
typed = [(27, "Equipment"), (28, "Travel"), (29, "Participant support"), (30, "Materials and supplies"), (31, "Publication"), (32, "Consultant services"),
         (33, "Computer services"), (34, "Subawards"), (35, "Other"), (36, "Tuition (move it here from Other when known; excluded from MTDC)")]
for r, label in typed:
    setc(r, A, label)
    for c, _ in YEARS: setc(r, c, 0)
setc(38, A, "NSF budget")
for i, (c, _) in enumerate(YEARS): setc(38, c, "Year %d" % (i + 1))
setc(38, L, "Total")
guard = lambda col, inner: "=IF(%s$17<=$B$6,%s,0)" % (col, inner)
lines = [
    (39, "A Senior personnel", lambda col: '=SUMIF($L$19:$L$24,"A",%s$19:%s$24)' % (col, col)),
    (40, "B Other personnel", lambda col: '=SUMIF($L$19:$L$24,"B",%s$19:%s$24)' % (col, col)),
    (41, "C Fringe benefits", lambda col: '=SUMPRODUCT($F$19:$F$24,%s$19:%s$24)' % (col, col)),
    (42, "D Equipment", lambda col: guard(col, "%s27" % col)),
    (43, "E Travel", lambda col: guard(col, "%s28" % col)),
    (44, "F Participant support costs", lambda col: guard(col, "%s29" % col)),
    (45, "G1 Materials and supplies", lambda col: guard(col, "%s30" % col)),
    (46, "G2 Publication", lambda col: guard(col, "%s31" % col)),
    (47, "G3 Consultant services", lambda col: guard(col, "%s32" % col)),
    (48, "G4 Computer services", lambda col: guard(col, "%s33" % col)),
    (49, "G5 Subawards", lambda col: guard(col, "%s34" % col)),
    (50, "G6 Other (incl. tuition)", lambda col: guard(col, "%s35+%s36" % (col, col))),
    (51, "G Total other direct costs", lambda col: "=SUM(%s45:%s50)" % (col, col)),
    (52, "H Total direct costs", lambda col: "=%s39+%s40+%s41+%s42+%s43+%s44+%s51" % ((col,) * 7)),
    (53, "MTDC base", lambda col: guard(col, "%s52-%s42-%s44-%s36-MAX(0,%s34-25000)" % ((col,) * 5))),
    (54, "I Indirect costs", lambda col: '=IF($B$13="TDC",%s52,%s53)*$B$12' % (col, col)),
    (55, "J Total direct and indirect costs", lambda col: "=%s52+%s54" % (col, col)),
    (56, "K Fees", None),
    (57, "L Amount of this request", lambda col: "=%s55+%s56" % (col, col)),
    (58, "M Cost sharing", None)]
for r, label, f in lines:
    setc(r, A, label)
    for c, col in YEARS: setc(r, c, f(col) if f else 0)
    setc(r, L, "=SUM(G%d:K%d)" % (r, r))
setc(60, A, "Ceiling check"); setc(60, B, '=IF(ISNUMBER($B$14),IF(L57<=$B$14,"OK","Over"),"no ceiling stated")')
setc(61, A, "Two-month rule (senior personnel)")
setc(61, B, '=IF(SUMPRODUCT(($L$19:$L$24="A")*($E$19:$E$24>2))>0,"Over: a senior person exceeds 2 months","OK")')
setc(61, C, '=IF($B$61="OK",1,0)')
setc(62, A, "Share of ceiling"); setc(62, B, '=IF(ISNUMBER($B$14),TEXT(L57/$B$14,"0%")&" of the ceiling","no ceiling stated")'); setc(62, C, '=IF(ISNUMBER($B$14),L57/$B$14,"")')
template = {
    "sheet": "Budget NSF", "values": v,
    "formats": [
        {"address": "D19:D24", "number_format": "$#,##0"}, {"address": "G19:K24", "number_format": "$#,##0"}, {"address": "E19:E24", "number_format": "0.0"},
        {"address": "B25", "number_format": "$#,##0"}, {"address": "E25", "number_format": "$#,##0"}, {"address": "G27:L58", "number_format": "$#,##0"},
        {"address": "B7:B12", "number_format": "0.0%"}, {"address": "F19:F24", "number_format": "0.0%"}, {"address": "C62", "number_format": "0%"},
        {"address": "B6:B12", "fill_color": "#FFFF00"}, {"address": "A19:E20", "fill_color": "#FFFF00"}, {"address": "G36:K36", "fill_color": "#FFFF00"}],
    "locked": ["A1:A3", "A5:D5", "A6:A15", "G17:K17", "A18:L18", "A19:L24", "A25", "D25", "G25", "A26:K26", "A27:A36", "A38:L58", "A60:C62"],
    "from_context": {"B1": "title", "B2": "sponsor", "B6": "years", "B8": "fringe_faculty", "B9": "fringe_staff", "B10": "fringe_students", "B11": "fringe_temporary", "B12": "fa_rate", "B13": "fa_base", "D12": "rates_note", "B14": "ceiling", "D14": "ceiling_note",
                     "B25": "senior_personnel_year1", "E25": "other_personnel_year1",
                     "G27:K27": "equipment_by_year", "G28:K28": "travel_by_year", "G29:K29": "participants_by_year", "G30:K30": "supplies_by_year", "G31:K31": "publication_by_year",
                     "G32:K32": "consultants_by_year", "G33:K33": "computing_by_year", "G34:K34": "subawards_by_year", "G35:K35": "other_by_year"},
    "notes": "Filled from the request: B1:B2, B6:D15 (the rates B8:B12 and their source line D12 from a Rates sheet when the workbook has one; 0 with origin 'not set' until then), B25 and E25 (the outline's personnel amounts for year 1, a guide for whoever fills the people in) and the other lines per year in G27:K35. People are typed by hand in Excel in A19:E24 (name, role, class faculty/staff/students/temporary, annual salary, months per year); rows 19-20 hold a template team; G36:K36 takes tuition when it is known. Everything else is a formula: F fringe rate, G-K salaries, L the NSF line from the class, rows 39-58 the NSF lines, 60-62 the checks (C61 = 1 when no senior person exceeds two months; C62 = the amount requested over the ceiling)."}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.json")
json.dump(template, open(out, "w"), indent=0)
print("wrote", out, len(v), "rows")
