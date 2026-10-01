---
name: reconcile
description: Recompute the implementation frontier for a resolved parent-backed or standalone issue from current tracker truth after post-merge closeout.
disable-model-invocation: true
triggers:
  - user
---

# Reconcile

Recompute one implementation parent's frontier after a ticket resolves. Invoke this explicitly as `/reconcile <ticket-ref>` after the tracker reports that the triggering implementation ticket is resolved.

This is a tracker-state operation. Read the repository instructions and `docs/agents/issue-tracker.md` before any tracker write. Require that configuration to define the ready state, direct parent lookup, canonical blocker lookup, claim/assignment state, resolution state, child enumeration, and ready-state mutation. If any part is missing or ambiguous, stop and tell the user to migrate or re-run `/setup-skills`. Also stop with that instruction, before any tracker write, when the configuration still defines the retired standalone authority comment record (a `## Standalone implementation authority` comment) instead of the Agent Brief rule.

## Recompute the frontier

1. Resolve `<ticket-ref>` through the configured tracker and read its current state, parent reference, blockers, assignee or claim, labels/status, body with author metadata, and comments with author metadata and creation time as applicable.
2. If the ticket has a direct parent/spec reference or native parent, resolve that parent and read it completely enough to identify its implementation children and their order. A present but unapproved or unresolvable parent fails closed and never falls back to standalone reconciliation. Do not infer a parent from a sibling.
3. If the ticket has no parent, resolve its Agent Brief with the same Agent Brief resolver as `/implement`, as `docs/agents/issue-tracker.md` defines it: the newest complete trusted brief comment, otherwise the complete trusted issue-body brief, where trusted means a human author with effective `write` (including `maintain`) or `admin` repository permission and a failed permission lookup is untrusted. `author_association` is supplemental context only. The trigger's readiness label is not part of this check. If the trigger has no complete trusted brief, stop with a report and no mutations. Historical standalone authority comments grant no authority. For GitHub, paginate all issues in `state=all`, exclude pull requests, and read each candidate's parent relationships, issue author, and comments with author metadata. The standalone set contains every issue in the repository with no direct or native parent and a complete trusted Agent Brief from that same resolver, including closed issues so stale ready labels can be removed. Do not add unapproved or unresolvable parent issues to this set.
4. Verify the trigger is resolved according to the tracker. For GitHub, the issue must be closed. If it is open, stop without changing any ticket and report that post-merge closeout or the required close reference did not complete. Do not close it here.
5. Re-query every implementation child of the parent, or every parentless issue with a complete trusted Agent Brief when the trigger has no parent. Include enough state to remove stale ready markers from non-executable issues. Use native dependency relationships when the tracker provides them; use the configured fallback only when native dependency data is unavailable.
6. Classify each issue from current state:
   - ready when it is open, unblocked by every blocker, and unclaimed or unassigned;
   - non-ready when it is blocked, claimed or assigned, closed, or otherwise non-executable;
   - for the standalone set only, held non-ready when it carries an explicit non-agent triage state: a label mapped from the `needs-triage`, `needs-info`, `ready-for-human`, or `wontfix` role in `docs/agents/triage-labels.md`. Reconciliation preserves that triage decision: it never promotes a held issue to ready and never changes its triage label. An unlabelled planned issue, such as a blocked `/to-tickets` ticket, carries no triage state and is promoted once its blockers close.
7. Apply only the ready-state mutations needed to make every issue match its classification. An issue already in the correct state is a no-op. Reconciliation mutates readiness only and never creates or edits Agent Brief authority. Never modify the parent resolution state, invent a dependency, claim a ticket, or resolve a ticket as part of reconciliation.
8. Preserve the parent's child ordering for parent-backed work. Report a standalone frontier in ascending issue-number order. The frontier is every open, unblocked, unclaimed issue in the selected set that is not held.

Report the triggering ticket, parent/spec or standalone scope, issues promoted to ready, issues removed from ready, issues already correct, unresolved blockers, and the resulting frontier. State explicitly when no mutations were needed. Re-running with unchanged tracker state must produce the same report and no additional writes.

## Tracker branches

For GitHub, verify the merged PR's expected `Closes #<issue>` lifecycle indirectly through the issue's closed state. Fetch each candidate's issue author and comments with author identity, and accept an Agent Brief only from a human account whose current repository permission is effective `write` (including `maintain`) or `admin`, as defined by the tracker contract. Native GitHub issue dependencies are authoritative when available. If the trigger is still open, report the failed close-reference lifecycle and leave all dependents unchanged. Do not modify the parent spec.

For local markdown, resolve the supplied path or configured ticket identifier, follow its `Parent:` line, verify its `Status:` is the configured resolved or closed state, then rescan every sibling file under the parent feature in filename or configured parent order. Update only the configured ready/planned or equivalent status fields needed to converge the frontier. If local resolution already performs a synchronous frontier refresh, still use the same idempotent classification and avoid a second write when states already match.

## Scope boundary

Do not edit implementation code, commit, push, create or modify pull requests, close implementation issues, change the parent, pull downstream work into this session, or globally repair unrelated closed tickets. `/implement` still owns implementation, review, commit, and its configured handoff; `/reconcile` starts only after the tracker says that implementation ticket is resolved.
