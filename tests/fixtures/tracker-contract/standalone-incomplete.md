# Issue tracker: Linear

Issues and specs for this repo live in the team's Linear workspace. Use the `linear` CLI for all operations.

## Implementation workflow

- **Implementation-ready state**: the `agent-ready` label. Only open, unblocked, unassigned implementation issues have it. Absence of the label is the planned or non-ready state.
- **Parent/spec**: follow the issue's Linear parent and read its approval.
- **Standalone authority**: a parentless issue is its own implementation authority when it is labelled `agent-ready` and carries an `## Agent Brief`.
- **Open and unblocked**: Linear `blocked by` relations are the canonical gate; every blocker must be done.
- **Claim**: assign the issue to yourself and remove `agent-ready`.
- **Resolve**: comment with commit and verification evidence and move the issue to Done.
- **Frontier promotion**: after publishing or resolving, add `agent-ready` to every unblocked, unassigned child and remove it from the rest.
- **`/reconcile` contract**: `/reconcile <issue-ref>` uses the resolved issue as its trigger. If the trigger is open, stop without writes; otherwise enumerate every child of its parent in Linear sort order. Apply only the label changes needed, so an issue already in its correct state is a no-op.
