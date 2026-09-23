# Evals

Reference cases for `nsf-expense-allowability-check`.

Current cases:

- `travel-cap-overage` - synthetic NSF-2427549-style travel expense where the expense is project-related and documented, but exceeds a supplied per-person travel cap. Expected decision: `not_allowable`.

Future cases should cover:

- allowable materials/supplies purchase with complete documentation
- participant-support expense missing separate account evidence
- equipment purchase with missing prior approval or threshold ambiguity
- missing receipt or insufficient vendor detail
- indirect-cost base exclusion check
