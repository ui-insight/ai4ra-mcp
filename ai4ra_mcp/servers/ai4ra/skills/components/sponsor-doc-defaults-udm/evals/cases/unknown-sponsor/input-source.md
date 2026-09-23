# Input source

The input in `input.md` uses a fabricated sponsor name designed to fall outside the model's default knowledge base. The sponsor does not exist; no policy document grounds a requirement set for it.

The purpose of this case is to verify that the component emits `document_requirements: []` with an explanatory `knowledge_notes` string rather than hallucinating a default list. This is a regression guard — the failure mode it protects against is a future prompt change that makes the component over-eager with unfamiliar sponsors.

No sensitive or identifying content is present.
