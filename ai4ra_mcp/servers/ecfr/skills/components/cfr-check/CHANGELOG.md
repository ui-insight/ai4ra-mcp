# Changelog

Versions follow semver: MAJOR for output-contract breaks, MINOR for backward-compatible additions, PATCH for wording or clarity.

## [0.1.0] — 2026-10-01

- First version here: the pane's `cfr-check` 0.1.1 (mindrouter-365) as a report-only skill that names no client, cut to what the check needs. The passage is whatever the client supplies; the findings go in the reply with a `Statement:` line so a client can put each one on its sentence. The current rules unless the request names a date; two verdicts, violates and unclear; the rule against citing from memory said once.

## [0.2.0] — 2026-10-01

- The work is bounded, after the first real run took 16 model calls for a four-sentence passage (#19): search once and read once, each as one round of calls; two or three words a query; read only what a sentence needs, then stop and report.
- The sample finding's pinpoint is a form (`2 CFR 200.<section>(<paragraph>)`), not a real section: the model had fetched the one named there as if it were a lead.
- A sentence with no finding is not mentioned anywhere, and "not checked" in the closing is only a sentence whose rule could not be fetched. "Conforms" and "consistent" join "complies" as words not written.

## [0.3.0] — 2026-10-01

From the second real run (#20).

- The source line is labelled with the name of the server the clause was fetched from, `eCFR:`, in place of `Federal:`, so a finding reads the same in any client as in the pane. The lines of the form and their order are unchanged.
- One search for each sentence that asserts something checkable. A sentence not searched for, or whose rule was not fetched, draws no finding and is listed as not checked: the run had written a finding on one from a section it never fetched.
- The closing lists a sentence not checked by its own words only, with no section number and no word on what governs it. Nothing about the regulation is said without a fetch behind it, in the closing as in the findings.
- The two verdicts no longer overlap: violates is something the text forbids; unclear is a condition or a requirement the passage does not show.
