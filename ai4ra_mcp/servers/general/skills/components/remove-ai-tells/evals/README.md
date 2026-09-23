# Evals — remove-ai-tells

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml` (with `validated_against_version`), `input.md` (the text as supplied), and `expected.md` (the rewritten text and the report).

## Case selection

- A paragraph dense with 2023-era vocabulary (delve, tapestry, testament, pivotal): every listed word gone, facts intact.
- A "Challenges and Future Outlook" section: cut or rewritten to say something.
- Text with em dashes as commas and bold inline headers: punctuation and emphasis normalised, headings untouched.
- A clean human paragraph: unchanged, reported as clean.
- A quoted passage containing tells: left alone and reported as such.

No cases yet.
