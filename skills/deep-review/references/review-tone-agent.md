# Agent Review Tone Guide

Use for `audience: agent`, as selected by `pr-review-comments.md`. That reference and `pr-review-overlap.md` own the shared publication rules and take precedence. This guide shapes wording from the existing evidence and recommendation.

Write a concise, actionable comment that an implementing agent can interpret without guessing the intended result. Start with the concrete concern and its consequence, using exact identifiers. State the required outcome and every material constraint from the recommendation. Include applicable verification expectations when the existing evidence or recommendation establishes them, such as the failing scenario and the behavior that must pass after repair. Keep proposed implementation details within the inspected evidence; leave unstated choices open. Use short prose or a compact list when several constraints need separate attention; a fixed report schema adds noise.

- **`fix-now`**: directly request the required outcome. Make the success condition and material constraints explicit, including a plausible shortcut that would leave the confirmed concern unresolved. Verification describes the established behavior to check, without inventing a test command or a new acceptance criterion.
- **`discuss`**: ask a decision-complete question naming the concrete design choice or tradeoff, the known constraints, and what the author's answer needs to settle. Preserve judgment calls as questions rather than issuing implementation directives for an undecided remedy.
- **`follow-up`**: explain the future work's required outcome, scope, and reason it belongs in a later issue or PR. Use an informative, non-blocking tone; leave the current PR's scope intact.
- **Unresolved**: state the observed evidence and ask for the missing evidence or decision that would resolve the remaining uncertainty. Keep the suspected concern conditional; uncertainty never becomes an implementation directive.

Edit for interpretation: could the agent satisfy the literal request while losing an established outcome or constraint? Clarify that gap using the source recommendation, then apply the shared ambiguity check in `pr-review-comments.md`.
