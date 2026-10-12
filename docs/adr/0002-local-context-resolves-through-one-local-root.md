# Local-only context resolves through one declared local root shared by every worktree

Skills read repository context that may not be committed (ignored instruction files, `docs/agents/` configuration, glossaries, ADRs) and the local-markdown tracker keeps specs, tickets, claims, and the frontier under an ignored `.scratch/`. A harness or orchestrator that runs a skill in a linked Git worktree or another isolated working copy leaves all of that behind, and copying `.scratch/` into each worktree forks the tracker so one worker's claim is invisible to the next. The `local-context` skill now owns one convention for both, and the skills and `/setup-skills` templates that read local context apply it by name.

## Decision

Local-only context is classified into two kinds, and nothing else Git ignores is in scope:

- **Read-only local context**: root instruction files, `docs/agents/`, glossary files, and ADR directories. A skill reads each from the working copy first and, when absent, from the same repository-relative path under the local root, in place.
- **Mutable shared workflow state**: the local-markdown tracker. Its only authoritative location is `.scratch/` under the local root, read and written in place from every working copy.

The **local root** is resolved from the working copy alone:

1. `git config --local --type=path --get skills.localRoot`, when set, must be an absolute path to an existing directory, or the skill stops and reports it.
2. Otherwise, when `git rev-parse --path-format=absolute --git-dir` equals `--git-common-dir`, the working copy is an ordinary checkout and the local root is its top level. This is exactly the location skills used before this decision.
3. Otherwise the working copy is an undeclared linked worktree and has no local root. Required context and tracker state fail closed with a report of what is missing and where the skill looked; optional context is skipped silently as before.

The declaration is the whole mechanism. Repository config lives in Git's common directory, so `--git-common-dir` is the foundation without the state itself having to move there: one `git config` write is read by every linked worktree of the repository, including worktrees of a bare repository that has no primary working tree. Global, system, and per-worktree (`--worktree`) values are ignored, so one repository's declaration never leaks into another and a single worktree cannot opt out into its own copy. `python scripts/check.py` runs a model of this resolution, built from the same Git commands the skill states verbatim, against real Git repositories: two linked worktrees read each other's claim, resolution, and frontier promotion, and an undeclared worktree, a missing tracker, and an invalid declaration fail closed.

## Why it is harness-agnostic

Resolution uses only Git's own view of the working copy plus one repository setting. It never derives a path from the common directory's location, never asks `git worktree list` for a main worktree, and never assumes a sibling or parent directory layout, so it works the same for a plain checkout, a `git worktree add` worktree, a worktree of a bare repository, and whatever directory a harness chooses for its worktrees. Once a local root is declared, every harness-created working copy that can see the repository's config shares it: a linked worktree, or a directory copy that carries the repository's `.git`. A separate clone has its own config and joins only by declaring the same `skills.localRoot`; undeclared, it resolves as an ordinary checkout of its own and stops when it needs tracker state it does not have, because an absent tracker is never treated as empty and a skill reports before starting a new `.scratch/`. Before any declaration, a linked worktree has no local root and fails closed even when a harness copied `.scratch/` into it at creation, because skills ignore that copy.

## Migration

A repository used from one ordinary checkout needs no change. A repository that keeps local-only context and wants to use it from linked worktrees declares a local root once, from any working copy, with `git config --local skills.localRoot <absolute-path>`. Until it does, undeclared linked worktrees stop and report the missing declaration instead of forking state. `/setup-skills` offers the declaration when it finds linked worktrees alongside local-only context, and it moves files only after confirmation:

- **Dedicated directory (recommended).** Move, never copy, the existing `.scratch/` and any local-only classified files into a directory outside every working copy, at their repository-relative paths, then declare it. Nothing depends on any worktree afterward.
- **Existing checkout.** Declare the checkout that already holds the context. Nothing moves, but that checkout becomes load-bearing: moving or deleting it leaves the declaration pointing at a missing directory, which fails closed.

Per-worktree `.scratch/` directories left over from earlier copies are not migrated automatically. Skills report them as stray copies and ignore them; the user reconciles any state that diverged before discarding them.

## Tradeoffs

- Linked worktrees need one explicit setting before they can use local-only context. We accept that cost over silent discovery, because discovering a main worktree is what fails in bare repositories and harness layouts, and guessing wrong forks the tracker.
- An absolute path is machine-specific and survives neither a moved local root nor a move to another machine. Both cases fail closed and are fixed by re-declaring.
- An undeclared repository copied as a whole directory, `.git` and ignored `.scratch/` included, is indistinguishable from its original to Git, so the copy resolves as an ordinary checkout and uses its copied tracker. Detecting it would require configuration in every single checkout, which this decision rejects. The remedy is to declare a local root before any harness copies whole working directories; afterwards a copy carries the declaration and shares the tracker.
- The shared tracker makes writes visible, not atomic. Concurrent claims of the same ticket still race; parallel orchestrators keep assigning one ticket per worker.

## Rejected alternatives

- **Per-worktree copies of mutable state**, whether made at worktree creation or synced later. Copies diverge by construction: a claim or resolution in one worktree is invisible to the others, and the frontier splits.
- **Moving `.scratch/` into Git's common directory** (for example `$(git rev-parse --git-common-dir)/scratch`). It needs no setting for worktrees, but it changes the location every existing single checkout uses, forces a migration on all of them, and hides human-edited tracker files inside `.git/`.
- **Deriving the root from the common directory's parent.** That is the main worktree of a non-bare repository and an unrelated directory for a bare repository or a separate Git directory, so it is primary-worktree discovery in disguise.
- **Symbolic links from each worktree to one `.scratch/`.** Some skill or harness would have to create and maintain them in every worktree, they depend on a primary location, and Windows link support is uneven.
- **Copying every ignored file into isolated working copies.** It forks mutable state and exposes secrets, environment files, credentials, caches, and build output that skills have no reason to read.
