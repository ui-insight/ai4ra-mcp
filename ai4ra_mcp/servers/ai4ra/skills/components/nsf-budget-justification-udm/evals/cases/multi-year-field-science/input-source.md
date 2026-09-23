# Input source

The structured budget in `input.md` is **synthetic**: a realistic NSF three-year budget constructed specifically for this eval. It is not drawn from any real proposal. Names, institutions, and scopes are fabricated to be illustrative rather than identifying.

The synthetic budget exercises every NSF direct-cost category (A through G) with at least one non-zero year and provides item-level detail for equipment, travel, participant support, and the subaward. Fringe rates are not encoded numerically in the input — the narrative is expected to use the "institutional rates applicable to each personnel category" fallback language per the component's quality standards.

Dollar figures are internally consistent by inspection (e.g., senior personnel totals in `budget_summary.A` track the base salaries, effort levels, and 3% escalation declared on the `personnel` entries) but precise arithmetic is not a constraint — the justification narrative's job is to explain the numbers, not to verify them.

The `indirect_cost.notes` field encodes a step change ("Rate increases from 52% to 54.5% in Year 3 per the current DHHS-negotiated rate agreement") to exercise Section H narration of rate changes across project years.

No sensitive or identifying content is present.
