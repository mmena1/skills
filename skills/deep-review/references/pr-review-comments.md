# Add PR Review Comments

Use this only for a confirmed GitHub PR when the user asks to add comments.

1. Re-check PR state and `headRefOid` with `gh pr view --json state,mergedAt,headRefOid`, then compare `headRefOid` with the recorded reviewed head SHA. Stop if closed, merged, or changed; a stale pinned result cannot be published.
2. Draft inline comments only for Findings and user-selected Unresolved items. Use committed code and team-visible evidence whenever practical; private ignored context is not named or quoted without explicit approval.
3. Findings use assertive defect language supported by validator evidence. An Unresolved item is posted only after explicit per-item approval and must be a question describing observed evidence and what remains unsettled; it must not assert a defect.
4. For every comment, declare scope: point, method/design, or compact range. Record the smallest semantically representative source anchor and rationale.
5. Validate each payload mechanically against the current head: path, side, changed-line/range eligibility, and complete range fields. Also validate semantic representativeness. Reject mismatches rather than widening anchors.
6. If the preferred anchor is not commentable, use only the smallest relevant changed line or compact range as an explicit fallback, preserving scope and rationale. If no relevant changed location exists, do not publish inline.
7. Get per-comment approval with scope and anchor.
8. Re-check PR state and head SHA immediately before posting. If the head changed, stop and rerun the review.
9. Submit one review with an empty top-level body unless the user explicitly requests a summary:
   `gh api POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` with `event: COMMENT` and the approved `comments` array.
10. Validate the final payload after any coordinate change and verify the expected comment count.
