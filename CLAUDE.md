# Working rules for this repository

**Where a thing lives is decided by two questions, and nothing else.** Decided 2026-09-30, not to be drifted from.

|                       | Needs the institution's own knowledge: no | Needs the institution's own knowledge: yes |
|-----------------------|-------------------------------------------|--------------------------------------------|
| Calls host tools: yes | 1. The base client (mindrouter-365)       | 2. The institution's mindrouter-365-aware server (Idaho's) |
| Calls host tools: no  | 4. ai4ra-mcp, a general server            | 3. ai4ra-mcp, the institution's server (`uidaho`, `lakehouse`) |

- **Host tools** are a client's document tools: read a range, write values, add a sheet, insert a paragraph, draw a chart. Anything that calls them, or names them, or assumes a screen, a card, a dialog or a picker, is in row 1 or 2 and does not live in this repository.
- **This repository is row 2 of the grid's bottom half only: cells 3 and 4.** Tools over one upstream each, and guides. A guide is facts and reference material only, never a method: the shape of a correct record, the word lists, the contract, the invariants, in terms that name no client (no host, no tool names, no cells, no fills); the order of work belongs to the placement skill that reads it, so fetching a guide is reading data, not calling a skill (decided 2026-09-30 with mindrouter-365); `tests/test_guides.py` holds every component whose category is `guide` to that. What a client does with a guide is the client's.
- **The servers tell clients apart in no way.** A client is the base pane, an institution's mindrouter-365-aware server (a client in its own right from here, since it only ever calls in), or any other MCP client. The test for any line: would it be wrong if the caller were Claude Desktop? Then it moves. Dependence runs one way: a change in a client never requires a change here.
- **Cells 3 and 4 are kept apart by "one server, one upstream, one audience"**: a general server has no institution's defaults; the institution's server hard-codes its own.
- **Log no keys.** Nothing a person sent as their credential appears in any log line (`log_no_keys` in `common/http.py`).
- **Nothing from memory.** A tool that cannot reach its upstream says so; a guide reports only what tools returned.

Interim: some row-1 skills still sit here beside the guides that replaced their judgment (the proposal sheets, udm-sheet, Gantt, ask, remove-ai-tells, proposal-workbook). Each leaves when its mindrouter-365 takeover closes (#33 to #42 there); the client-only catalog fields (`hosts`, `fold`, `template`, `assertions`, `stages`, `from_context`, `excel:` requirements) leave last (#10 here). The plan is a Claude Doc linked from the README's Status.

Other rules: work in this repository only from a conversation started here; never SSH to the deployment host (the user pulls and rebuilds); `notes/` and `admin/` stay out of git; the README is updated in the same commit as the change it describes.
