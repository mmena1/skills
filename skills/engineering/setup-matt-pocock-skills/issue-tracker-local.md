# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Every implementation issue has a `Parent:` line containing the direct path to its governing spec
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Implementation workflow

- **Implementation-ready state**: `Status: ready-for-agent`, or the mapped value for that role in `docs/agents/triage-labels.md` when present. Only open, unblocked, unclaimed implementation tickets have this state.
- **Planned state**: `Status: planned`. Every blocked implementation ticket has this explicit non-ready state.
- **Parent/spec**: follow the ticket's `Parent:` path and read the spec. The ticket defines scope and acceptance criteria; the parent spec defines approved architecture and public seams.
- **Open and unblocked**: the ticket is open unless `Status` is `resolved` or `closed`. The `Blocked by:` references are the canonical gate; confirm each referenced ticket is resolved.
- **Claim**: after all readiness checks pass, set `Status: claimed` and save before implementation.
- **Resolve**: check completed acceptance criteria, append an `## Implementation` summary with commit and verification evidence, then set `Status: resolved`.
- **Frontier promotion**: after publishing tickets or resolving one, rescan every open, unclaimed sibling implementation ticket. Set unblocked tickets to the configured implementation-ready state and blocked tickets to `Status: planned`, then report the frontier in number order. If the resolved ticket belongs to a Wayfinder map, also perform the map update below.
- **`/reconcile` contract**: `/reconcile <ticket-ref>` uses the resolved ticket as its trigger, follows its `Parent:` path, and rescans every implementation sibling under that spec in filename or configured parent order. Verify the trigger is resolved before writing. A child is ready only when open, every blocker is resolved, and unclaimed. Set only statuses that differ, remove stale ready status from blocked, claimed, closed, or otherwise non-executable children, leave the parent unchanged, and report promotions, removals, no-ops, unresolved blockers, and the resulting frontier. If local resolution already refreshed the frontier, a second run is a no-op.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
