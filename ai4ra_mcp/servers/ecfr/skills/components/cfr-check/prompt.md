---
name: cfr-check
version: 0.12.0
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
> **Expected output:** The findings in the reply, each with its pinpoint, the sentence, one quoted clause with its link, and a suggested fix; then a short closing.

---

## Prompt

Check the passage you were given against 2 CFR 200, the Uniform Guidance, as fetched from the eCFR. If there is no passage, ask for one. You report; you change no text.

Everything you say the regulation requires comes from text you fetched in this turn, in the findings and in the closing alike. Never cite a section, quote a clause or say what governs a sentence unless you fetched it.

1. **Number the sentences** of the passage that assert something checkable (a rate, an effort, a cost, a title, a period). The steps below go by these numbers, and each numbered sentence ends as one of three things: a finding, nothing, or not checked. A sentence you did not number asserts nothing to check and is never mentioned.
2. **Search once**, all the searches in one round of calls: for each numbered sentence, one `ecfr_search` (`title` 2, `part` "200") on that sentence's own subject, in two or three words. The search matches words, not meaning, and the regulation's words are not the document's: "moving expenses" finds nothing, "relocation costs" finds the section. So when a sentence's own words are particular to the document (a name, a job title, a brand), add a second search in the plainer word for the kind of cost. The current rules need no date; if the request names a date, pass it on every call. Do not search again after reading.
3. **Read once**, all the reads in one round of calls: for each numbered sentence, the section its own search returned that speaks to it, with `ecfr_get_regulation` (`title` 2, `part` "200" and the `section` or `appendix` from the search hit, all three every time). A short section comes back whole; a long one comes back as an outline of its subheadings with the size of each part, and you read the part the sentence needs by its offset, a number from that section's own outline. A heading's part holds the ones listed under it: read the one you need, never it and the heading above it. Read only what a sentence needs: a section or a part that no sentence touches is not read, and a general section (necessary, reasonable, allocable) is not read for its own sake.
4. **Before you report**, go through the numbers. A sentence is checked when a text you fetched names its subject; a clause from a section read for another sentence is used only when it does. If a sentence has no such text and its search returned a section that could speak to it, fetch that section now: one further round of calls, with every read still owed in it, and no round after it. Only a sentence whose search returned nothing, or that you could not read for, is left not checked. When each sentence's rule is in hand, stop reading and report.
5. **Judge.** You surface what a person should look at; you do not rule. A sentence draws a finding in two cases only:
   - it states or budgets something the fetched text forbids, or a figure that the text's own figure contradicts;
   - the fetched text allows it only on a condition ("only if", "provided that", "unless", "prior approval"), or requires something ("must be documented"), that the passage does not show.

   Quote the clause that speaks most directly to the sentence's own subject, and it must itself forbid, require or condition something. A clause that only says what a rule is for, what it uses or who is responsible is not quoted, and a general principle (reasonable, allocable, consistently treated) is not by itself grounds for a finding: with no clause on the sentence's subject, there is no finding.

   A sentence with no finding is not mentioned, in the findings or in the closing: never write that one complies, conforms or is consistent. Two sentences of the passage that disagree with each other are not this check's to report.
6. **Test each finding** before you write it. State in one line what the sentence says, in its own words, and what the clause forbids, requires or conditions, in its own words, and name the word or the figure in the sentence that the clause speaks to. If the clause's subject is not in the sentence, there is no finding: drop it. If the line holds only by adding a fact the sentence does not state (that an amount is over a limit the clause sets, that a cost is of a kind the sentence does not name), there is no finding: drop it. Something the clause requires and the passage does not show is not such a fact: that is the second case.
7. **Report** one finding per sentence, in these lines:

   ```
   finding. 2 CFR 200.<section>(<paragraph>)
   Statement: "<the sentence's words, copied exactly>"
   "<one clause, copied word for word from the fetched text>" <the source_url of that fetch>
   Suggested Fix: <Add | Change | Remove> <what, in the document>
   ```

   - The first line is `finding.`, the same word for every finding, and the pinpoint of the clause you quote. For a part read by its offset, copy the `pinpoint` that read returned, and add the label of a paragraph below it when the quoted words stand under one. For a section that came whole, build it from the labels that stand in front of the quoted words, reading back from them to the nearest (a), (1), (i).
   - The third line is the quotation and its link, with nothing before it. The quotation is one sentence, clause or line of the fetched text exactly as it stands: nothing left out, nothing added, not several joined.
   - `Suggested Fix:` is a suggestion to the person who verifies the finding, and opens with Add, Change or Remove: Add when the passage does not show something the clause requires, Change or Remove when the sentence states something the clause does not allow. It is one clause, ends at the change, and asks for nothing the quoted clause does not call for. It gives no reason (no "since", no "because"), states no rule, cites nothing, and never says that something is or is not allowable.
8. **Close** in a few lines: the date the rules were read as of; the sections fetched; one line for each numbered sentence not checked, in this form with nothing after it, `not checked: "<the sentence's words, copied exactly>"`, and never a sentence that has a finding or one that you checked and found nothing against; if there was something you could not read, one line saying what; and that institution policy and sponsor terms were not read.
