---
name: cfr-check
version: 0.1.0
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

Everything you say the regulation requires comes from text you fetched in this turn. Never cite a section or quote a clause you did not fetch. A sentence whose rule you could not fetch is not checked, and you say so.

1. **Date.** The current rules, unless the request names a date; then that date on every call. With no date the tools read the current text and report the day as `date`.
2. **Find and read.** For each sentence that asserts something the regulation governs, find the section with `ecfr_search` (`title` 2, `part` "200") and read it with `ecfr_get_regulation`.
3. **Judge.** A sentence draws a finding only when it disagrees with the fetched text or with another sentence of the passage:
   - **violates**: it asserts or budgets something the regulation forbids, or allows only on a condition the passage does not show.
   - **unclear**: it may or may not comply; name what is missing.

   Say nothing about any other sentence, and never write that one "complies".
4. **Report** one finding per sentence, in these lines:

   ```
   violates. 2 CFR 200.313(a)
   Statement: "<the sentence's words, copied exactly>"
   Federal: "<one clause, copied word for word from the fetched text>" <the source_url of that fetch>
   Fix: <one plain sentence saying what to change or what to add>
   ```

   When two sentences of the passage disagree, `Conflicts with: "<the other sentence's words>"` takes the place of the `Federal:` line.
5. **Close** in a few lines: the date the rules were read as of, the sections fetched, each sentence not checked and why, and that institution policy and sponsor terms were not read.
