# Remove AI Writing Tells

Edits a document or selection so it stops reading like machine output. The skill works through twenty-nine families of tells in five groups (words, sentences, structure, formatting, residue), merged from Wikipedia's editor-maintained catalogue of AI writing signs and the 2026 lists from writing and marketing editors: AI vocabulary and Latinate substitutions, puffed significance, avoided copulas, negative parallelism, the rule of three, participle openers, from-X-to-Y sweeps, personified abstractions, even rhythm, hedge stacking, formulaic openers and closers, signposting filler, the challenges formula, ghost attribution, canned notability, em dashes, emoji bullets (✅ and ❌ included), bold for emphasis, inline-header lists, heading habits, tiny tables, leaked Markdown, chatbot address, cutoff disclaimers and template leftovers. It edits in logical blocks (one paragraph per tracked change, or one sentence when that is all that changed), rewrites only the paragraphs that carry one, keeps every fact, citation and quotation, and ends with a grammar-only pass over what it touched. In Word the edits land as tracked changes; the reply summarises what was found and changed. It never says the text was machine-written.

**Version:** 1.0.0 · **Category:** transformation · **Status:** experimental · **Output:** document edits

## Inputs

In Word, the highlighted text or the whole document, read with the document tools. Elsewhere, pasted text.

## Outputs

In Word, tracked changes paragraph by paragraph and a short report: paragraphs changed, families found with one before/after example each, grammar fixes from the final pass, and what was left alone. Elsewhere, the rewritten text and the same report.

## Evals

See [`evals/`](evals/). None yet.

## Provenance

Authored 2026-09-14 for the MindRouter Office add-in. The tell families and word lists follow [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) as of September 2026, merged with the 2026 lists at [oliviacal.com](https://www.oliviacal.com/post/ai-writing-tells), [vrid.ai](https://vrid.ai/blog/signs-of-ai-writing), [yaps.ai](https://www.yaps.ai/blog/how-to-detect-ai-writing) and [explainx.ai](https://www.explainx.ai/blog/top-10-signs-ai-generated-text-2026). All of them caution that none of these signs proves machine authorship; the skill therefore edits without accusing.
