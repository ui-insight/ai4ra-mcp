# UIdaho Rates

Fetches the University of Idaho's current F&A and fringe rates from the rate agreement and the fringe-rate page with `uidaho_rates` and reports them in the Rates contract's order, each with its effective period, its document and the address it was read from: seven labelled items (Location, F&A rate, F&A base, Fringe faculty, Fringe staff, Fringe students, Fringe temporary), the reference rates, and one Source line of provenance, so a client that lays them down keeps the contract a budget form reads. Writing them onto a sheet is a client's job; Idaho's mindrouter-365-aware server holds that skill.

**Version:** 0.4.1 · **Category:** research · **Status:** experimental · **Output:** the reply

## Inputs

The project's location (on-campus unless told otherwise) and type (organized research unless told otherwise).

## Outputs

The figures in the reply, each as a fraction with its effective period, its document and the address it was read from, in the Rates contract's order, then the reference rates and the Source line.

## No figures from memory

The skill reports only what the tools returned. If the rate agreement or the fringe page cannot be read, its rates are reported as not fetched and the reply says which document failed and why. Nothing is estimated and no earlier year's figure stands in.

## Why a contract

A budget form reads its rates by fixed labels, whichever institution supplied them; `nsf-budget-guide` on the `ai4ra` server carries that Rates contract. This skill is the Idaho half of it. Another institution writes its own rates skill to the same labels.

## Evals

See [`evals/`](evals/). None yet.
