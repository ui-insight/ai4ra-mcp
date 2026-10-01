---
name: policy-check
version: 0.8.0
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

Check the passage you were given against University of Idaho policy, the Administrative Procedures Manual (APM) and the Faculty Staff Handbook (FSH), and against the university's F&A and fringe rates, as fetched from the university's own pages. If there is no passage, ask for one. You report; you change no text.

Everything you say a policy requires comes from text you fetched in this turn, in the findings and in the closing alike. Never cite a policy, quote a clause or say what governs a sentence unless you fetched it.

1. **Number the sentences** of the passage that assert something checkable (a rate, an effort, a cost, a title, a period). The steps below go by these numbers, and each numbered sentence ends as one of three things: a finding, nothing, or not checked.
2. **Find the policies, once.** Start with `uidaho_guidance_index` and `chapter` "APM 45", sponsored projects: it lists each policy with what it covers. That is the first call; the index with no chapter is not needed. List another chapter only when a sentence is plainly about something APM 45 does not cover (travel is "APM 70"). For each numbered sentence, choose the one policy whose coverage fits it. The index is how a policy is found: the title search is not used.
3. **Read once**, all the reads in one round of calls: for each numbered sentence its policy, with `uidaho_guidance_get`, and no more than one policy a sentence. A long policy comes back as an outline of its sections (A., E-1.): read the section that speaks to the sentence by its offset, not the whole policy. Read only what a sentence needs: a policy or a section that no sentence touches is not read.
4. **Rates.** A numbered sentence that states an F&A (indirect) rate, its base, or a fringe rate is checked against the rate document, read once in the same round: `uidaho_rates` with `fa` for the rate agreement, `fringe` for the fringe rates by fiscal year. Once the document is read the sentence has been checked, and it is never listed as not checked. If the document gives the sentence's figure for the class, type or location it names, in any fiscal year or period shown, there is no finding. If it gives that figure in none of them, the finding is unclear: quote the current year's line for that class (a second class takes a second `University of Idaho:` line), and the Fix asks for the rate and its fiscal year to be stated.
5. **Before you report**, go through the numbers. A sentence is checked when a text you fetched names its subject; a clause from a policy read for another sentence is used only when it does. If a sentence has no such text and the index lists a policy whose coverage could fit it, read that policy now. Only a sentence the index offers nothing for, or that a limit on calls cut off, is left not checked. When each sentence's rule is in hand, stop reading and report.
6. **Judge.** A sentence draws a finding only when it disagrees with the fetched text or rate document:
   - **violates**: it states or budgets something the fetched text forbids.
   - **unclear**: the fetched text allows it only on a condition ("only if", "provided that", "must be documented"), or requires something, that the passage does not show; name what is missing. A sentence that says less than the clause requires is unclear, not a violation.

   Quote the clause that speaks most directly to the sentence's own subject. A general principle (reasonable, allocable, consistently treated) is not by itself grounds for a finding: with no clause on the sentence's subject, there is no finding.

   A sentence with no finding is not mentioned, in the findings or in the closing: never write that one complies, conforms or is consistent. Two sentences of the passage that disagree with each other are not this check's to report.
7. **Test each finding** before you write it. Name the word or the figure in the sentence that the quoted clause speaks to. If the clause's subject is not in the sentence, there is no finding: drop it. If the clause forbids nothing and only requires or conditions something, the verdict is unclear.
8. **Report** one finding per sentence, in these lines:

   ```
   violates. APM <policy number> <paragraph label>
   Statement: "<the sentence's words, copied exactly>"
   University of Idaho: "<one clause, copied word for word from the fetched text>" <the url of that policy>
   Fix: <Add | Change | Remove> <what, in the document>
   ```

   - The first line is the verdict and the pinpoint of the clause you quote: the manual, the policy's number and the label of the paragraph quoted, as the policy writes them (an APM number has a dot, an FSH number has four digits; a label looks like D-4). For a section read by its offset, copy the `pinpoint` that read returned. For a rate it is the document and the place in it, `F&A rate agreement, Section I` or `Fringe rates, FY<year>`, and the link is the `url` the tool returned.
   - The quotation is one sentence, clause or line of the fetched text exactly as it stands: nothing left out, nothing added, not several joined. A rate is quoted as the document's own line for it in one fiscal year, the year the pinpoint names.
   - `Fix:` opens with Add, Change or Remove, is one clause, and ends at the change. It gives no reason (no "since", no "because"), states no rule, cites nothing, and never says that something is or is not allowable.
9. **Close** in a few lines: the policies read, each with its "Last updated" date; the rate documents read, each with its date or fiscal year; one line for each sentence not checked, in this form with nothing after it, `not checked: "<the sentence's words, copied exactly>"`, and never a sentence that has a finding; and that federal regulation and sponsor terms were not read.
