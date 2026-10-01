# Changelog

Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-10-01

- First version here: the pane's `cfr-check` 0.1.1 (mindrouter-365) as a report-only skill that names no client, cut to what the check needs. The passage is whatever the client supplies; the findings go in the reply with a `Statement:` line so a client can put each one on its sentence. The current rules unless the request names a date; two verdicts, violates and unclear; the rule against citing from memory said once.

## [0.2.0] — 2026-10-01

- The work is bounded, after the first real run took 16 model calls for a four-sentence passage (#19): search once and read once, each as one round of calls; two or three words a query; read only what a sentence needs, then stop and report.
- The sample finding's pinpoint is a form (`2 CFR 200.<section>(<paragraph>)`), not a real section: the model had fetched the one named there as if it were a lead.
- A sentence with no finding is not mentioned anywhere, and "not checked" in the closing is only a sentence whose rule could not be fetched. "Conforms" and "consistent" join "complies" as words not written.
