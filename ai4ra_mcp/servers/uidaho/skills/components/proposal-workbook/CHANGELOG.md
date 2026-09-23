# Changelog

All notable changes to this component. Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [5.2.0] — 2026-09-23

- The Rates step runs uidaho-rates with the sheet named in its context (Rates); the skill writes the sheet only because the step names one.

## [5.1.0] — 2026-09-22

- The Rates step runs uidaho-rates-sheet, which writes a Rates sheet, instead of uidaho-lookup, which answered in the reply; the Budget template step reads the Rates sheet (a source) for its rates and its provenance line. Moved to ui-insight/ai4ra-mcp as a skill of the uidaho server; its steps live on the general, AI4RA and University of Idaho servers.

## [5.0.1] — 2026-09-22

- The Gantt step's context carries each activity's description from the Work plan sheet, so the Timeline sheet's Description column holds the text and not the context's 'start, duration' line.

## [0.3.0] — 2026-09-14

- Four stages: the RFA sheet ends by asking the context questions and the user's answer continues the workflow without "next"; the pane refuses a later stage's tools while an earlier stage is active.

## [0.2.2] — 2026-09-14

- Stage 5 hands the Activities months to the simplified Gantt skill; add_gantt is gone.

## [0.2.1] — 2026-09-14

- Stage 5 stays in months and requires the add_gantt tool; estimates are welcome and marked, only people, organisations and announcement facts are never invented.

## [0.2.0] — 2026-09-14

- Rebuilt as a staged skill the pane drives: five stages in the order RFA sheet, Context, Narrative and Activities, Budget, Timeline; one stage per turn, each stage's tool calls required by the pane (forced through the API when the model tries to end the stage without them).

## [0.1.4] — 2026-09-14

- A stage ends the turn even when the user's message already supplied later stages' inputs; stages 3 and 4 call their skills once, in their own turns, and earlier stages do not create Timeline or Budget sheets.

## [0.1.3] — 2026-09-14

- Stage 0 states the tool check the pane performs and binds the model to use the required tools at their stages.

## [0.1.2] — 2026-09-14

- The Stage 1 questions end with an open invitation for context or specific things to consider, carried through every later stage.

## [0.1.1] — 2026-09-14

- Says plainly that each stage's deliverable is sheets written with the tools, that the reply is only a status, that stages 3 and 4 call the timeline and budget skills, and that a project page the user names is fetched rather than guessed.

## [0.1.0] — 2026-09-14

- Initial version: four stages (RFA sheet and questions; Narrative and Activities with a tells pass; Timeline via the Gantt skill; Budget via the budget skill, wired back by formula).
