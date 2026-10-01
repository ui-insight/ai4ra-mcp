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

## [0.4.0] — 2026-10-01

- Before reporting, a sentence that asserts something and has no fetched section behind it gets the section its search returned, fetched then (#20, item 2 as revised). In the second run the search had returned 200.413 for a sentence on an administrative assistant's effort; only 200.430 and 200.431 were read and the sentence was listed as not checked, one fetch away. Not checked is now only a sentence whose search returned nothing, or that a limit on calls cut off.

## [0.5.0] — 2026-10-01

From the first two-source run (#21).

- A finding quotes the clause that speaks most directly to the sentence's own subject, and a general principle alone is not grounds for one.
- unclear names its cue: a clause that allows something "only if" or "provided that", with the passage silent on the condition. The run had called such a sentence a violation.
- Before reporting, a sentence counts as checked when any fetched text speaks to it, whichever sentence it was fetched for; and a sentence that has a finding is never listed as not checked.

## [0.6.0] — 2026-10-01

From the run after 0.5.0 (#22).

- `Fix:` says only what to change in the document, in terms of the clause quoted; it states no rule and never says something is or is not allowable. It was the one line of a finding nothing tested, and it carried a claim no fetched text made.
- A step before the report: name the word or figure in the sentence that the quoted clause speaks to; if the clause's subject is not in the sentence, there is no finding; a clause that forbids nothing gives unclear.
- The quotation is one sentence or clause exactly as it stands, nothing left out and nothing joined: a finding was withheld for a dropped phrase.
- No second search after reading, and no general section read for its own sake. A long section now comes back as an outline (the server's threshold is 12,000), so 200.431 is read by its part.
- A not-checked line has nothing after the sentence's words, no reason.
