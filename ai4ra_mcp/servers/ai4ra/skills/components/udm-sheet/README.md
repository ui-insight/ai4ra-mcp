# UDM Sheet

Converts a sheet of research-administration records (an award list, a personnel export, a subaward register) into a new sheet laid out as one table of the AI4RA Unified Data Model. The udm server holds the two things the job needs, the schema (`udm_index`, `udm_schema`) and the conversion guide (`udm_guide`); this skill is the workbook side: read the records, follow the guide, ask once, write the sheet.

**Version:** 0.2.0 · **Category:** data · **Status:** experimental · **Output:** a sheet named `UDM <Table>`, and a reply reporting the mapping and the gaps

## Inputs

The sheet the request names, else the active sheet: a header row and records below it. Optionally the UDM table (else the model decides what one row is) and the name of the source system, recorded in `Source_System`.

## What the model decides

Four operations: rename (the same thing under another name), split (one column into several, "Doe, Jane" into last and first), combine (several into one) and transform (a text date to a date, "Y" to true, "Closed-Out" to Closed, "$1,200" to 1200). It decides each from the column's name, the schema's synonyms, the column's description and, above all, the values in the rows. The synonyms are examples, not a closed list.

## Outputs

`UDM <Table>`: every column of the table plus the seven audit columns, row 1 bold, every data cell a formula pointing at the source cell (a reference, a split, a join, a parsed date, a `SWITCH` over the vocabulary, a generated key). Required columns with no source have a light-yellow header. The reply lists the mapping with its operations, the columns left empty, the source columns left out with the table they belong to, and the vocabulary values that kept their source text.

## One question

The skill asks once: the table, one line per column with its operation, the vocabulary pairs, the key, and at most three questions for what the data does not settle. "Go" writes; a correction is applied and written. A request that says not to ask is written straight away.

## Why formulas

The model transcribes nothing. A formula per cell keeps the new sheet true to the source, lets the person audit any value by clicking it, and means a correction to the source flows through. One `write_formulas` call fills a column, so a wide table is one confirmation card per mapped column.

## Elsewhere

A client with no workbook does the same job with the udm server alone: the guide and the schema are tools, and the model writes the converted rows wherever that client puts output.

## Evals

See [`evals/`](evals/). None yet.
