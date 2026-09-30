# UIdaho Rates

Fetches the University of Idaho's current F&A and fringe rates from the rate agreement and the fringe-rate page with `uidaho_rates` and reports them in the Rates contract's order, each with its effective period, its document and the address it was read from: seven labelled items (Location, F&A rate, F&A base, Fringe faculty, Fringe staff, Fringe students, Fringe temporary), the reference rates, and one Source line of provenance, so a client that lays them down keeps the contract a budget form reads. Writing them onto a sheet is a client's job; Idaho's mindrouter-365-aware server holds that skill.

**Version:** 0.4.0 · **Category:** research · **Status:** experimental · **Output:** the reply

## Inputs

The project's location (on-campus unless told otherwise) and type (organized research unless told otherwise); optionally a sheet name.

## Outputs

The figures with their dates and addresses in the reply; the Rates sheet as well when a sheet is named (the proposal workbook's Rates step names one).

## No figures from memory

The skill writes only what the tools returned. If the rate agreement or the fringe page cannot be read, the rows are on the sheet with their labels and no value, the Basis cell says "not fetched", and the reply says which document failed and why. Nothing is estimated and no earlier year's figure stands in.

## Why a sheet

The budget form skills are institution-agnostic: they read their rates from a Rates sheet when the workbook has one and write its Source line beside the rates as provenance. This skill is the Idaho half of that contract. Another institution writes its own rates skill to the same labels.

## Evals

See [`evals/`](evals/). None yet.
