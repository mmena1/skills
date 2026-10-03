# Add PR Review Comments

Use this only for a confirmed GitHub PR when the user asks to add comments.

1. Re-check PR state and `headRefOid` with `gh pr view --json state,mergedAt,headRefOid`, then compare `headRefOid` with the recorded reviewed head SHA. Stop if closed, merged, or changed; a stale pinned result cannot be published.
   Apply `pr-review-overlap.md` before drafting: exclude already-reported items and include prior discussion links for resolved overlaps. Publish new comments only; never reply inside, edit, or resolve an existing thread.
2. Draft inline comments only for Findings and user-selected Unresolved items. Use committed code and team-visible evidence whenever practical; private ignored context is not named or quoted without explicit approval.
3. Findings use assertive defect language supported by validator evidence. An Unresolved item is posted only after explicit per-item approval and must be a question describing observed evidence and what remains unsettled; it must not assert a defect.
   Write each comment in the voice described in `review-tone.md`; these publication rules take precedence where they differ.
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
10. Submit one review with an empty top-level body unless the user explicitly requests a summary:
   `gh api POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` with `event: COMMENT` and the approved `comments` array.
11. Validate the final payload after any coordinate change and verify the expected comment count after overlap suppression. Update the final report and run state with actual publication and overlap dispositions.
