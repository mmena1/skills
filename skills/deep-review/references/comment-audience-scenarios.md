# Comment Audience Scenarios

Use when changing audience routing or tone instructions. These synthetic review inputs exercise wording only; they are not evidence from a real PR or an execution of the scout/validator pipeline. The examples below were drafted and assessed by the implementing coordinator for issues #94 and #146 using the publication instructions and selected tone guide. They were not posted. This is a bounded wording check, not a model benchmark or proof of GitHub publication behavior.

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

## Outcome precision: fix-now

These cases check `audience: agent` wording only. For each input, three agent drafts contrast a vague goal, an over-prescriptive fix, and an outcome-oriented comment. Only the outcome-oriented draft is a target. Judge the drafts on whether they keep the failure, consequence, certainty, required outcome, material correctness constraints, and evidence-backed verification, and on whether they leave solution design, internal abstractions, and test implementation to the implementing agent unless the evidence or a genuine boundary requires otherwise.

### Several implementation strategies are acceptable

Input: high severity, distinct overlap. `ImportJob.run()` calls `readAllRows()`, which holds the whole CSV in memory, so a file near the documented 2 GB limit exhausts the configured heap. The confirmed recommendation requires importing without retaining the whole file, preserving row order and per-row error reporting. Streaming and fixed-size batching would both satisfy it, and the evidence does not choose. Existing ordering and error-report scenarios apply, and a file at the documented limit is the failing scenario.

Vague draft:

> `ImportJob` uses too much memory. Please make it more efficient.

Over-prescriptive draft:

> Replace `readAllRows()` with a new `RowStreamer` class wrapping a `BufferedReader` with an 8192-character buffer, inject it through `ImportJob`'s constructor, and add a Mockito test for `RowStreamer`.

Outcome-oriented draft:

> `ImportJob.run()` loads the whole file through `readAllRows()`, so an import near the documented 2 GB limit exhausts the configured heap. Import without retaining the whole file, keeping row order and per-row error reporting unchanged; streaming or fixed-size batches are both acceptable. Verify that a file at the documented limit imports under the configured heap and that the existing ordering and error-report scenarios still pass.

Assessment: the vague draft names no failure, outcome, or constraint, so a literal edit could leave the heap exhaustion in place. The over-prescriptive draft mandates a class, a buffer size, a wiring choice, and a test technique the evidence never established. The outcome-oriented draft keeps the failure, the success condition, and the ordering and error-reporting constraints, names the two acceptable strategies as illustrations, and leaves the design and the tests to the implementing agent.

### A real API boundary must be retained

Input: high severity, distinct overlap. To let `PluginHost` hooks record audit events, the PR makes `AuditTrail` public. That exposes its write path to every plugin and breaks the documented rule that only types exported from `audit-api` are public. The confirmed recommendation requires hooks to record events through the exported `AuditSink` while `AuditTrail` stays internal. How `PluginHost` obtains the sink is not established. Existing `ApiSurfaceTest` and the plugin audit scenario apply.

Vague draft:

> Making `AuditTrail` public is a problem. Please find a better way.

Over-prescriptive draft:

> Revert the visibility change, create an `AuditFacade` with a `record()` method, pass it into `PluginHost` as a constructor argument, and cover it with new mocks.

Outcome-oriented draft:

> Making `AuditTrail` public exposes its write path to every plugin and breaks the rule that only `audit-api` exports are public. Hooks must record events through the exported `AuditSink`, and `AuditTrail` must stay internal; that boundary is required. How `PluginHost` obtains the sink is open. Verify that plugins can still record audit events and that `ApiSurfaceTest` still passes.

Assessment: the vague draft gives no outcome or boundary. The over-prescriptive draft invents a facade, a wiring shape, and a test approach the finding does not support, and it never states the exported seam that actually matters. The outcome-oriented draft retains the boundary as a requirement, because correctness depends on it, and leaves everything the boundary does not decide to the implementing agent.

## Verification record

The coordinator assessed all four pairs against the criteria above: human voice preserved, useful agent wording differences, and retained outcomes, constraints, applicable verification expectations, and certainty. Omitted audience routing uses the human guide; explicit human follows the same guide. Those selection paths and the shared policy clauses are checked mechanically by `scripts/check.py`, including mutation checks that reject removed routes and safeguards. The eight drafts above assess language, independently of those deterministic results; no exact-text assertions apply to generated wording.

For issue #146 the coordinator also drafted the two outcome precision cases with the revised agent guide and assessed each outcome-oriented draft against the same criteria. Both retain the observed failure, consequence, certainty, required outcome, material correctness constraints, and the evidence-backed verification, and neither mandates a class, wiring, or test technique the input did not establish. The existing `fix-now` agent draft above already follows this pattern: it fixes the three outcomes and forbids false success without choosing an implementation. Because the same coordinator wrote the guide and the drafts, a repeat check by a separate drafting pass remains the stronger test.
