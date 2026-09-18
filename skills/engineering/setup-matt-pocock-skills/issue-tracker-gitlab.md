# Issue tracker: GitLab

Issues and specs for this repo live as GitLab issues. Use the [`glab`](https://gitlab.com/gitlab-org/cli) CLI for all operations.

## Conventions

- **Create an issue**: `glab issue create --title "..." --description "..."`. Use a heredoc for multi-line descriptions. Pass `--description -` to open an editor.
- **Read an issue**: `glab issue view <number> --comments`. Use `-F json` for machine-readable output.
- **List issues**: `glab issue list -F json` with appropriate `--label` filters.
- **Comment on an issue**: `glab issue note <number> --message "..."`. GitLab calls comments "notes".
- **Apply / remove labels**: `glab issue update <number> --label "..."` / `--unlabel "..."`. Multiple labels can be comma-separated or by repeating the flag.
- **Close**: `glab issue close <number>`. `glab issue close` does not accept a closing comment, so post the explanation first with `glab issue note <number> --message "..."`, then close.
- **Merge requests**: GitLab calls PRs "merge requests". Use `glab mr create`, `glab mr view`, `glab mr note`, etc., the same shape as `gh pr ...` with `mr` in place of `pr` and `note`/`--message` in place of `comment`/`--body`.

Infer the repo from `git remote -v`; `glab` does this automatically when run inside a clone.

## Merge requests as a triage surface

**MRs as a request surface: no.** _(Set to `yes` if this repo treats external merge requests as feature requests; `/triage` reads this flag.)_

When set to `yes`, MRs run through the same labels and states as issues, using the `glab mr` equivalents:

- **Read an MR**: `glab mr view <number> --comments` and `glab mr diff <number>` for the diff.
- **List external MRs for triage**: `glab mr list -F json`, then keep only MRs whose author is not a project member/owner (a contributor's MR, not a maintainer's in-flight work).
- **Comment / label / close**: `glab mr note`, `glab mr update --label`/`--unlabel`, `glab mr close`.

Unlike GitHub, GitLab numbers issues and MRs separately, so `#42` is unambiguous once you know which surface the maintainer means.

## When a skill says "publish to the issue tracker"

Create a GitLab issue.

## When a skill says "fetch the relevant ticket"

Run `glab issue view <number> --comments`.

## Implementation workflow

- **Implementation-ready state**: the issue has the label mapped from the `ready-for-agent` role in `docs/agents/triage-labels.md`; when no mapping file exists, the default label is `ready-for-agent`. Only open, unblocked, unassigned implementation issues have this label. Absence of the label is the planned or non-ready state.
- **Parent/spec**: follow the direct reference in the issue's `## Parent` section. Read the parent's description and notes. The ticket defines scope and acceptance criteria; the approved parent defines architecture and public seams.
- **Open and unblocked**: fetch state, labels, assignees, and issue links. The issue must be open. Native `blocked_by` links are the canonical gate when available; otherwise use the configured fallback `Blocked by` references. Every blocker must be closed.
- **Claim**: after all readiness checks pass, assign the issue with `glab issue update <n> --assignee @me` and remove the implementation-ready label so the claimed issue leaves the frontier.
- **Resolve**: update acceptance criteria when supported, post a note with commit and verification evidence, then close the issue. Do not close the parent spec.
- **Post-resolution trigger and child enumeration**: `/reconcile <ticket-ref>` verifies that the supplied issue is closed according to GitLab before writing. Prefer the parent's configured native child or epic relationship when available, preserving its order. When native child relationships are unavailable, enumerate repository issues whose direct `## Parent` reference resolves to that parent and order them by the configured fallback, defaulting to ascending issue IID. Include closed and open children so stale ready labels can be removed. Native blocking links are authoritative when available; use the configured `Blocked by` fallback only when native dependency data is unavailable. A child is ready only when open, unblocked by every blocker, and unassigned.
- **`/reconcile` contract**: after trigger verification, recompute every implementation child's ready state from current tracker data. Add the implementation-ready label only to open, unblocked, unassigned children; remove stale ready labels from blocked, assigned, closed, or otherwise non-executable children. Set only states that differ, preserve the resolved child order, leave the parent and issue-resolution state unchanged, and report promotions, removals, no-ops, unresolved blockers, and the resulting frontier. If the trigger is open, stop without mutations and report that post-resolution or merge-request closeout did not complete.
- **Frontier promotion**: after publishing tickets or closing one, re-query every open child of the parent. Add the implementation-ready label to every unblocked, unassigned child; remove it from blocked or assigned children. Preserve parent order and report the resulting frontier. If the closed ticket belongs to a Wayfinder map, also perform its resolve operation below.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `glab issue create --label wayfinder:map`. (On GitLab tiers with native epics, an epic may hold the map instead; a labelled issue works everywhere.)
- **Child ticket**: an issue carrying `Part of #<map>` at the top of its description and labels `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitLab's **native blocking link**, the canonical, UI-visible representation. Add it with the `/blocked_by #<n>` quick action, posted as a note (`glab issue note <child> --message "/blocked_by #<blocker>"`). Native blocking links are a Premium/Ultimate feature; on the free tier (or where unavailable) fall back to a `Blocked by: #<n>, #<n>` line at the top of the description. A ticket is unblocked when every blocker is closed.
- **Frontier query**: `glab issue list -F json` scoped to the map's children, drop any with an open blocker: a native `blocked_by` link to an open issue (`glab api projects/:id/issues/:iid/links`), or an open issue in the `Blocked by` line, or an assignee; first in map order wins.
- **Claim**: `glab issue update <n> --assignee @me`, the session's first write.
- **Resolve**: `glab issue note <n> --message "<answer>"`, then `glab issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
