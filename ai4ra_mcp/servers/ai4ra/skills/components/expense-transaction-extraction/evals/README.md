# Evals — expense-transaction-extraction

Each case lives under `cases/<case-slug>/` with at minimum `metadata.yaml`, `input-source.md`, `expected.json`, and optional `notes.md`. Run artifacts go under `runs/` (gitignored).

## Planned cases

- **Itemized travel receipt** — exercises `transaction_date`, `vendor`, `amount`, and an `expense_category_hint` of "Travel".
- **Vendor invoice with PO reference** — exercises `invoice_reference`, `gl_account`, and `cost_code`.
- **GL detail line with no receipt** — exercises an empty `documentation_on_hand` array.

## `validated_against_version`

Every case must declare the component version that its `expected.json` was validated against.
