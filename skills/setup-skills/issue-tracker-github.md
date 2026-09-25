# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Implementation workflow

- **Implementation-ready state**: the issue has the label mapped from the `ready-for-agent` role in `docs/agents/triage-labels.md`; when no mapping file exists, the default label is `ready-for-agent`. Only open, unblocked, unassigned implementation issues have this label. Absence of the label is the planned or non-ready state.
- **Authority**: use the approved direct parent/spec when the issue has a `## Parent` reference or native parent. A present but unapproved or unresolvable parent fails closed and never falls back to standalone authority. A parentless issue may use itself as authority only with the complete standalone approval record below. The issue defines scope and acceptance criteria; an approved parent defines architecture and public seams. Standalone issues need no synthetic parent/spec.
- **Standalone authority record**: add a GitHub issue comment with exactly this structure after `/to-tickets` has published a parentless issue whose breakdown the user explicitly approved, or after `/triage` receives explicit maintainer approval both that no parent/spec is intended and that the issue itself is implementation authority:

  ```markdown
  ## Standalone implementation authority
  - Parent/spec: intentionally none
  - Authority: this issue
  - Upstream approval: explicit user approval in `/to-tickets`
  ```

  The recognized approval values are `/to-tickets` and `/triage`. Triage comments must retain their required AI disclaimer before the record. Verify the comment's author metadata and accept it only when `user.type` is `User` and the author's current repository permission is effective `write` (including `maintain`) or `admin`, using GitHub's collaborator-permission endpoint. `author_association` is supplemental context only. `/implement` accepts this record only when the issue has no parent. A ready label or agent brief alone is insufficient.
- **Open and unblocked**: fetch state, labels, assignees, and dependency data. The issue must be open. Native `blocked_by` dependencies are the canonical gate when available; otherwise use the configured fallback `Blocked by` references. Every blocker must be closed.
- **Claim**: after all readiness checks pass, assign the issue with `gh issue edit <n> --add-assignee @me` and remove the implementation-ready label so the claimed issue leaves the frontier.
- **Resolve**: for implementation closeout, update acceptance criteria when supported and comment with commit and verification evidence, but leave the issue open. Record a PR/merge handoff naming the issue that must be closed. Do not close the parent spec. Explicit issue closure is reserved for tracker workflows whose lifecycle requires it outside `/implement`.
- **PR/merge handoff and post-merge reconciliation**: the separately authorized PR/merge owner (the human or workflow that creates and merges the implementation PR) owns adding and verifying `Closes #<n>`, confirming auto-closure, and invoking `/reconcile <ticket-ref>`. If the issue did not auto-close, stop the reconciliation and report the missing or ineffective close reference rather than promoting dependent tickets. If the closed ticket belongs to a Wayfinder map, also perform its resolve operation below.
- **`/reconcile` contract**: `/reconcile <ticket-ref>` uses the resolved ticket as its trigger. For a parent-backed trigger, enumerate all implementation children under its direct parent/spec, preferring native child relationships and preserving their order; otherwise resolve each child's direct `## Parent` reference and order by the configured fallback, defaulting to ascending issue number. For a parentless trigger, require its trusted standalone authority record and enumerate all parentless issues with trusted standalone authority records. Paginate all issues in `state=all`, exclude pull requests, and read candidate parent relationships and approval-comment metadata before selecting this set; for each candidate record, verify `user.type` is `User` and permission is effective `write` (including `maintain`) or `admin`, failing closed on lookup failures. `author_association` is supplemental context only. Include closed issues to remove stale ready labels and sort by issue number. A present but unapproved or unresolvable parent never falls back to standalone reconciliation. Native dependencies are authoritative when available; use the configured fallback only when native dependency data is unavailable. An issue is ready only when open, unblocked by every blocker, and unassigned. Remove stale ready labels from blocked, assigned, closed, or otherwise non-executable issues. Do not change parent-state or issue-resolution. Report promotions, removals, no-ops, unresolved blockers, and the resulting frontier. If the trigger is open, stop without mutations and report the failed `Closes #<n>` lifecycle.
- **Frontier promotion**: after publishing tickets, or during the post-merge reconciliation above, re-query every open child of the parent. Add the implementation-ready label to every unblocked, unassigned child; remove it from blocked or assigned children. Preserve parent order and report the resulting frontier.

For parentless standalone reconciliation, apply the same readiness classification to the full trusted parentless set and report the frontier in ascending issue-number order. Closing one standalone issue can therefore promote another whose blocker is now closed.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
