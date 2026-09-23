#!/usr/bin/env python3
"""Generates template.json for the award-status skill. The sheet lists the accounts the award actually has, pulled from
the Lines sheet by formula (up to 15), with the budget from each account's own row and the spent and committed summed
from the expense codes that roll up to it; flags against the share of time elapsed; burn rate, runway, projection;
the F&A check on the MTDC base (everything but accounts 32, 40, 60 and the part of 31 above $25,000); the rebudget
each account's pace implies; closeout figures; the budget pools (Banner checks availability at the pool: General
Accounting, 2026-09-15: "all personnel roll to PC for checking budget balance, but the expenses on reports roll to the
primary expense account and for temp help that is 12, not 10"). Every figure is a formula; typed: the award's facts (B1:B5), the flag
threshold (B33) and the F&A rate (B37). Columns have fixed widths and no wrap; long notes and the email lines overflow to the right across empty cells."""
import json, os

COLS = 8; A, B, C, D, E, F, G, H = range(8)
ACCT = lambda rng: "((%s<>\"\")*(%s<>0)*ISNUMBER(IFERROR(%s*1,\"\")))" % (rng, rng, rng)   # 1 for an account row (a numeric code) on the Lines sheet, 0 for an expense code or a blank
NTH = lambda n: "AGGREGATE(15,6,(ROW(Lines!$A$2:$A$%d)-1)/%s,%d)" % (LN, ACCT("Lines!$A$2:$A$%d" % LN), n)   # the Lines row of the nth account
SLOTS = 15; R0 = 12; R1 = R0 + SLOTS - 1   # account slots, rows 12-26
LN = 300
v = []
def setc(r, c, val):
    while len(v) < r: v.append([None] * COLS)
    v[r - 1][c] = val
setc(1, A, "Award status"); setc(1, B, "")
setc(2, A, "Sponsor and award number"); setc(2, B, "")
setc(3, A, "Principal investigator"); setc(3, B, "")
setc(4, A, "Start date"); setc(4, B, ""); setc(4, C, '=IF(B4="","",IF(ISNUMBER(B4),B4,DATEVALUE(LEFT(B4,FIND(" ",B4&" ")-1))))')
setc(5, A, "End date"); setc(5, B, ""); setc(5, C, '=IF(B5="","",IF(ISNUMBER(B5),B5,DATEVALUE(LEFT(B5,FIND(" ",B5&" ")-1))))')
setc(6, A, "Review date"); setc(6, B, "=TODAY()")
setc(7, A, "Months elapsed"); setc(7, B, '=IF(AND(ISNUMBER(C4),ISNUMBER(C5)),ROUND(MIN(B6,C5)-C4,0)/30.4375,"")')
setc(8, A, "Months in the award"); setc(8, B, '=IF(AND(ISNUMBER(C4),ISNUMBER(C5)),(C5-C4)/30.4375,"")')
setc(9, A, "Share of time elapsed"); setc(9, B, '=IF(ISNUMBER(B8),MIN(1,MAX(0,B7/B8)),"")')
for c, h in enumerate(["Account", "Name", "Budget", "Spent", "Committed", "Available", "Share spent", "Flag"]): setc(11, c, h)
for n in range(1, SLOTS + 1):
    r = R0 + n - 1
    setc(r, A, '=IFERROR(INDEX(Lines!$A$2:$A$%d,%s)&"","")' % (LN, NTH(n)))
    setc(r, B, '=IF(A%d="","",INDEX(Lines!$B$2:$B$%d,%s))' % (r, LN, NTH(n)))
    setc(r, C, '=IF(A%d="","",INDEX(Lines!$D$2:$D$%d,%s))' % (r, LN, NTH(n)))
    setc(r, D, '=IF(A%d="","",SUMIF(Lines!$C$2:$C$%d,A%d,Lines!$E$2:$E$%d))' % (r, LN, r, LN))
    setc(r, E, '=IF(A%d="","",SUMIF(Lines!$C$2:$C$%d,A%d,Lines!$F$2:$F$%d))' % (r, LN, r, LN))
    setc(r, F, '=IF(A%d="","",C%d-D%d-E%d)' % (r, r, r, r))
    setc(r, G, '=IF(A%d="","",IF(C%d>0,D%d/C%d,""))' % (r, r, r, r))
    setc(r, H, '=IF(A%d="","",IF(C%d=0,IF(D%d+E%d>0,"Spending with no budget",""),IF(G%d>1,TEXT(G%d,"0%%")&" spent, over budget",IF(ISNUMBER($B$9),IF(ABS(G%d-$B$9)>$B$33,TEXT(G%d,"0%%")&" spent, "&TEXT($B$9,"0%%")&" of the time gone",""),""))))' % ((r,) * 8))
T = R1 + 1   # 27
setc(T, A, "Total")
for c, col in zip([C, D, E, F], "CDEF"): setc(T, c, "=SUM(%s%d:%s%d)" % (col, R0, col, R1))
setc(T, G, '=IF(C%d>0,D%d/C%d,"")' % (T, T, T))
setc(28, A, "Charges on expense codes that roll up to an account this award has no row for")
setc(28, D, '=SUMPRODUCT((Lines!$A$2:$A$%d<>"")*NOT(%s)*(Lines!$C$2:$C$%d<>"?")*(COUNTIF(Lines!$A$2:$A$%d,Lines!$C$2:$C$%d)=0),Lines!$E$2:$E$%d)' % (LN, ACCT("Lines!$A$2:$A$%d" % LN), LN, LN, LN, LN))
setc(28, H, '=IF(D28>0,"No budget line: checked against its pool (Budget pools below)","")')
# the codes behind row 28, listed: code, description, amount and the account each rolls up to
setc(28, B, '=IFERROR(TEXTJOIN(", ",TRUE,IF((Lines!$A$2:$A$%d<>"")*(Lines!$C$2:$C$%d<>"")*NOT(%s)*(Lines!$C$2:$C$%d<>"?")*(COUNTIF(Lines!$A$2:$A$%d,Lines!$C$2:$C$%d)=0),Lines!$A$2:$A$%d&" "&Lines!$B$2:$B$%d&" (Lines row "&ROW(Lines!$A$2:$A$%d)&")","")),"")' % (LN, LN, ACCT("Lines!$A$2:$A$%d" % LN), LN, LN, LN, LN, LN, LN))
setc(30, A, "Burn rate per month"); setc(30, B, '=IF(AND(ISNUMBER(B7),B7>0),D%d/B7,"")' % T)
setc(31, A, "Months of runway at that rate"); setc(31, B, '=IF(AND(ISNUMBER(B30),B30>0),F%d/B30,"")' % T); setc(31, C, "Months left in the award"); setc(31, D, '=IF(ISNUMBER(B8),MAX(0,B8-B7),"")')
setc(32, A, "Projected spend at the end date"); setc(32, B, '=IF(ISNUMBER(B30),D%d+B30*MAX(0,B8-B7),"")' % T); setc(32, C, "Over (+) or under (-) the budget"); setc(32, D, '=IF(ISNUMBER(B32),B32-C%d,"")' % T)
setc(33, A, "Flag threshold (share points)"); setc(33, B, 0.15)
setc(34, A, "Lines in the export"); setc(34, B, "=Lines!$I$1"); setc(34, C, "Export budget (should equal C%d)" % T); setc(34, D, "=SUM(Lines!$D$2:$D$%d)" % LN); setc(34, E, "Export spent (should equal D%d plus D28)" % T); setc(34, F, "=SUM(Lines!$E$2:$E$%d)" % LN)
acct = lambda code, col: 'SUMIF($A$%d:$A$%d,"%s",%s$%d:%s$%d)' % (R0, R1, code, col, R0, col, R1)
setc(36, A, "F&A check"); setc(36, B, "Indirect costs at the award's rate on the MTDC base, against the overhead posted")
setc(37, A, "F&A rate on this award"); setc(37, B, 0.5); setc(37, C, "estimate: the university's on-campus organized research rate; the award's own rate (FRMFUND) applies, as in effect when it was executed")
setc(38, A, "MTDC base spent"); setc(38, B, "=D%d-%s-%s-%s-MAX(0,%s-25000)" % (T, acct("32", "D"), acct("40", "D"), acct("60", "D"), acct("31", "D"))); setc(38, C, "all spending except participant support (32), capital outlay (40), overhead (60) and the part of subcontracts (31) above $25,000; tuition inside Other Expense is not excluded here")
setc(39, A, "Expected indirect"); setc(39, B, "=B38*B37")
setc(40, A, "Overhead posted"); setc(40, B, "=" + acct("60", "D"))
setc(41, A, "Gap (posted minus expected)"); setc(41, B, "=B40-B39"); setc(41, C, '=IF(AND(ISNUMBER(B39),B39>0),IF(ABS(B41)>0.02*B39,"Check: more than 2% off",""),"")')
setc(42, A, "Effective rate posted"); setc(42, B, '=IF(AND(ISNUMBER(B38),B38>0),B40/B38,"")'); setc(42, C, "overhead posted over the base spent; a capped or off-campus award reads below the university rate")
setc(44, A, "Rebudget at this pace"); setc(44, B, "The budget each account would need if it kept its rate to the end date")
for c, h in enumerate(["Account", "Name", "Budget", "Needed at this pace", "Difference", "Approval"]): setc(45, c, h)
for n in range(SLOTS):
    r, s = 46 + n, R0 + n
    setc(r, A, "=A%d" % s); setc(r, B, "=B%d" % s); setc(r, C, '=IF(A%d="","",C%d)' % (r, s))
    setc(r, D, '=IF(OR(A%d="",NOT(ISNUMBER($B$9)),$B$9=0),"",D%d/$B$9)' % (r, s))
    setc(r, E, '=IF(ISNUMBER(D%d),D%d-C%d,"")' % (r, r, r))
    setc(r, F, '=IF(ISNUMBER(E%d),IF(AND(A%d="32",E%d<0),"sponsor approval to move participant support out",IF(ABS(E%d)>0.1*$C$%d,"over 10%% of the award: sponsor approval likely","")),"")' % (r, r, r, r, T))
setc(61, A, "Total"); setc(61, C, "=SUM(C46:C60)"); setc(61, D, "=SUM(D46:D60)"); setc(61, E, "=SUM(E46:E60)")
setc(63, A, "Closeout"); setc(63, B, "At this pace")
setc(64, A, "Unspent at the end date"); setc(64, B, '=IF(ISNUMBER(B32),C%d-B32,"")' % T)
setc(65, A, "Open commitments to clear"); setc(65, B, "=E%d" % T)
setc(66, A, "Timing"); setc(66, B, '=IF(AND(ISNUMBER(B31),ISNUMBER(D31)),IF(B31>D31,"the available balance outlasts the award by "&TEXT(B31-D31,"0.0")&" months","the available balance runs out "&TEXT(D31-B31,"0.0")&" months before the end date"),"")')
# budget pools: Banner checks availability at the pool (all personnel together), not at the account; charges on expense
# codes whose account the award has no row for still draw on their pool, so they are counted here
pools = [("Personnel (PERS)", ["10", "11", "12"]), ("Operating expense", ["20", "30", "31", "32", "33", "50", "99"]), ("Capital outlay", ["40", "45"]), ("Overhead", ["60"]), ("Trustee/Benefits", ["70"])]
setc(68, A, "Budget pools"); setc(68, B, "Banner checks availability at the pool, all personnel together, not at the account")
for c, h in enumerate(["Pool", "Accounts", "Budget", "Spent", "Committed", "Available", "Share spent"]): setc(69, c, h)
for i, (name, accts) in enumerate(pools):
    r = 70 + i
    arr = "{" + ",".join('"%s"' % a for a in accts) + "}"
    setc(r, A, name); setc(r, B, ", ".join(accts))
    setc(r, C, "=SUMPRODUCT(--ISNUMBER(MATCH($A$%d:$A$%d,%s,0)),C$%d:C$%d)" % (R0, R1, arr, R0, R1))   # amounts as a separate argument: an empty slot's \"\" counts as 0
    noRow = '=SUMPRODUCT((Lines!$A$2:$A$%d<>"")*NOT(%s)*ISNUMBER(MATCH(Lines!$C$2:$C$%d,%s,0))*(COUNTIF(Lines!$A$2:$A$%d,Lines!$C$2:$C$%d)=0),Lines!$%%s$2:$%%s$%d)' % (LN, ACCT("Lines!$A$2:$A$%d" % LN), LN, arr, LN, LN, LN)
    setc(r, D, "=SUMPRODUCT(--ISNUMBER(MATCH($A$%d:$A$%d,%s,0)),D$%d:D$%d)+" % (R0, R1, arr, R0, R1) + (noRow % ("E", "E"))[1:])
    setc(r, E, "=SUMPRODUCT(--ISNUMBER(MATCH($A$%d:$A$%d,%s,0)),E$%d:E$%d)+" % (R0, R1, arr, R0, R1) + (noRow % ("F", "F"))[1:])
    setc(r, F, "=C%d-D%d-E%d" % (r, r, r))
    setc(r, G, '=IF(C%d>0,D%d/C%d,"")' % (r, r, r))
setc(75, A, "Total"); setc(75, C, "=SUM(C70:C74)"); setc(75, D, "=SUM(D70:D74)"); setc(75, E, "=SUM(E70:E74)"); setc(75, F, "=SUM(F70:F74)")
# email lines: every sentence of the memo built here by formula, so the memo skill copies and interprets nothing
M = lambda x: 'TEXT(%s,"$#,##0")' % x
setc(77, A, "Email lines"); setc(77, B, "The sentences of the memo, by formula, facts only; the memo copies the ones that are not blank, in order")
setc(78, A, '=IF(ISNUMBER(B9),"The award is "&TEXT(B9,"0%%")&" of the way through its period and "&TEXT(G%d,"0%%")&" of the budget is spent: "&%s&" of "&%s&", with "&%s&" committed and "&%s&" available.","")' % (T, M("D%d" % T), M("C%d" % T), M("E%d" % T), M("F%d" % T)))
for n in range(SLOTS):
    r, s = 79 + n, R0 + n   # one line per flagged account, in the flag's own words
    setc(r, A, '=IF(OR(A%d="",H%d=""),"",B%d&" (account "&A%d&"): "&H%d&", "&%s&" spent of "&%s&".")' % (s, s, s, s, s, M("D%d" % s), M("C%d" % s)))
setc(94, A, '=IF(D28>0,%s&" was charged to expense codes that roll up to an account this award has no budget line for: "&B28&". Banner checks that spending against the budget pool the account belongs to, not against the account, so the pool balance is the one that applies.","")' % M("D28"))
setc(95, A, '=IF(AND(ISNUMBER(B30),ISNUMBER(B31),ISNUMBER(D31)),"At the current rate of "&%s&" a month, the available balance lasts "&TEXT(B31,"0.0")&" months against "&TEXT(D31,"0.0")&" months left in the award; at that pace "&%s&" would be unspent at the end date and "&%s&" of commitments would still be open.","")' % (M("B30"), M("B64"), M("B65")))
setc(96, A, '=IF(B66="","","At this pace "&B66&".")')
setc(97, A, '=IF(C41="","","Overhead posted is "&TEXT(B42,"0.0%")&" of the direct-cost base spent, against the "&TEXT(B37,"0%")&" rate entered on the status sheet; the expected figure depends on the rate in the award agreement.")')
for n in range(SLOTS):
    r, s = 98 + n, 46 + n   # one line per account whose pace implies a change of more than a tenth of its budget
    setc(r, A, '=IF(OR(A%d="",NOT(ISNUMBER(E%d)),H%d=""),"",IF(ABS(E%d)>0.1*MAX(C%d,1),B%d&" is spending at a pace that would use "&%s&" by the end date, "&IF(E%d<0,%s&" less than",%s&" more than")&" its budget of "&%s&IF(F%d="","","; "&F%d)&".",""))' % (s, s, R0 + n, s, s, s, M("D%d" % s), s, M("-E%d" % s), M("E%d" % s), M("C%d" % s), s, s))
template = {
    "sheet": "Award status", "values": v,
    "formats": [
        {"address": "C12:F27", "number_format": "$#,##0"}, {"address": "G12:G27", "number_format": "0%"}, {"address": "D28", "number_format": "$#,##0"}, {"address": "B9", "number_format": "0%"}, {"address": "B33", "number_format": "0%"},
        {"address": "B30:B32", "number_format": "$#,##0"}, {"address": "D32", "number_format": "$#,##0"}, {"address": "D34", "number_format": "$#,##0"}, {"address": "F34", "number_format": "$#,##0"},
        {"address": "B7:B8", "number_format": "0.0"}, {"address": "B31", "number_format": "0.0"}, {"address": "D31", "number_format": "0.0"}, {"address": "B6", "number_format": "d mmm yyyy"}, {"address": "C4:C5", "number_format": "d mmm yyyy"},
        {"address": "B37", "number_format": "0.0%"}, {"address": "B38:B41", "number_format": "$#,##0"}, {"address": "B42", "number_format": "0.0%"}, {"address": "C46:E61", "number_format": "$#,##0"}, {"address": "B64:B65", "number_format": "$#,##0"}, {"address": "C70:F75", "number_format": "$#,##0"}, {"address": "G70:G74", "number_format": "0%"},
        {"address": "B33", "fill_color": "#FFFF00"}, {"address": "B37", "fill_color": "#FFFF00"},
        {"address": "A12:H26", "highlight_when": '=$H12<>""', "fill_color": "#FFF9C4"}, {"address": "A28:H28", "highlight_when": '=$H28<>""', "fill_color": "#FFF9C4"},
        {"address": "A41:C41", "highlight_when": '=$C41<>""', "fill_color": "#FFF9C4"}, {"address": "A46:F60", "highlight_when": '=$F46<>""', "fill_color": "#FFF9C4"},
        {"address": "A1:H112", "wrap_text": False}, {"address": "A1:A112", "column_width": 230}, {"address": "B1:F112", "column_width": 84}, {"address": "G1:G112", "column_width": 70}, {"address": "H1:H112", "column_width": 200}],
    "locked": ["A1:A9", "B6:B9", "C4:C5", "A11:H28", "A30:A34", "B30:B32", "C31:D32", "A33", "B34:F34", "A36:C36", "A37", "C37", "A38:C42", "A44:B44", "A45:F61", "A63:B66", "A68:G75", "A77:B112"],
    "from_context": {"B1": "award", "B2": "sponsor_award", "B3": "pi", "B4": "start_date", "B5": "end_date"},
    "notes": "Filled from the request: B1:B5 (title, sponsor and number, PI, start and end as the export writes them; C4:C5 hold them as dates). Rows 12-26 list the award's accounts from the Lines sheet by formula: budget from the account's row, spent and committed summed from the expense codes rolling up to it, available, share spent, a Flag in plain words (\"90% spent, 40% of the time gone\") when an account's share spent is more than B33 (15 points, the administrator's to change in Excel) from the share of time elapsed, is over budget, or has spending with no budget; row 27 totals; row 28 charges whose account the award has no row for, with the codes listed in B28. Rows 30-34 burn rate, runway, projection, threshold and the reconciliation against the export; rows 36-42 the F&A check on the MTDC base at the rate in B37 (50% by default, the award's own rate to be typed in Excel) with the effective rate posted; rows 44-61 the budget each account would need at its pace and which moves need the sponsor; rows 63-66 the closeout figures; rows 68-75 the budget pools as Banner enforces them (all personnel together), counting charges whose account the award has no row for; a row turns light yellow while its Flag, Check or Approval cell is filled; rows 77-112 the email's sentences by formula (opener, one per flagged account, no-line charges, runway, timing, F&A, one per flagged account whose pace differs from its budget), facts only, which the memo copies."}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.json")
json.dump(template, open(out, "w"), indent=0)
print("wrote", out, len(v), "rows")
