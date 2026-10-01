---
name: policy-check
version: 0.5.0
category: review
domain: research-administration
status: experimental
tags: [compliance, university-of-idaho, policy, apm, fsh, review]
audience: [research-administrators]
owner: nlayman
created: 2026-10-01
updated: 2026-10-01
---

# Check a Passage Against University of Idaho Policy — Prompt

> **Purpose:** Check a passage of a document against University of Idaho policy (the APM and the FSH) and the university's F&A and fringe rates, as fetched from the university's own pages and rate documents, and report a finding for each sentence that disagrees with it. Report only: where a finding is put is the client's.
> **Expected input:** A passage of text, however the client supplies it.
> **Expected output:** The findings in the reply, each with its verdict, the sentence, one quoted clause with its link, and a fix; then a short closing.

---

## Prompt

Check the passage you were given against University of Idaho policy, the Administrative Procedures Manual (APM) and the Faculty Staff Handbook (FSH), as fetched from the university's policy pages. If there is no passage, ask for one. You report; you change no text.

Everything you say a policy requires comes from text you fetched in this turn, in the findings and in the closing alike. Never cite a policy, quote a clause or say what governs a sentence unless you fetched it. A sentence you found no policy for, or whose policy you could not fetch, is not checked: it draws no finding, and you say it was not checked.

1. **Find the policies, once.** `uidaho_guidance_index` with `chapter` lists each policy of a chapter with what it covers ("APM 45" is sponsored projects, "FSH 5" is research policy; with no chapter it lists the chapters). For each sentence of the passage that asserts something checkable (a rate, an effort, a cost, a title, a period), choose from the index the policy whose coverage fits it.
2. **Read once.** Read those policies with `uidaho_guidance_get`, and the rate documents of step 3 when a sentence states a rate, all in one round of calls. A long policy comes back in pages; read on only until the part that governs the sentence is in hand. Read only what a sentence needs: a policy that no sentence touches is not read.
3. **Rates.** When a sentence states an F&A (indirect) rate, its base, or a fringe rate, read the figure with `uidaho_rates` (`fa` for the rate agreement, `fringe` for the fringe rates by fiscal year). Which rate applies depends on the project's type and location, or the employee's class and the fiscal year. A figure the document gives for any of them is not a finding unless the passage itself names a type, location, class or year that the document gives a different figure for; a figure the document gives for none of them is unclear, since a sponsor's limit or an approved reduction was not read.
4. **Before you report**, go through the sentences that assert something. If one has no fetched policy or rate document behind it and the index lists a policy whose coverage could fit it, read that policy now. Only a sentence the index offers nothing for, or that a limit on calls cut off, is left not checked. When each sentence's rule is in hand, stop reading and report.
5. **Judge.** A sentence draws a finding only when it disagrees with the fetched policy or rate document:
   - **violates**: it states or budgets something the fetched text forbids.
   - **unclear**: the fetched text allows it only on a condition, or requires something, that the passage does not show; name what is missing. A sentence that says less than the clause requires is unclear, not a violation.

   A sentence with no finding is not mentioned, in the findings or in the closing: never write that one complies, conforms or is consistent. Two sentences of the passage that disagree with each other are not this check's to report.
6. **Report** one finding per sentence, in these lines:

   ```
   violates. APM <policy number> <paragraph label>
   Statement: "<the sentence's words, copied exactly>"
   University of Idaho: "<one clause, copied word for word from the fetched text>" <the url of that policy>
   Fix: <one plain sentence saying what to change or what to add>
   ```

   The pinpoint is the manual, the policy's number and the label of the paragraph quoted, as the policy writes them (an APM number has a dot, an FSH number has four digits; a label looks like D-4). For a rate it is the document and the place in it, `F&A rate agreement, Section I` or `Fringe rates, FY<year>`; the clause is the document's own line for that rate, and the link is the `url` the tool returned.
7. **Close** in a few lines: the policies read, each with its "Last updated" date; the rate documents read, each with its date or fiscal year; each sentence not checked, by its own words and nothing more ("not checked: the sentence on ..."), with no policy number and no word on what governs it; and that federal regulation and sponsor terms were not read.
