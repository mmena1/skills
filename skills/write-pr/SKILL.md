---
name: write-pr
description: Prepare and open a GitHub pull request from a clean, committed branch delta, repository guidance, the configured issue-tracker workflow, and verified change evidence.
disable-model-invocation: true
triggers:
  - user
---

# Prepare and open a pull request

Use this workflow when the user asks to prepare, write, open, or create a pull request. Repository guidance overrides the defaults in this skill.

This workflow handles pull-request preparation and handoff, not implementation or branch preparation. It does not create or switch branches, stage or commit changes, or fix implementation findings. It asks before pushing or creating a pull request. It may inspect the repository and prepare a draft without those confirmations.

## Terms

- **Base branch**: the branch the pull request targets, discovered from the configured primary remote and repository guidance.
- **Branch delta**: committed changes on the current branch that are not in the base branch.
- **Change brief**: the authoritative explanation of the work, assembled from the configured issue tracker, linked issue or specification files, repository guidance, commits, and the diff.
- **Supporting change**: a changed file or theme not explained by the change brief but plausibly related to the pull request. The body must explain why it is included.
- **Evidence**: concrete output showing that the change works, such as a test result, command output, rendered result, or a clearly stated verification gap.
- **Merge danger**: the reversibility and potential impact of merging the change. Every pull request states whether it is a one-way or two-way door and gives a one-word blast-radius classification.

## Required repository contract

Before analyzing the branch, read the repository's `AGENTS.md` files and referenced workflow documents. A repository must contain `docs/agents/issue-tracker.md`.

If `docs/agents/issue-tracker.md` is missing, stop and tell the user to run `setup-skills` before continuing. Do not infer where issues or specifications live when the repository contract is absent.

Read `docs/agents/issue-tracker.md` and follow its instructions for locating the issue, specification, or task that explains the branch, including tracker-defined PR/merge linkage, closure, and handoff requirements. Read the repository's PR template when one exists. Repository-specific rules may override every default in this skill, including the primary remote, base branch, verification commands, and pull-request creation command.

## Workflow

### 1. Inspect repository guidance and branch state

Read, in this order:

1. Root and applicable nested `AGENTS.md` or equivalent instruction files.
2. The documents those files explicitly require for Git, pull requests, issue tracking, security, and verification.
3. `docs/agents/issue-tracker.md`.
4. The repository pull-request template, if present.
5. The current branch, worktree state, and committed branch delta.

Resolve the configured primary remote explicitly from repository guidance or repository configuration. In fork/upstream setups, do not assume that `origin` is the primary remote. If the primary remote cannot be identified unambiguously, stop and ask the user which remote is authoritative.

Resolve the base branch in this order:

1. The symbolic remote `HEAD` for the configured primary remote, for example `git symbolic-ref --quiet --short refs/remotes/<primary-remote>/HEAD`.
2. The provider's authoritative default branch for the repository represented by that remote. For GitHub, use `gh repo view <owner>/<repo> --json defaultBranchRef --jq '.defaultBranchRef.name'`, deriving `<owner>/<repo>` from the primary remote URL.
3. The repository's explicitly documented default branch.
4. Stop and ask the user if none resolves.

A failed or empty provider lookup proceeds to the next fallback. Do not guess `main`, `master`, or another branch name.

Inspect the current branch and worktree with `git branch --show-current` and `git status --porcelain`. If the branch is detached or the worktree is dirty, stop, report the state, and ask the user to finish implementation and commit the intended changes through the owning workflow before retrying. Do not create a branch, stage, commit, stash, or otherwise modify the worktree. If the current branch is the base branch or has no committed delta from it, stop and ask the user to return with the intended feature branch and committed changes.

Inspect the delta with commands equivalent to:

```bash
git log --oneline <base>..HEAD
git diff --stat <base>...HEAD
git rev-list --left-right --count <base>...HEAD
```

Being behind the base branch alone does not require a rebase. Report the behind state and continue unless repository guidance requires synchronization. If synchronization is required, follow its documented update strategy. Do not rebase a published branch or force-push without explicit approval; when a force-push is approved and permitted by repository guidance, use the repository's safe convention, typically `--force-with-lease`. If conflicts occur, stop and ask the user to resolve them. Never auto-resolve code conflicts.

Check for an existing open pull request from the current head branch to the configured primary repository. For GitHub, scope the query to the base repository and head owner, for example `gh pr list --repo <base-owner>/<base-repo> --head <head-owner>:<branch> --state open --json number,title,url,baseRefName,isDraft`. Record any matching pull request; do not create a duplicate or update it implicitly.

**Completion criterion**: the configured primary remote, base branch, current branch, clean worktree, committed branch delta, behind/ahead state, existing pull-request status, repository obligations, and required ticket or issue identifier are known.

### 2. Build the change brief

Use `docs/agents/issue-tracker.md` to locate the authoritative issue, specification, or task files. Read all files that the tracker workflow identifies as part of the change brief. Also read linked design or implementation notes when repository guidance requires them.

If the tracker identifies multiple plausible sources, list them and ask the user to choose. If the tracker source is missing or does not explain the branch, ask the user for the issue or specification path rather than inventing requirements.

Capture the tracker-defined PR/merge lifecycle, including required issue references, close directives, and handoff or post-merge reconciliation steps. For example, when the tracker requires the PR/merge owner to close a GitHub issue through the PR, include the exact `Closes #<issue>` reference in the final PR body. Do not close the issue directly unless the configured tracker workflow explicitly assigns that action to this workflow.

Compare the change brief with:

- The branch delta and commit messages.
- The complete diff, including renamed and deleted files.
- Tests, documentation, configuration, and infrastructure changes.

Record every changed theme as either described by the change brief or a supporting change requiring rationale.

**Completion criterion**: the change brief, issue identifier, tracker-defined PR/merge lifecycle, intended implementation areas, tests, documentation, and every supporting change are accounted for.

### 3. Check repository conventions and security

Apply the repository's coding, testing, documentation, and Git conventions to the branch delta. Flag likely violations. Do not make implementation fixes; return actionable findings to the user and ask them to resolve or explicitly override each one before drafting the final pull request.

At minimum, check for:

- Required verification commands and their results.
- New or changed tests corresponding to behavior changes.
- Public API, schema, migration, infrastructure, or configuration impact.
- Unrelated changes or generated files.
- Secrets, credentials, tokens, passwords, private keys, environment contents, or sensitive URLs in the diff.
- New dependencies, if the repository requires approval or existing-use evidence.

Stop and warn the user before creating the pull request if the diff contains likely secrets or sensitive material. Do not print secret values.

**Completion criterion**: every flagged convention or security concern is resolved, explicitly overridden, or blocks pull-request creation.

### 4. Collect evidence

Run the smallest relevant verification commands required by the repository. Prefer execution-based evidence. Capture concise before-and-after evidence when the change fixes an existing behavior:

- **Before**: failing test, reproduced output, or previous observable behavior.
- **After**: passing test, corrected output, or new observable behavior.

For a new feature, use the relevant test or command proving the new behavior. For documentation or configuration changes, use the validation command, rendered result, or structural check. If no meaningful executable evidence exists, say so and name the remaining verification gap. Do not fix implementation failures in this workflow; report them and return the branch to its owning implementation workflow.

Do not claim evidence that was not observed.

**Completion criterion**: each behavior claim in the pull-request body has concrete evidence or an explicit verification gap.

### 5. Draft the pull request

Use the repository pull-request template when present. Preserve its headings and checklist semantics. When no template exists, use this structure:

```markdown
## Summary

<the smallest useful visual: a diff sketch, pseudocode block, call tree, file tree, or Mermaid diagram>

<brief explanation in the repository's domain language>

<tracker-required PR/merge references, including an exact close directive such as Closes #<issue> when applicable>

## Evidence

- **Before:** <failing or previous result, when meaningful>
- **After:** <passing or current result>

## Merge Danger

**Door:** <one-way or two-way>

**Blast Radius:** <one-word classification>

<brief explanation when the change is hard to reverse, destructive, changes a public contract, or has broad impact>
```

Keep prose brief. Place each visual next to the text it supports. Choose the smallest representation that makes ownership, order, state, or data flow clear:

- Pseudocode for algorithms or state transitions.
- A call tree for runtime control flow.
- A shallow file tree for ownership or broad refactors.
- Mermaid for component interaction or data flow.
- A diff sketch when the surrounding shape already exists and the change itself is the point.

Include:

- A title using the repository's required format, based on the change brief.
- A concise summary of the intended result.
- Grouped changed themes from the diff.
- Every supporting change with its rationale and appropriate depth.
- Verification evidence and gaps.
- Tracker-required PR/merge references and handoff directives, including `Closes #<issue>` when the tracker requires it.
- Merge danger with reversibility and blast radius.
- Template checkboxes that the diff and verification can actually prove.

**Completion criterion**: the title and body follow the repository template or generic structure, use the repository's domain language, account for the entire branch delta, and satisfy tracker-defined PR/merge lifecycle requirements.

### 6. Confirm with the user

Print the final title and body. If an open pull request for this branch was found, also print its URL and stop without pushing, creating a duplicate, or updating it. The prepared title and body are returned for the user to apply to the existing pull request if desired.

If no existing pull request was found, ask:

```text
Create pull request? (ready / draft / edit / abort)
```

- `ready` or `draft`: continue. This approves pushing the branch and creating the pull request with the exact displayed title and body.
- `edit`: accept inline changes, regenerate the body, and ask again.
- `abort`: stop without pushing or creating anything.

**Completion criterion**: the user has approved the exact title and body and selected ready or draft, or has received the prepared content and URL for an existing pull request.

### 7. Push and create the pull request

After confirmation:

1. Re-check for an open pull request from this head branch to the configured primary repository. If one now exists, print its URL and the approved title and body, then stop. Do not create a duplicate or update it implicitly.
2. Follow repository guidance for the remote and branch push.
3. Write the approved body to a temporary file when the CLI supports a body-file option.
4. Use the repository's documented pull-request command. If none exists, use `gh pr create` with the approved title, body, discovered base branch, and `--draft` when requested.
5. If the CLI is unavailable or unauthenticated, print the approved title, body, and an equivalent manual command without exposing secrets.
6. Remove temporary files created by this workflow.

**Completion criterion**: a pull-request URL is returned, or a complete manual fallback is printed. Never claim that a pull request was created without a confirmed result.
