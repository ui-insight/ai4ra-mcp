---
name: cfr-check
version: 0.4.0
category: review
domain: research-administration
status: experimental
tags: [compliance, ecfr, 2-cfr-200, uniform-guidance, review]
audience: [research-administrators]
owner: nlayman
created: 2026-10-01
updated: 2026-10-01
---

# Check a Passage Against 2 CFR 200 — Prompt

> **Purpose:** Check a passage of a document against 2 CFR 200, the Uniform Guidance, as fetched from the eCFR, and report a finding for each sentence that disagrees with it. Report only: where a finding is put is the client's.
> **Expected input:** A passage of text, however the client supplies it. A date, if the rules of an earlier day are wanted.
> **Expected output:** The findings in the reply, each with its verdict, the sentence, one quoted clause with its link, and a fix; then a short closing.

---

## Prompt

Check the passage you were given against 2 CFR 200, the Uniform Guidance, as fetched from the eCFR. If there is no passage, ask for one. You report; you change no text.

Everything you say the regulation requires comes from text you fetched in this turn, in the findings and in the closing alike. Never cite a section, quote a clause or say what governs a sentence unless you fetched it. A sentence you did not search for, or whose rule you could not fetch, is not checked: it draws no finding, and you say it was not checked.

1. **Date.** The current rules, unless the request names a date; then that date on every call. With no date the tools read the current text and report the day as `date`.
2. **Search once.** Make one search for each sentence of the passage that asserts something checkable (a rate, an effort, a cost, a title, a period), with `ecfr_search` (`title` 2, `part` "200"), all the searches in one round of calls. Two or three words a query: a section matches only when it has every word, so a long query finds nothing.
3. **Read once.** For each of those sentences, read with `ecfr_get_regulation` the section its search returned that speaks to it, all in one round of calls. A section comes back whole unless it is very long; then it comes back as an outline of its subheadings, and you read the part a sentence needs by its offset. Read only what a sentence needs: a section or a part that no sentence touches is not read.
4. **Before you report**, go through the sentences that assert something. If one has no fetched section behind it and its search returned a section that could speak to it, fetch that section now. Only a sentence whose search returned nothing, or that a limit on calls cut off, is left not checked. When each sentence's rule is in hand, stop reading and report.
5. **Judge.** A sentence draws a finding only when it disagrees with the fetched text or with another sentence of the passage:
   - **violates**: it states or budgets something the fetched text forbids.
   - **unclear**: the fetched text allows it only on a condition, or requires something, that the passage does not show; name what is missing. A sentence that says less than the clause requires is unclear, not a violation.

   A sentence with no finding is not mentioned, in the findings or in the closing: never write that one complies, conforms or is consistent.
6. **Report** one finding per sentence, in these lines:

   ```
   violates. 2 CFR 200.<section>(<paragraph>)
   Statement: "<the sentence's words, copied exactly>"
   eCFR: "<one clause, copied word for word from the fetched text>" <the source_url of that fetch>
   Fix: <one plain sentence saying what to change or what to add>
   ```

   The first line is the verdict and the pinpoint of the clause you quote, down to its paragraph. When two sentences of the passage disagree, `Conflicts with: "<the other sentence's words>"` takes the place of the `eCFR:` line.
7. **Close** in a few lines: the date the rules were read as of; the sections fetched; each sentence not checked, by its own words and nothing more ("not checked: the sentence on ..."), with no section number and no word on what governs it; and that institution policy and sponsor terms were not read.
