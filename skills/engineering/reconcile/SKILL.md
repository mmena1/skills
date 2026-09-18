---
name: reconcile
description: Recompute the implementation frontier under a resolved ticket's parent from current tracker truth after post-merge closeout.
disable-model-invocation: true
triggers:
  - user
---

# Reconcile

Recompute one implementation parent's frontier after a ticket resolves. Invoke this explicitly as `/reconcile <ticket-ref>` after the tracker reports that the triggering implementation ticket is resolved.

This is a tracker-state operation. Read the repository instructions and `docs/agents/issue-tracker.md` before any tracker write. Require that configuration to define the ready state, direct parent lookup, canonical blocker lookup, claim/assignment state, resolution state, child enumeration, and ready-state mutation. If any part is missing or ambiguous, stop and tell the user to migrate or re-run `/setup-matt-pocock-skills`.

## Recompute the frontier

1. Resolve `<ticket-ref>` through the configured tracker and read its current state, parent reference, blockers, assignee or claim, labels/status, body, and comments as applicable.
2. Resolve the ticket's direct parent or spec and read it completely enough to identify its implementation children and their order. Do not infer a parent from a sibling or scan unrelated closed tickets.
3. Verify the trigger is resolved according to the tracker. For GitHub, the issue must be closed. If it is open, stop without changing any ticket and report that post-merge closeout or the required close reference did not complete. Do not close it here.
4. Re-query every implementation child of that same parent, including enough state to remove stale ready markers from non-executable children. Use native dependency relationships when the tracker provides them; use the configured fallback only when native dependency data is unavailable.
5. Classify each child from current state:
   - ready when it is open, unblocked by every blocker, and unclaimed or unassigned;
   - non-ready when it is blocked, claimed or assigned, closed, or otherwise non-executable.
6. Apply only the ready-state mutations needed to make every child match its classification. A child already in the correct state is a no-op. Never modify the parent resolution state, invent a dependency, claim a ticket, or resolve a ticket as part of reconciliation.
7. Preserve the parent's child ordering when reporting the resulting frontier. The frontier is every open, unblocked, unclaimed child in parent order.

Report the triggering ticket, parent/spec, tickets promoted to ready, tickets removed from ready, tickets already correct, unresolved blockers, and the resulting frontier. State explicitly when no mutations were needed. Re-running with unchanged tracker state must produce the same report and no additional writes.

## Tracker branches

For GitHub, verify the merged PR's expected `Closes #<issue>` lifecycle indirectly through the issue's closed state. Native GitHub issue dependencies are authoritative when available. If the trigger is still open, report the failed close-reference lifecycle and leave all dependents unchanged. Do not modify the parent spec.

For GitLab, verify the supplied issue is closed after the configured merge-request closeout. Prefer the configured native child or epic relationship and its order; otherwise enumerate issues whose direct `## Parent` reference resolves to the parent, using the configured order or ascending issue IID. Native blocking links are authoritative when available, with the configured `Blocked by` fallback used only when native dependency data is unavailable. An open trigger stops without mutations.

For local markdown, resolve the supplied path or configured ticket identifier, follow its `Parent:` line, verify its `Status:` is the configured resolved or closed state, then rescan every sibling file under the parent feature in filename or configured parent order. Update only the configured ready/planned or equivalent status fields needed to converge the frontier. If local resolution already performs a synchronous frontier refresh, still use the same idempotent classification and avoid a second write when states already match.

## Scope boundary

Do not edit implementation code, commit, push, create or modify pull requests, close implementation issues, change the parent, pull downstream work into this session, or globally repair unrelated closed tickets. `/implement` still owns implementation, review, commit, and its configured handoff; `/reconcile` starts only after the tracker says that implementation ticket is resolved.
