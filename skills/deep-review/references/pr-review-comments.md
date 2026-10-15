# Add PR Review Comments

Use this only for a confirmed GitHub PR when the user asks to add comments.

## Audience

The user may specify `audience: human` or `audience: agent` when requesting publication. Resolve the audience before drafting approval candidates. Use the user's explicit selection; when unspecified, use `human` without an extra confirmation step. Never infer the audience from the PR author's identity.

| User selection | Audience | Tone guide |
| --- | --- | --- |
| unspecified | `human` | `review-tone.md` |
| `human` | `human` | `review-tone.md` |
| `agent` | `agent` | `review-tone-agent.md` |

Read the selected guide before drafting. Audience changes wording only: preserve outcomes (including Findings and Unresolved), evidence, severity, action classification, overlap dispositions, publication eligibility, approval requirements, and payload validation. Record the audience alongside the approval candidates in the existing run state. A later audience change requires redrafting and the same validation and per-comment approval for the changed bodies.

## Publication

1. Re-check PR state and `headRefOid` with `gh pr view --json state,mergedAt,headRefOid`, then compare `headRefOid` with the recorded reviewed head SHA. Stop if closed, merged, or changed; a stale pinned result cannot be published.
   Apply `pr-review-overlap.md` before drafting: exclude already-reported items and include prior discussion links for resolved overlaps. Publish new comments only; never reply inside, edit, or resolve an existing thread.
2. Draft inline comments only for Findings and user-selected Unresolved items. Use committed code and team-visible evidence whenever practical; private ignored context is not named or quoted without explicit approval.
3. Findings use assertive defect language supported by validator evidence. A structural Finding names the task its cost burdens and the required outcome, not a preference for a design technique. An Unresolved item is posted only after explicit per-item approval and must be a question describing observed evidence and what remains unsettled; it must not assert a defect.
   Write each comment in the selected tone guide's voice; these publication rules take precedence where they differ.
4. Keep remediation short without losing clarity. Carry the required outcome and the material constraints from the Finding's recommendation; simplify or clarify the wording, but never drop a constraint that separates an acceptable repair from a superficially valid one. Then run the ambiguity check for the comment's action before presenting it for approval:
   - `fix-now`: ask, "Could an author reasonably implement this comment literally and still leave the confirmed concern unresolved?" If yes, add the missing required outcome or constraint. When an obvious shortcut is plausible and materially wrong, rule it out explicitly. A precise outcome constraint is sufficient; do not add speculative implementation detail just to supply a code sample.
   - `discuss`, including a user-selected Unresolved item: do not require implementation-complete remediation. Require a decision-complete question: the concern or tradeoff is specific enough that the author knows which decision needs to be resolved.
   - `follow-up`: make the future work's required outcome and scope clear. Suggest an implementation only when confidently established, and do not turn the comment into a design document.

   Code samples are optional. Use one only when prose would leave meaningful ambiguity and the suggested shape is supported by inspected surrounding code. If a comment stays ambiguous, re-inspect the relevant code to establish safer wording; do not invent a confident architectural prescription the finding or surrounding code does not support.
5. For every comment, declare scope: point, method/design, or compact range. Record the smallest semantically representative source anchor and rationale.
6. Validate each payload mechanically against the current head: path, side, changed-line/range eligibility, and complete range fields. Also validate semantic representativeness. Reject mismatches rather than widening anchors.
7. If the preferred anchor is not commentable, use only the smallest relevant changed line or compact range as an explicit fallback, preserving scope and rationale. If no relevant changed location exists, do not publish inline.
8. Get per-comment approval with scope and anchor.
9. Immediately before posting, re-fetch complete PR discussion and re-check overlap under `pr-review-overlap.md`, together with PR state and head SHA. If the head changed, stop and rerun the review. Remove newly overlapping open concerns; route any changed comment body or anchor through validation and per-comment approval again, then repeat this freshness/overlap check. Submit no review when every comment is suppressed, and report that result.
10. Before submitting, record in run state the final approved and overlap-filtered payload, the pinned head SHA, the authenticated account, and the submission start time. Submit one review with an empty top-level body unless the user explicitly requests a summary:
   `gh api POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` with `event: COMMENT` and the approved `comments` array. Submit it at most once per approved payload; see "Submission outcome".
11. Validate the final payload after any coordinate change. After submission, run "Read-back verification" and update the final report and run state with the actual publication, verification, and overlap dispositions.

## Submission outcome

Record the submission outcome independently of read-back verification, with the response status, returned review ID and `commit_id`, and the request and response times.

| Outcome | Meaning |
| --- | --- |
| `submitted` | A success response returned a review ID. |
| `rejected` | A definitive error response states that no review was created. |
| `ambiguous` | Anything else: a timeout, dropped connection, server error, unreadable body, or success without a review ID. |

Never post the review or any of its comments a second time because verification failed or was incomplete, or because the outcome is `ambiguous`. A `rejected` review is reported with the response and is never replayed automatically; posting again is a new attempt that repeats step 9 and the per-comment approval for any changed payload.

For `ambiguous`, reconcile with read-only calls only. Retrieve the PR's reviews and comments completely, then take as candidates every review by the authenticated account at the pinned head SHA within the submission window, whether or not its comments match. The window runs from the recorded submission start time to the time of the reconciliation read, with a margin for clock skew between the local clock and GitHub's `submitted_at`. Accept the review only if there is exactly one candidate and it verifies against the exact approved payload under "Read-back verification". Retry a transient retrieval failure a small bounded number of times, such as three. With no candidate, several candidates, a lone candidate that does not verify, or a retrieval that stays incomplete, keep the outcome `ambiguous`, record the evidence, and stop for explicit human action. Absence from an incomplete or lagging read is not proof that nothing was published.

## Read-back verification

Verification confirms the received comments against the approved payload. It never decides whether to submit again.

1. Read comments from `gh api --paginate "/repos/{owner}/{repo}/pulls/{pull_number}/comments?per_page=100"`, the PR-wide endpoint. Do not use the review-specific comments endpoint as the source, because it can omit anchor fields. Pagination must complete; a failed page, a rate limit, or an unreadable body is a retrieval failure. Retry a transient retrieval failure with read-only calls a small bounded number of times before treating it as one.
2. Select only comments whose `pull_request_review_id` equals the returned review ID. Other reviews' and unrelated comments are never part of the receipt. Without a returned review ID, the publication cannot be identified and verification is incomplete unless reconciliation under "Submission outcome" established the review.
3. Compare each expected comment with the selected comments on `body`, `path`, `side`, `line`, and, for a range, `start_line` and `start_side`. A comment whose payload sets no range expects none. If `line` or `start_line` is null because the comment became outdated, use `original_line` or `original_start_line`. Compare bodies exactly after normalizing only line endings and surrounding whitespace. Compare as a multiset, one received comment per expected comment; a matching count is never sufficient.
4. Classify each expected and selected comment pair as equal (every compared field present and equal), conflicting (a present field differs), or unknown (no present field differs but a compared field is missing). Then decide:
   - `verified`: the expected comments can be paired one-to-one with the selected comments, all equal, with no selected comment left unpaired.
   - `mismatch`: no pairing is consistent even if every unknown pair were equal, including a different number of selected comments. Re-read once before concluding a count difference, because a fresh review can lag. Record each difference as expected versus received.
   - `verification incomplete`: any pairing is consistent only because a missing field might match, or retrieval or identification failed. A missing field is never a mismatch.
5. Record the verification outcome with the read-back source and pagination state, the read time, and diagnostic evidence: matched, missing, conflicting, and extra comments, with missing field names and any retrieval error. A known `submitted` outcome stays reported as published whatever the verification outcome. Report `verification incomplete` as unverified, and `mismatch` with its differences, as separate from the submission result.

## Wording verification

When changing audience routing or tone instructions, use `comment-audience-scenarios.md` to verify generated wording separately from the deterministic contract checks in `scripts/check.py`. This is maintenance verification, not an additional publication gate.

## Verification scenarios

When changing the submission outcome or read-back verification rules, use `publication-verification-scenarios.md` to check the outcomes for omitted fields, mismatches, ranges, pagination, other reviews' comments, partial failures, and ambiguous submissions. This is maintenance verification, not an additional publication gate.
