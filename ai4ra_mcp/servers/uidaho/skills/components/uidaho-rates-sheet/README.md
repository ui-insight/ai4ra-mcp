# UIdaho Rates Sheet

Writes the University of Idaho's current F&A and fringe rates onto a sheet named Rates, read from the rate agreement and the fringe-rate page with `uidaho_rates`, one row per rate with its effective period and its document. The first seven rows carry fixed labels (Location, F&A rate, F&A base, Fringe faculty, Fringe staff, Fringe students, Fringe temporary) and the last row, Source, is one line of provenance, so a budget form skill can take its rates from the sheet and say where they came from.

**Version:** 0.1.0 · **Category:** research · **Status:** experimental · **Output:** a spreadsheet sheet

## Inputs

The project's location (on-campus unless told otherwise) and type (organized research unless told otherwise).

## Outputs

The Rates sheet, and a three-line reply with the figures and their dates.

## Why a sheet

The budget form skills are institution-agnostic: they read their rates from a Rates sheet when the workbook has one and write its Source line beside the rates as provenance. This skill is the Idaho half of that contract. Another institution writes its own rates skill to the same labels.

## Evals

See [`evals/`](evals/). None yet.
