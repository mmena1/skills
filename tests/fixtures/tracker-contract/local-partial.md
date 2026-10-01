# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

_Team note: we review every spec in a pairing session before ticketing it._

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Every implementation issue has a `Parent:` line containing the direct path to its governing spec
- Triage state is recorded as a `Status:` line near the top of each issue file

## Implementation workflow

- **Implementation-ready state**: `Status: agent-ready`. Only open, unblocked, unclaimed implementation tickets have this state.
- **Parent/spec**: follow the ticket's `Parent:` path and read the spec.
- **Open and unblocked**: the ticket is open unless `Status` is `resolved` or `closed`, and every ticket in its `Blocked by:` line is resolved.
- **Claim**: set `Status: claimed` and save before implementation.
- **Resolve**: append an `## Implementation` summary with commit and verification evidence, then set `Status: resolved`.
- **Frontier promotion**: after resolving a ticket, set every unblocked, unclaimed sibling to `Status: agent-ready` and report the frontier.
- **`/reconcile` contract**: `/reconcile <ticket-ref>` follows the resolved ticket's `Parent:` path, verifies the trigger is resolved, rescans every implementation sibling under that spec in filename order, and reports promotions, removals, unresolved blockers, and the resulting frontier.

## Wayfinding operations

- **Claim**: set `Status: claimed` and save before any work.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`; this line is the canonical gate for wayfinding tickets.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`.
