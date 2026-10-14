# Comment Audience Scenarios

Use when changing audience routing or tone instructions. These synthetic review inputs exercise wording only; they are not evidence from a real PR or an execution of the scout/validator pipeline. The examples below were drafted and assessed by the implementing coordinator for issue #94 using the publication instructions and selected tone guide. They were not posted. This is a bounded wording check, not a model benchmark or proof of GitHub publication behavior.

For a repeat check, keep each input fixed and draft once with an omitted audience, once with explicit `human`, and once with explicit `agent`. Omitted and explicit human selections should follow the same voice, without requiring identical text. Assess the drafts against the source concern and recommendation, rather than asserting exact strings. Retain drafts and the assessment; do not infer wording quality from passing deterministic checks.

For every pair below, check that the human draft sounds like a teammate's short review comment and that the agent draft makes the success condition, constraints, or needed decision easier to act on. Both must retain the same meaning, certainty, and action. Applicable verification expectations come from the input, not invented commands or tests. Shared approval, overlap, eligibility, and payload rules still come from `pr-review-comments.md` and `pr-review-overlap.md`.

## Finding: fix-now

Input: high severity, distinct overlap. `acquireDedupLock()` treats `false` as a duplicate. `setIfAbsent()` catches a Redis connection exception and returns `false`, so an undelivered message is dropped. The confirmed recommendation requires a retryable unavailable result, preserving genuine duplicate detection. Returning success on connection failure would process a message without acquiring its lock. Existing verification scenarios distinguish connection failure (retry), an existing key (duplicate), and an acquired lock (process).

Human draft:

> On a Redis connection failure, `setIfAbsent()` returns `false` and `acquireDedupLock()` drops the message as a duplicate. Return a retryable unavailable result here, keeping `false` for an existing key. Don't return success without acquiring the lock. Check that connection failures retry, existing keys still count as duplicates, and acquired locks still process.

Agent draft:

> `setIfAbsent()` maps connection failure to the duplicate result, causing `acquireDedupLock()` to drop an undelivered message. Preserve three outcomes: unavailable means retry, an existing key means duplicate, and an acquired lock means process. Return the retryable unavailable result on connection failure; do not report successful lock acquisition. Verify all three existing scenarios after repair.

Assessment: both directly request the same repair and retain the constraint against false success and the three verification outcomes. The human draft uses conversational sentences; the agent draft makes the outcome distinctions explicit without choosing an unsupported implementation.

## Finding: discuss

Input: medium severity, distinct overlap. `purgeAuditRows()` uses a seven-day cutoff. The confirmed concern is that the documented investigation window is thirty days, so seven days removes records needed for that task. The recommendation leaves a design decision: retain rows online for thirty days, or preserve queryable archived records after day seven. Either must retain the full investigation window while meeting the existing online storage budget. Verification of access across the thirty-day window applies after that decision; the evidence does not select an architecture.

Human draft:

> `purgeAuditRows()` removes rows after seven days, but investigations need thirty days of records. Should we keep them online for thirty days or archive them after day seven? Either way, can we keep the full window queryable within the online storage budget and check access across that window?

Agent draft:

> The seven-day cutoff in `purgeAuditRows()` leaves the documented thirty-day investigation window incomplete. Which remedy should govern: thirty days online, or queryable archived records after day seven? The decision needs to preserve access throughout the thirty-day window within the existing online storage budget. How should that access be verified for the selected remedy?

Assessment: both ask the same decision-complete design question and preserve the budget and full-window access constraint. The agent draft separates the choice, its constraints, and the applicable verification question. Neither orders an archive implementation or treats the unselected remedy as settled.

## Finding: follow-up

Input: medium severity, prior resolved discussion. A confirmed unbounded `TenantCache` growth concern persists despite the prior discussion at `https://example.com/reviews/cache`. The remedy spans admission and eviction across modules and belongs in a later PR. Required outcome: bound retained entries while preserving tenant isolation and cache-hit behavior. Existing tenant-isolation and cache-hit scenarios must pass; bounded-growth verification is part of the recommendation. No eviction strategy is established. This PR changes serialization only.

Human draft:

> `TenantCache` can still grow without a limit; the [earlier discussion](https://example.com/reviews/cache) doesn't resolve that here. This can go in a follow-up to the serialization PR: bound retained entries while keeping tenant isolation and cache hits working. Check bounded growth and retain the existing isolation and hit behavior.

Agent draft:

> Follow-up scope: bound retained entries in `TenantCache` across admission and eviction, preserving tenant isolation and cache-hit behavior. The growth concern remains after the [prior discussion](https://example.com/reviews/cache). Track this in a later PR; the current serialization scope can proceed. Verify bounded growth and the existing tenant-isolation and cache-hit scenarios. The evidence leaves the eviction strategy open.

Assessment: both retain the prior discussion link, the future-work scope, required outcome, constraints, and verification expectations. The agent draft makes the later work easier to scope without turning it into a current merge requirement or prescribing an eviction strategy.

## Unresolved: discuss

Input: no confirmed severity, distinct overlap, explicitly selected by the user for drafting. `testPublisherFailure()` and `testInvalidRequest()` both show `ValidationError` in retained output. Static inspection did not establish whether the former reaches `publish()`. Remaining question: is publisher-exception behavior exercised independently? The needed evidence is an invocation trace or equivalent proof of reachability; there is no supported removal recommendation.

Human draft:

> `testPublisherFailure()` and `testInvalidRequest()` both show `ValidationError`, but I couldn't establish whether the first reaches `publish()`. Can you check that it exercises publisher failure independently, with a trace or equivalent evidence?

Agent draft:

> Both `testPublisherFailure()` and `testInvalidRequest()` show `ValidationError`; reachability of `publish()` in the first test remains unestablished. What invocation trace or equivalent evidence shows whether publisher-exception behavior is exercised independently? That evidence is needed to distinguish publisher coverage from another validation path.

Assessment: both remain questions about evidence and uncertainty. The agent draft states the missing proof and why it matters. Neither asserts duplicate coverage, recommends removal, or turns suspicion into an implementation directive.

## Verification record

The coordinator assessed all four pairs against the criteria above: human voice preserved, useful agent wording differences, and retained outcomes, constraints, applicable verification expectations, and certainty. Omitted audience routing uses the human guide; explicit human follows the same guide. Those selection paths and the shared policy clauses are checked mechanically by `scripts/check.py`, including mutation checks that reject removed routes and safeguards. The eight drafts above assess language, independently of those deterministic results; no exact-text assertions apply to generated wording.
