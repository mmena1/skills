## What it does

`reconcile` refreshes the implementation frontier beneath one parent after a resolved ticket changes the tracker graph. It starts from the supplied ticket, follows its direct parent, and classifies every sibling from current tracker state. It is a narrow causal trigger, not a global scan of closed work.

## When to reach for it

You invoke this by typing `/reconcile <ticket-ref>`, and the agent won't reach for it on its own. Reach for it after a merged GitHub implementation PR has closed its issue, or when a local or custom tracker needs the same explicit frontier recomputation. For implementation work itself, use [implement](https://aihero.dev/skills-implement); for a broad tracker cleanup, this skill is intentionally the wrong tool.

## Prerequisites

The repository must have the tracker configuration produced by [setup-matt-pocock-skills](https://aihero.dev/skills-setup-matt-pocock-skills). It must describe the ready state, parent lookup, blocker source, resolution state, child enumeration, and ready-state mutations.

## The frontier

The leading idea is **recompute**. A child is ready only when it is open, every blocker is resolved, and it is unclaimed. The skill re-queries all implementation children under the triggering ticket's parent, so it handles multiple newly executable siblings and also removes stale ready states from blocked, assigned, closed, or otherwise non-executable children. Parent order remains the order of the resulting frontier.

GitHub uses native issue relationships and dependencies when available and checks that the trigger is closed before writing. Custom trackers use the relationships and resolution contract recorded in `docs/agents/issue-tracker.md`. A missing or ineffective close lifecycle stops the run without compensating by closing the issue. Local markdown trackers follow their `Parent:` and `Status:` fields and converge sibling statuses idempotently.

## Common questions

**Does it close the triggering GitHub issue if the merge did not?**

No. An open trigger means the PR/merge close-reference lifecycle failed. The skill reports that state and makes no frontier mutations.

**Does it promote a sibling just because the trigger closed?**

No. Every sibling's full blocker set, open state, and assignment state are evaluated.

**What happens on a second run?**

It reports the same frontier with no additional mutations when tracker state is unchanged.

## It's working if

- An open trigger stops before any tracker mutation.
- A sibling blocked by another still-open ticket remains non-ready.
- An unblocked assigned sibling remains non-ready.
- Multiple newly executable siblings are all promoted in parent order.
- A second run with unchanged tracker state is a no-op.

## Where it fits

`reconcile` is a post-merge chain step after [implement](https://aihero.dev/skills-implement) and its separately authorized PR/merge handoff: `to-tickets → implement → code-review → PR/merge → reconcile`. It is the tracker-state complement to implementation, while [ask-matt](https://aihero.dev/skills-ask-matt) routes the broader skill set.
