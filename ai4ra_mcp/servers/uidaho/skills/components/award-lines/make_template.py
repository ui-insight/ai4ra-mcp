#!/usr/bin/env python3
"""Generates template.json for the award-lines skill: the Lines sheet, a copy of every row of a FRIGITD export with one
formula column, C "Account": an account row (numeric code) is itself; an expense code (E4105, ES001) takes the account
its longest matching prefix maps to, the table being two array constants inside the formula (nothing else on the sheet).

The table comes first from General Accounting's expense code list, dev/examples/expense-codes-2019.csv (each code with
its primary expense category, 10 Salaries to 70 Trustee/Benefits), and for the codes added to the chart since then from
dev/examples/FTVACCT.csv (Banner's Account Code Validation page): its Type gives the family (PC personnel, OE operating
expense, CO capital outlay, OH overhead, TB trustee/benefits) and account_for() the account within it. The prefixes are
the shortest that reproduce every active code's account, checked below.
General Accounting's description of the chart (2026-09-15): E4xxx personnel; E5xxx everything other than personnel,
capital and tuition; E6xxx capital outlay of $5K and over; E78xx and E79xx non-capital equipment; E7150-E7154
participant support; E7060, E7099, E7110-E7149 and E7199 tuition; E75xx payments as agent; ES subawards; EXCS cost
share reallocations. The split of E5 between Travel (20) and Other Expense (30) is this file's rule, not the chart's.
Temporary pay to 12 confirmed by General Accounting the same day: reports roll expenses to the primary account, temp help
is 12 not 10; budget availability is checked at the pool (FTMACCT's Pool Account, PERS for all personnel).
Checks on the sheet: I1 rows written; I2 codes the chart lacks (asserted 0)."""
import csv, json, os

here = os.path.dirname(os.path.abspath(__file__))
chart = os.path.join(here, "..", "..", "..", "dev", "examples", "FTVACCT.csv")
FAMILY = {"PC": {"10", "11", "12", "33"}, "OE": {"20", "30", "31", "32", "33", "50", "99"}, "CO": {"40", "45", "33"}, "OH": {"60"}, "TB": {"70", "32", "33"}, "TR": {"80"}}

def account_for(code, typ, title):
    """The account an expense code rolls up to. The family comes from the chart's Type; the split inside a family
    (salaries against fringe against temporary help; travel against the rest of operating expense) from the code."""
    t = title.lower()
    if code.endswith("CS") or code.startswith("EXCS"): return "33"        # cost-share codes and cost-share reallocations
    if typ == "PC":
        if code.startswith("E42"): return "11"
        if "temporary" in t or "temp " in t: return "12"
        return "10"
    if typ == "OE":
        if code.startswith("ES"): return "31"
        if code.startswith("E715"): return "32"
        if code.startswith("E53") and code >= "E5360" and code != "E5395": return "20"   # vehicles, airfare, ground, per diem, other travel
        if code == "E5971": return "20"                                     # student travel
        if code == "E5141": return "31"                                     # subcontract travel
        return "30"
    if typ == "CO": return "40" if code.startswith("E6") else "45"
    if typ == "OH": return "60"
    if typ == "TB": return "32" if code.startswith("E715") else "70"   # participant support (32) is typed TB since 2018, like its codes
    if typ == "TR": return "80"
    return "30"

booklet = os.path.join(here, "..", "..", "..", "dev", "examples", "expense-codes-2019.csv")   # General Accounting's expense code list: code -> primary expense category
listed = {r[0]: r[2] for r in list(csv.reader(open(booklet, encoding="utf-8")))[1:] if r[0].startswith("E") and r[2]}
rows = [r for r in csv.reader(open(chart, encoding="utf-8-sig"))][1:]
from datetime import datetime
codes, when = {}, {}
for r in rows:   # a code listed more than once: the row with the latest effective date is the current one
    code, title, typ, status, eff = r[1], r[2], r[3], r[6], r[8]
    if not (code.startswith("E") and status == "A"): continue
    d = datetime.strptime(eff, "%m/%d/%Y %I:%M:%S %p") if eff else datetime.min
    if code not in when or d >= when[code]: codes[code] = (typ, title); when[code] = d
# the booklet's category where it lists the code; the chart's family and this file's rules for codes added since
target = {c: listed.get(c) or account_for(c, t, ti) for c, (t, ti) in codes.items()}
for c, a in target.items():
    if c not in listed: assert a in FAMILY[codes[c][0]], (c, codes[c], a)
unlisted = [c for c in target if c not in listed]

# the shortest prefixes that reproduce every code's account, longest prefix winning at lookup
rules = {}
def carve(prefix):
    members = [c for c in target if c.startswith(prefix)]
    accts = {target[c] for c in members}
    if len(accts) == 1: rules[prefix] = accts.pop(); return
    # a rule for the majority at this prefix, longer rules for the rest
    major = max(accts, key=lambda a: sum(1 for c in members if target[c] == a))
    rules[prefix] = major
    for nxt in sorted({c[:len(prefix) + 1] for c in members if target[c] != major}): carve(nxt)
for p in sorted({c[:1] for c in target}): carve(p)
def lookup(code):
    for n in (5, 4, 3, 2, 1):
        if code[:n] in rules: return rules[code[:n]]
    return "?"
bad = [(c, target[c], lookup(c)) for c in target if lookup(c) != target[c]]
assert not bad, bad[:5]
prefixes = sorted(rules.items())

ROWS = 300
COLS = 11
# the roll-up table lives inside the formula as two array constants, shortest prefix first so the last match is the longest
ordered = sorted(rules.items(), key=lambda kv: (len(kv[0]), kv[0]))
P = "{" + ",".join('"%s"' % k for k, _ in ordered) + "}"
Q = "{" + ",".join('"%s"' % a for _, a in ordered) + "}"
v = [[None] * COLS for _ in range(ROWS)]
for c, h in enumerate(["Code", "Description", "Account", "Budget", "Spent", "Committed"]): v[0][c] = h
# the export is read in place: K2 names its tab (filled by the pane from the step's context), K3 strips any note after
# it, and the rows below the export's header (row 3: Account, Type, Description, Adjusted Budget, Activity, Commitments)
# come through by INDIRECT, so nothing is copied by hand
v[0][10] = "Export tab"; v[1][10] = ""
v[2][10] = '=IF(K2="","",TRIM(LEFT(K2,IFERROR(FIND(" (",K2)-1,LEN(K2)))))'
tab = "\"'\"&$K$3&\"'!\""
def pull(col, r):   # the export's column col at the row two below this one (row 2 here is the export's row 4); an empty cell reads "" (INDEX alone would give 0)
    cell = 'INDEX(INDIRECT(%s&"%s:%s"),ROW()+2)' % (tab, col, col)
    return 'IFERROR(IF(%s="","",%s),"")' % (cell, cell)
for r in range(2, ROWS + 1):
    v[r - 1][0] = '=IF($K$3="","",%s)' % pull("A", r)
    v[r - 1][1] = '=IF(A{r}&""="","",%s)'.replace("{r}", str(r)) % pull("C", r)
    look = '"?"'
    for n in (1, 2, 3, 4, 5): look = 'IFERROR(LOOKUP(2,1/(LEFT(A{r},LEN(%s))=%s),%s),%s)' % (P, P, Q, look) if n == 1 else look
    v[r - 1][2] = ('=IF(OR(A{r}&""="",A{r}=0),"",IF(ISNUMBER(IFERROR(A{r}*1,"")),TRIM(A{r})&"",IFERROR(LOOKUP(2,1/(LEFT(A{r},LEN(%s))=%s),%s),"?")))' % (P, P, Q)).replace("{r}", str(r))
    for c, col in ((3, "D"), (4, "E"), (5, "F")):
        v[r - 1][c] = ('=IF(A{r}&""="","",IFERROR(--%s,0))' % pull(col, r)).replace("{r}", str(r))
v[0][7] = "Rows"; v[0][8] = '=SUMPRODUCT(--(C2:C%d<>""))' % ROWS
v[1][7] = "Codes the chart lacks"; v[1][8] = '=COUNTIF(C2:C%d,"?")' % ROWS
v[2][7] = "Codes rolling up to an account this award has no line for"; v[2][8] = '=SUMPRODUCT((C2:C%d<>"")*(C2:C%d<>"?")*(COUNTIF(A2:A%d,C2:C%d)=0))' % (ROWS, ROWS, ROWS, ROWS)
template = {"sheet": "Lines", "values": v,
            "formats": [{"address": "D2:F%d" % ROWS, "number_format": "$#,##0.00"},
                        {"address": "A2:F%d" % ROWS, "highlight_when": '=AND($C2<>"",COUNTIF($A$2:$A$%d,$C2)=0)' % ROWS, "fill_color": "#FFF9C4"},
                        {"address": "A1:K1", "autofit_columns": True}],
            "locked": ["A1:F1", "A2:F%d" % ROWS, "H1:I3", "K1", "K3"],
            "from_context": {"K2": "frigitd_tab"},
            "notes": "Every cell is a formula. K2 is the export's tab, filled by the pane from the step's context (K3 strips a note after the name); rows 2 down read the export's grid in place (code, description, budget, spent, committed from its columns A, C, D, E, F, from its row 4), so nothing is copied by hand. C names the account each row rolls up to: an account (numeric code) is itself; an expense code takes the account of its longest matching prefix in the table built into the formula from General Accounting's expense code list and the chart of accounts, '?' when both lack it. I1 rows, asserted at least 1; I2 codes the chart lacks, asserted 0; I3 codes rolling up to an account the award has no line for. A row turns light yellow when its code is either of the last two."}
out = os.path.join(here, "template.json")
json.dump(template, open(out, "w"), indent=0)
print("wrote", out, len(v), "rows;", len(target), "active expense codes (%d from the booklet, %d by rule) reproduced by" % (len(target) - len(unlisted), len(unlisted)), len(ordered), "prefixes inside the formula")
