---
name: udm-conversion-guide
version: 0.2.0
category: guide
domain: research-administration
status: experimental
tags: [udm, unified-data-model, conversion, crosswalk, mapping, guide]
audience: [research-administrators, data-stewards, analysts]
owner: nlayman
created: 2026-09-29
updated: 2026-09-30
---

# UDM Conversion — Guide

> **Purpose:** How records are converted to one table of the AI4RA Unified Data Model: look at the data, say what one row is, fetch the table, decide each column's one operation, conform the values, fill provenance, ask once, report. Names no client: where the result goes is the caller's.
> **Expected input:** A set of records with a header row, and the udm server's schema tools.
> **Expected output:** The decisions laid out once for the person, then the converted records, one per source record, in the table's column order, with a report of the mapping and the gaps.

---

## Prompt

You are converting a set of records, one row per thing, into one table of the Unified Data Model (UDM), the vendor-neutral schema for research-administration data. The schema is the authority on the shape: which table, which columns, in what order, with what types and vocabularies. You are the authority on what the records mean: you read the headers and the values, and you decide what each column of the source is. The schema's synonyms are examples of what a column has been called elsewhere, not a closed list; an institution's names for things are its own, and the values in the rows tell you more than the header does.

## 1. Look at the data first

Before touching the schema, know the records: the header row; how many rows; a sample of twenty or so; for each column, what the values look like (identifiers, names, dates, amounts, a short vocabulary of a few repeated values, free text, blanks). Note which column is unique per row (the record's own identifier), which columns repeat the same few values (a status, a type, a yes/no), which hold dates in what format, which hold amounts, and which name a related thing (a sponsor, a person, a department) rather than the record itself.

Then say what one row is. One row is one award, one person, one subaward, one transaction, one proposal. That is the table. A sheet often carries columns of several tables (an award list with its PI's name and its sponsor's name); it is still one table, the one the row is, and the other columns are that table's references to the others.

## 2. Fetch the schema, then the table

`udm_index` gives the version, the modules and the tables with a line each. Choose the table the row is. Then `udm_schema` with that table's name gives its columns in the spec's order, each with its type, whether it is required, whether it is the primary key, what it references, its allowed values, its description and its synonyms; then the audit columns every table carries; then the cross-row constraints on it. When the table is not obvious, `udm_schema` with a section name (`core_module_membership`, `universal_patterns`, `semantic_conventions`) explains the model's organizing ideas.

## 3. Map each source column

Unknown data meeting a standard needs a small set of operations, and every column gets exactly one. Name it.

- **Rename.** The same thing under another name; the column moves across as it is. Most columns.
- **Split.** One source column holds what the table keeps in several: "Doe, Jane" into `Last_Name` and `First_Name`; "Moscow, ID 83844" into city, state and postal code. **Extract** is the same operation taking one part and leaving the rest: the year out of a code, the number out of "Award 2025-1234".
- **Combine.** Several source columns hold what the table keeps in one: a first and a last name into a full name; a fiscal year and a period into a date. **Coalesce** is the same operation choosing the first filled of several: a preferred name else a legal name.
- **Transform.** The value changes form and nothing else: a text date to ISO, "Y" to true, "$1,200.00" to 1200, a percentage from 0.55 to 55.00 or back as the column's type says, months to years, upper case to the vocabulary's case, whitespace trimmed, a code to the label it stands for or a label to its code. **Recode** is the transform over a vocabulary: each distinct source value to the allowed value that means the same. **Blank** is the transform for a sentinel: "N/A", "-", "TBD", "NULL", "?" and a zero that means unknown become empty.
- **Default.** A column whose value is the same on every row and comes from what the data is, not from a source column: `Lifecycle_Stage` on a budget export is "Actual" because the export is actuals; `Source_System` is the system's name; `Is_Active` is true.
- **Derive.** A column computed from other columns of the same row only: an end date from a start and a duration; a total from its parts; a fiscal year from a date. Say the rule; never derive from anything outside the row.
- **Resolve.** A reference column the source fills with a name where the table wants an identifier: when the workbook or the client holds the referenced table (an Organization sheet with its IDs), look the identifier up; when it does not, keep the name as text in the reference column and flag it as unresolved.
- **Route.** Which target column a value goes to depends on another column: the two-way attachment fills `Award_ID` or `Subaward_ID` by the row's type; a sponsor lands in `Sponsor_Organization_ID` or `Prime_Sponsor_Organization_ID` by whether the award is flow-through.
- **Generate.** A key the source lacks, one per row, in a stated form.
- **Drop.** A source column with no home in this table: another table's, or nothing in the model. Named in the report, never silently.
- **Keep, flagged.** A column you cannot settle keeps its source value in the likeliest target and is marked as a guess, so that nothing is lost and the person decides.

For each source column decide the UDM column it feeds, or that it feeds none, from four things together: the column's name, its listed synonyms, its description, and what the source values look like. The description and the values outrank the synonyms. Some patterns:

- **The key.** The table's `<Table>_ID` is the record's own identifier. Take the source's unique identifier column for it, whatever it is called (a grant code, an employee number, a project string). When the source has no unique identifier, generate one per row (`AWA-00001`) and say so.
- **Numbers the sponsor gives versus numbers the institution gives.** The UDM keeps them apart (`Award_Number` from the sponsor; `Internal_Award_Number` from the institution's own system). Read the values: a sponsor's award number looks like the sponsor's format; an internal number looks like the ERP's.
- **References.** Foreign keys are named by role (`Sponsor_Organization_ID`, `Current_PI_Personnel_ID`, `Administering_Organization_ID`) and hold identifiers. When the source has the related thing's name and not its identifier, put the name in the reference column as text and flag it: the identifier is supplied later, when the referenced table exists.
- **Original versus current.** Where the table has both (`Original_End_Date`, `Current_End_Date`; `Original_Total_Funded`, `Current_Total_Funded`), a source column called just "End Date" or "Amount" is ambiguous. Look for a second column that settles it (an "Original" or a "Revised" beside it); otherwise the current value is the safer guess and the choice is a question for the person.
- **Lifecycle tables.** Some tables carry a record through stages with a `Lifecycle_Stage` column (Budget, Effort, CostShare, Payment). The stage is a column you fill from what the source is (a proposed budget, an actual), not a column the source has.
- **Two-way attachment.** Some tables attach to either an Award or a Subaward through two columns of which exactly one is filled. Fill the one the source is about.
- **Columns the source lacks.** They exist in the output, empty. A required one that is empty is a gap to name.
- **Columns the source has that the table lacks.** They belong to another table (the PI's email is Personnel's) or to nothing in the model. Leave them out and name them with the table each belongs to; a second conversion writes that table.

## What this conversion never does

The output has exactly one row per source row, in the source's order. The conversion never filters, deduplicates, aggregates, sorts, pivots, unpivots or splits rows, and a cell holding several values ("Smith; Jones") stays one cell in one row, flagged. When the source's grain is not the table's (one row per award per year for the Award table), the table is wrong, not the rows: choose the table whose grain the rows have (a Budget period, an Effort stage), or say the data needs a reshape first and stop. When it has the table, the row count before and after is the check that the conversion did what it claims.

## 4. Conform the values

- **Dates** as ISO `YYYY-MM-DD`, whatever the source format (text in any common format, a spreadsheet serial number, a datetime).
- **Booleans** as true or false, from yes/no, Y/N, TRUE/FALSE, 1/0, X/blank; a column named `Is_...` or `Requires_...` or `Subject_To_...` is one.
- **Vocabularies.** A column with `allowed_values` takes exactly those values. Map each distinct source value to the allowed value that means the same thing ("Closed-Out" is `Closed`; "Ended" is `Closed` or `Terminated` depending on why, which the person knows). A source value that means none of them keeps its text and is flagged; do not force it. A column whose vocabulary is institution-specific by design (a `_Value_ID` column pointing at AllowedValues) takes the source's own code.
- **Amounts** as numbers, no currency symbols or thousands separators. **Percents** as the spec's type says (a percentage like 55.00, not a fraction, unless the column's description says otherwise).
- **Text** trimmed. Names split when the table wants them split (`First_Name`, `Last_Name` from "Last, First" or "First Last"; say which form you saw).
- **Blanks** stay blank. Never invent a value.

## 5. Provenance

Every table carries the audit columns. Fill `Source_System` with the name of the system the records came from (the person's word for it, else the file or sheet name), `Source_Record_ID` with the source row's own identifier or its row number, and `Is_Active` with true. Leave `Created_At`, `Updated_At` and the `_By_Personnel_ID` columns empty unless the source has them.

## 6. Ask once, then convert

Lay the decisions out before converting, in one message: the table and the schema version; one line per source column, the UDM column it feeds or that it is left out and why, and any transform; the vocabulary pairs; the key; the required columns that will be empty. Then at most three questions, only for what the data does not settle (which of two identifiers is the key; original or current; what a status value means). Ask nothing the data answers. When the person has answered, or said not to ask, convert.

## 7. The output

One row per source row. The columns are every column of the table in the spec's order, then the audit columns in the spec's order, whether or not the source fills them. Say where the output went, then report: the mapping as `source column → UDM column` with its transform; the required columns left empty; the source columns left out and the table each belongs to; the vocabulary values that kept their source text. Facts only.
