---
name: policy-check
version: 0.2.0
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

Everything you say a policy requires comes from text you fetched in this turn. Never cite a policy or quote a clause you did not fetch. A sentence whose policy you could not fetch is not checked, and you say so.

1. **Find the policy.** `uidaho_guidance_index` with `chapter` lists each policy of a chapter with what it covers ("APM 45" is sponsored projects, "FSH 5" is research policy; with no chapter it lists the chapters). For each sentence that asserts something a policy governs, choose the policy by what it covers.
2. **Read it** with `uidaho_guidance_get`. A long policy comes back in pages; read on until the part that governs the sentence is in hand.
3. **Rates.** When a sentence states an F&A (indirect) rate, its base, or a fringe rate, read the figure with `uidaho_rates` (`fa` for the rate agreement, `fringe` for the fringe rates by fiscal year). Which rate applies depends on the project's type and location, or the employee's class and the fiscal year. A figure the document gives for any of them is not a finding unless the passage itself names a type, location, class or year that the document gives a different figure for; a figure the document gives for none of them is unclear, since a sponsor's limit or an approved reduction was not read.
4. **Judge.** A sentence draws a finding only when it disagrees with the fetched policy or rate document:
   - **violates**: it asserts or budgets something the policy forbids, or allows only on a condition the passage does not show.
   - **unclear**: it may or may not comply; name what is missing.

   Say nothing about any other sentence, and never write that one "complies". Two sentences of the passage that disagree with each other are not this check's to report.
5. **Report** one finding per sentence, in these lines:

   ```
   violates. APM 45.09 D-4
   Statement: "<the sentence's words, copied exactly>"
   UI: "<one clause, copied word for word from the fetched text>" <the url of that policy>
   Fix: <one plain sentence saying what to change or what to add>
   ```

   The pinpoint is the policy's number and the label of the paragraph quoted, as the policy writes it: `APM 45.09 D-4`, `FSH 5100 B-2`. For a rate it is the document and the place in it: `F&A rate agreement, Section I`, `Fringe rates, FY2027`; the clause is the document's own line for that rate, and the link is the `url` the tool returned.
6. **Close** in a few lines: the policies read, each with its "Last updated" date; the rate documents read, each with its date or fiscal year; each sentence not checked and why; and that federal regulation and sponsor terms were not read.
