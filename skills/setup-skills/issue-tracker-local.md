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
- **Standalone authority**: unsupported. Every implementation ticket requires a `Parent:` spec, and its approved parent spec is its only implementation authority. A parentless ticket has no implementation authority and is never made ready; `/implement` and `/reconcile` stop and report that this tracker requires a parent/spec. An Agent Brief grants no authority here, so never add one to a local ticket.
- **Open and unblocked**: the ticket is open unless `Status` is `resolved` or `closed`. The `Blocked by:` references are the canonical gate; confirm each referenced ticket is resolved.
- **Direct dependent discovery**: scan all configured `.scratch/<feature-slug>/issues/*.md` files for direct open downstream dependents with exact `Blocked by:` references to the resolved trigger. Resolve numbered identifiers within the containing feature and explicit ticket paths relative to the repository across features; compare resolved paths, independently of ready statuses and titles. Order dependents by repository-relative filename. Native dependency data takes precedence if configured; use fallback text only when native data is unavailable. Do not recursively traverse dependencies of discovered or newly promoted tickets. Repository enumeration authorizes reads, not mutation in unrelated specs.
- **Affected reconciliation scopes**: select the trigger's approved parent/spec and the approved parent/spec of each direct open dependent. Follow each dependent's own `Parent:` path and verify that spec's approval; siblings and blockers never supply authority. A present but unapproved, missing, or unresolvable parent fails closed. Report dependent authority failures and skip those invalid scopes while continuing independently validated scopes. Invalid trigger authority stops without writes. This tracker remains parent-only: a parentless dependent has no authority and never selects a standalone scope. Deduplicate specs by resolved path before writing. Process the trigger's scope first, then dependents in filename order, and rescan every implementation sibling in each selected spec, including resolved and closed files, in filename or configured parent order.
- **Claim**: after all readiness checks pass, set `Status: claimed` and save before implementation.
- **Resolve**: check completed acceptance criteria, append an `## Implementation` summary with commit and verification evidence, then set `Status: resolved`.
- **Frontier promotion**: after publishing tickets, rescan every open, unclaimed sibling implementation ticket. After resolving one, refresh all affected reconciliation scopes as below. Set unblocked, unclaimed, non-held tickets to the configured implementation-ready state and blocked ready tickets to `Status: planned`, then report each frontier in number order. If the resolved ticket belongs to a Wayfinder map, also perform the map update below.
- **`/reconcile` contract**: `/reconcile <ticket-ref>` validates the trigger's own parent authority and verifies the trigger is resolved; an open trigger causes no writes. Discover direct open dependents and validate affected reconciliation scopes as above before writing. A candidate is ready only when open, every blocker is resolved, unclaimed, and not held. Mapped `needs-triage`, `needs-info`, `ready-for-human`, and `wontfix` statuses hold candidates non-ready in every selected scope and are preserved. An unresolved blocker reference prevents promotion. Set only statuses that differ, at most once per ticket, so an unchanged rerun is a no-op. Demote a blocked ready ticket to planned; preserve held, claimed, resolved, and closed lifecycle statuses. If a configured tracker stores a separate ready marker, remove only that marker from blocked, claimed, resolved, closed, held, or otherwise non-executable candidates. The default single `Status:` cannot hold a ready marker simultaneously with a closed or held status. Readiness is the only mutation: never change specs, authority, claims, dependencies, issue resolution, or held triage states. Report affected scopes, authority failures, promotions, removals, no-ops, unresolved blockers, and each resulting frontier in its scope's order. Reads for discovery do not authorize mutation in unrelated specs, and merely transitive dependents do not select more scopes. If local resolution already refreshed all affected scopes, a second run is a no-op.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
