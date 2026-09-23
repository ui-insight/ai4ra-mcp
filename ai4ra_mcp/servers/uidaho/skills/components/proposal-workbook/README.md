# Proposal Workbook

An orchestrating skill that the pane drives one stage per turn. Starting from an opportunity the user picked out of the funding-opportunity finder's list, it builds a proposal-planning workbook in four stages, in this order: the opportunity record on an RFA sheet, checked complete, with the award ceiling and any tracks, followed in the same reply by the questions only the user can answer; a Narrative sheet and an Activities table grounded in the record and the context, copy-edited by the remove-AI-tells skill; a budget from the narrative through the narrative-to-budget worksheet skill, wired back into requested funding, the narrative's budget sentence and a ceiling check by formula; and a timeline from the activities and the budget through the project-timeline (Gantt) skill.

**Version:** 5.2.0 · **Category:** drafting · **Status:** experimental · **Output:** a workbook

## How the stages are enforced

The catalog entry lists the four stages and the tools each must call. The pane serves the prompt's preamble plus the current stage only, records the tool calls the model makes, and if the model tries to end the turn without a required call, forces that call through the API. A stage ends when its tools have all run and the turn ends. A stage marked as asking (stage 1) continues by itself: the user's next message is taken as the answer and the pane calls the skill for the next stage before anything else. After the other stages the user says "next". A tool that belongs to a later stage is refused while an earlier stage is active, so the model cannot skip ahead. "stage N" in the request jumps to a stage; "restart" starts over; a new chat resets.

## Inputs

An opportunity from the finder's list (number, title or grants.gov link); in answer to stage 1, the proposal title, the idea, the award type, the team, the project length and start, and any other context. Needs the general server's `web_search` and `fetch_document`, the University of Idaho server's `uidaho_rates`, the skills its steps name (on the general, AI4RA and University of Idaho servers), and the Excel tools.

## Outputs

Sheets RFA, Narrative, Work plan, Rates, Budget outline, Budget NSF and Timeline. The Rates sheet is the University of Idaho's F&A and fringe rates with their dates; the budget form takes its rates from it and carries its Source line as provenance. Every derived number is a formula, every date a DATE formula, every assumption yellow. In Word, the same content as headed sections and tables without live numbers.

## Evals

See [`evals/`](evals/). None yet.

## Provenance

Authored 2026-09-14 for the MindRouter Office add-in, from a workbook (RFA sheet, narrative, activities, timeline, budget template) built by hand in the pane for an NSF AI-datasets opportunity. Rebuilt as a pane-driven staged skill after prompt-only orchestration proved unreliable on the models in use.
