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
- **Authority**: an implementation issue has either parent-backed authority or standalone authority. If the issue has a direct parent/spec reference in its `## Parent` section or a native parent relationship, follow that parent and require its approval. Read the parent's body and comments. The issue defines scope and acceptance criteria; the approved parent defines architecture and public seams. A present but unapproved, missing, or unresolvable parent fails closed and never falls back to standalone authority, even when the issue carries an Agent Brief.
- **Standalone authority**: a parentless issue is its own implementation authority when it has no direct or native parent/spec, carries a complete trusted Agent Brief, and is in the implementation-ready state. Keep bounded standalone work in the issue itself; do not create a synthetic parent/spec.
  - **Complete Agent Brief**: A complete Agent Brief has the `## Agent Brief` heading and the Category, Summary, Current behavior, Desired behavior, non-empty Acceptance criteria, and Out of scope fields; `Key interfaces` is optional and its absence never makes a brief incomplete. Acceptance criteria are non-empty when they list at least one criterion with text. The brief section runs from its heading to the next level-one or level-two heading, so surrounding text such as a heading above it, a `## Blocked by` section after it, or a generated footer does not invalidate it.
  - **Trusted sources**: an issue comment containing a complete Agent Brief whose author is a human GitHub account with effective repository permission `write` (including `maintain`) or `admin`; or the issue body, when it contains a complete Agent Brief and the issue author is a human account with that permission. `/triage` normally writes the brief comment, and `/to-tickets` writes the issue-body brief after the user approves the breakdown, but recognizing a brief does not depend on detecting `/triage`, its AI disclaimer, or any other workflow marker.
  - **Precedence**: the newest complete trusted brief comment is authoritative when one exists; otherwise the complete trusted issue-body brief is. An untrusted or incomplete comment never overrides a trusted issue-body brief.
  - **Verification**: fetch the issue author and every comment with author metadata, for example `gh api repos/<owner>/<repo>/issues/<n> --jq '{body, login: .user.login, user_type: .user.type}'` and `gh api --paginate repos/<owner>/<repo>/issues/<n>/comments --jq '.[] | {body, created_at, author_association, login: .user.login, user_type: .user.type}'`. For each candidate brief, require `user_type` to be `User`, then check that author's current permission with `gh api repos/<owner>/<repo>/collaborators/<login>/permission --jq '.permission'`. GitHub reports `maintain` as the legacy base permission `write`; accept only `write` or `admin`, and reject bots, `read` (including triage), `none`, missing permissions, and lookup failures. `author_association` is supplemental context only, not an authorization signal.
  - **Fail closed**: the implementation-ready label without a complete trusted brief grants no authority, and a complete trusted brief without the implementation-ready state is not yet implementable. Comments in the separate standalone approval-record format this contract used to define grant no authority.
- **Open and unblocked**: fetch state, labels, assignees, and dependency data. The issue must be open. Native `blocked_by` dependencies are the canonical gate when available; otherwise use the configured fallback `Blocked by` references. Every blocker must be closed.
- **Claim**: after all readiness checks pass, assign the issue with `gh issue edit <n> --add-assignee @me` and remove the implementation-ready label so the claimed issue leaves the frontier.
- **Resolve**: for implementation closeout, update acceptance criteria when supported and comment with commit and verification evidence, but leave the issue open. Record a PR/merge handoff naming the issue that must be closed. Do not close the parent spec. Explicit issue closure is reserved for tracker workflows whose lifecycle requires it outside `/implement`.
- **PR/merge handoff and post-merge reconciliation**: the separately authorized PR/merge owner (the human or workflow that creates and merges the implementation PR) owns adding and verifying `Closes #<n>`, confirming auto-closure, and invoking `/reconcile <ticket-ref>`. If the issue did not auto-close, stop the reconciliation and report the missing or ineffective close reference rather than promoting dependent tickets. If the closed ticket belongs to a Wayfinder map, also perform its resolve operation below.
- **`/reconcile` contract**: `/reconcile <ticket-ref>` uses the resolved ticket as its trigger. If it has a parent/spec, enumerate every implementation child of that parent. Prefer native sub-issue order; otherwise resolve each child's direct `## Parent` reference and use the configured fallback, defaulting to ascending issue number. A present but unapproved or unresolvable parent fails closed and never falls back to the standalone set. If the trigger has no parent/spec, require that it carries a complete trusted Agent Brief, resolved exactly as for `/implement` (the trigger is closed and unlabelled by then, so the implementation-ready state is not part of this check); a parentless trigger without one stops with a report and no mutations. The standalone candidate set is every issue in the repository with no direct or native parent and a complete trusted Agent Brief, resolved the same way. Paginate all issues in `state=all`, exclude pull requests, and read each candidate's parent relationships, issue author, and comments with author metadata before selecting this set; a failed permission lookup leaves that brief untrusted. Include closed and open candidates so stale ready labels can be removed, and sort the set by issue number. Native dependencies are authoritative when available; use the configured fallback only when native dependency data is unavailable. An issue is ready only when open, unblocked by every blocker, and unassigned. In the standalone set, an issue that carries an explicit non-agent triage state: a label mapped from the `needs-triage`, `needs-info`, `ready-for-human`, or `wontfix` role in `docs/agents/triage-labels.md` is held non-ready: reconciliation preserves that triage decision, never promotes it, and never changes its triage label, while an unlabelled planned issue is still promoted once its blockers close. Remove stale ready labels from blocked, assigned, closed, or otherwise non-executable issues. Apply only the label changes needed to match each classification; an issue already in its correct state is a no-op, so a rerun with unchanged tracker state makes no writes. Reconciliation mutates readiness only: it never creates or edits Agent Brief authority, changes a parent or issue resolution, or invents dependencies. Report promotions, removals, no-ops, unresolved blockers, and the resulting frontier. If the trigger is open, stop without mutations and report the failed `Closes #<n>` lifecycle.
- **Frontier promotion**: after publishing tickets, or during the post-merge reconciliation above, re-query every open child of the parent. Add the implementation-ready label to every unblocked, unassigned child; remove it from blocked or assigned children. Preserve parent order and report the resulting frontier. A parentless ticket enters the frontier only when its issue-body Agent Brief is trusted; when the publishing account's permission cannot be verified, it stays non-ready.

For a standalone reconciliation, apply the same readiness classification, including the held triage states, to the full trusted parentless set and report the frontier in ascending issue-number order. This lets closing one standalone issue promote another when its open blocker is resolved.

Standalone authority is separate from frontier promotion. Applying the implementation-ready label never creates authority, and reconciliation never creates or edits Agent Brief authority.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
