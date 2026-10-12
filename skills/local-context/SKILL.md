---
name: local-context
description: Resolve a repository's local-only context and local-markdown tracker state from any working copy, including linked Git worktrees and harness-created isolated working copies. Use when a skill needs ignored repository instruction files or local instruction overrides such as `AGENTS.local.md`, `docs/agents/` configuration, glossaries, or ADRs, or the `.scratch/` tracker, when such context is missing from the working copy, or when declaring where a repository's local context lives.
---

# Local Context

Context that Git does not track exists only where someone created it. A linked worktree or other isolated working copy does not contain it, and a copy of mutable state forks it. This convention says which local-only context skills use, where it lives, and how a skill finds it from any working copy. It never assumes or searches for a primary checkout or main worktree, and it does not depend on any harness's worktree layout.

## Classification

Only the context classified here is in scope. Never read through this convention, copy, link, or expose anything else Git ignores: secrets, environment files, credentials, caches, build output, or any other ignored content.

- **Read-only local context**: content skills read but do not change during a run. It is the repository instruction files `AGENTS.md` and `CLAUDE.md` at the root and their local instruction overrides `AGENTS.local.md` and `CLAUDE.local.md`, the `docs/agents/` configuration, the glossary files `GLOSSARY.md` and `GLOSSARY-MAP.md` with the per-context glossaries a map names (or their legacy `CONTEXT.md` and `CONTEXT-MAP.md` names), and the ADR directories `docs/adr/` and `src/<context>/docs/adr/`.
- **Mutable shared workflow state**: content skills change and every worker must observe. It is the local-markdown issue tracker under `.scratch/`: specs, tickets, statuses, claims, maps, and the frontier.

## Resolve the local root

The **local root** is the one directory per repository that holds its local-only context, at the repository-relative paths that context would have in a checkout. Resolve it from the working copy the skill runs in:

1. **Declared**: run `git config --local --type=path --get skills.localRoot`. Repository config lives in Git's common directory, so every linked worktree of a repository reads the same declaration. The value must be an absolute path to an existing directory. When it is relative or the directory does not exist, stop and report the value and the problem; never fall back to the next step.
2. **Ordinary checkout**: when nothing is declared, compare `git rev-parse --path-format=absolute --git-dir` with `git rev-parse --path-format=absolute --git-common-dir`. When they name the same directory, the working copy is an ordinary checkout and the local root is `git rev-parse --show-toplevel`. This is the behavior that predates the convention, so a single checkout needs no configuration.
3. **Undeclared linked worktree**: otherwise there is no local root. Never search for a main worktree, guess sibling directories, or treat the working copy's own top level as the local root.

Once a local root is declared, a harness-created working copy shares it when it is a linked worktree, a directory copy that carries the repository's `.git` and so its config, or a clone whose own repository config declares the same root. Before any declaration, a linked worktree has no local root, but a directory copy or a clone is an ordinary checkout of its own: Git cannot tell a copy from the original, so the copy uses its own top level, including any `.scratch/` copied into it. Declare a local root before anything copies whole working directories.

Only the repository config counts. A declaration in global or system config, or in per-worktree config written with `git config --worktree`, is not a local root. Outside a Git repository, the project directory is the local root, as before.

## Read read-only local context

Read each classified file from the working copy first. A file present there always wins, because it belongs to the commit under work. A classified file is local-only only when the working copy's Git ignores it: `git check-ignore -q -- <path>` succeeds, through `.gitignore` or the `.git/info/exclude` file every worktree shares. When a local-only file is absent from the working copy and a local root exists, read the same repository-relative path under the local root, in place: never copy or link it into the working copy. The copy there counts only when the local root's own Git does not track it: in the local root's directory, `git ls-files --error-unmatch -- <path>` must fail, which it also does when the local root is not a Git checkout. Otherwise the file is tracked content, and so is any classified file Git does not ignore. When the working copy lacks tracked content, for example because the branch deleted it, even while also ignoring it, it is absent: never read it from the local root, which may hold another branch's copy.

When a skill requires a classified file, such as `docs/agents/issue-tracker.md` for a tracker-driven run, and no allowed location holds it, stop and report the missing path, each location checked, and, in an undeclared linked worktree, that the repository declares no `skills.localRoot`. Absent optional context keeps its existing behavior: for example, missing domain docs are still skipped silently.

## Use mutable shared workflow state

The local-markdown tracker's one authoritative location is `.scratch/` under the local root. Every `.scratch/` path in a tracker contract means that directory. Read and write tracker files there, in place, from whichever working copy the skill runs in, so a claim, status change, or frontier promotion made from one worktree is what every other worktree reads.

- Use a working copy's own `.scratch/` only when that working copy is the local root. Never create, copy, or link `.scratch/` into a working copy. Report any other `.scratch/` in the working copy as a stray copy and ignore it.
- When a run needs existing tracker state (a spec, ticket, map, or frontier) and `.scratch/` or the referenced file is absent under the local root, stop and report the missing path and the local root it resolved to, as for any missing required context.
- Before creating `.scratch/` itself because it does not exist under the local root yet, report the local root and that a new tracker will start there, so a working copy that resolved as its own local root never starts a second tracker unnoticed.
- With no local root, local tracker state is unavailable. A skill that needs it must stop and report that the working copy is a linked worktree whose repository declares no `skills.localRoot`, naming the commands it ran. Never start a new tracker in the working copy.

The shared location makes one worker's writes visible to every other worker; it does not lock files. Two workers that claim the same ticket at the same moment still race, so a parallel orchestrator gives each worker its own ticket.

## Declare the local root

Only the user, or `/setup-skills` with the user's confirmation, writes the declaration. Other skills only read it. Declare it once, from any working copy of the repository:

```text
git config --local skills.localRoot <absolute-path>
```

Choose one of these:

- **A dedicated directory outside every working copy** (recommended). It depends on no worktree. Migrate by moving, not copying, the existing `.scratch/` and any local-only classified files into it at their repository-relative paths, so that no second copy remains.
- **An existing checkout that already holds the local context.** Nothing moves, but that checkout must stay in place while the declaration names it.

To undo a declaration, move the context back into the checkout that will be used alone and run `git config --local --unset skills.localRoot`.
