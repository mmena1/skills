---
name: write-pr
description: Prepare and open a GitHub pull request from the current branch, repository guidance, the configured issue-tracker workflow, and verified change evidence.
disable-model-invocation: true
triggers:
  - user
---

# Prepare and open a pull request

Use this workflow when the user asks to prepare, write, open, or create a pull request. Repository guidance overrides the defaults in this skill.

The skill asks before committing, pushing, or opening a pull request. It may inspect the repository and generate a draft without those confirmations.

## Terms

- **Base branch**: the branch the pull request targets, discovered from repository guidance or the remote's default branch.
- **Branch delta**: commits and file changes on the current branch that are not in the base branch.
- **Change brief**: the authoritative explanation of the work, assembled from the configured issue tracker, linked issue or specification files, repository guidance, commits, and the diff.
- **Supporting change**: a changed file or theme not explained by the change brief but plausibly related to the pull request. The body must explain why it is included.
- **Evidence**: concrete output showing that the change works, such as a test result, command output, rendered result, or a clearly stated verification gap.
- **Merge danger**: the reversibility and potential impact of merging the change. Every pull request states whether it is a one-way or two-way door and gives a one-word blast-radius classification.

## Required repository contract

Before analyzing the branch, read the repository's `AGENTS.md` files and referenced workflow documents. A repository must contain `docs/agents/issue-tracker.md`.

If `docs/agents/issue-tracker.md` is missing, stop and tell the user to run `setup-skills` before continuing. Do not infer where issues or specifications live when the repository contract is absent.

Read `docs/agents/issue-tracker.md` and follow its instructions for locating the issue, specification, or task that explains the branch. Read the repository's PR template when one exists. Repository-specific rules may override every default in this skill, including the base branch, branch naming, commit format, verification commands, and pull-request creation command.

## Workflow

### 1. Inspect repository guidance and branch state

Read, in this order:

1. Root and applicable nested `AGENTS.md` or equivalent instruction files.
2. The documents those files explicitly require for Git, pull requests, issue tracking, security, and verification.
3. `docs/agents/issue-tracker.md`.
4. The repository pull-request template, if present.
5. The current branch and worktree state.

Use commands equivalent to:

```bash
git rev-parse --abbrev-ref HEAD
git status --short
git remote -v
git log --oneline <base>..HEAD
git diff --stat <base>..HEAD
```

Discover the base branch from repository guidance first, then the remote's default branch, then a conventional local branch such as `main` or `master`. Do not assume a branch name. Discover required commit and branch formats from repository guidance and existing history.

Classify the state:

1. Feature branch with a branch delta and a clean tree: continue.
2. Feature branch with uncommitted changes: show the changes and ask for an approved commit message before committing.
3. Base or another non-feature branch with uncommitted changes: identify the change brief, propose a feature branch and commit message, and ask before creating either.
4. A clean branch with no delta: ask for the intended change or issue before drafting a pull request.

**Completion criterion**: the base branch, current branch, worktree state, branch delta, repository obligations, and required ticket or issue identifier are known.

### 2. Rebase when required

If repository guidance requires an up-to-date base branch, or the branch is behind it, propose rebasing onto the discovered base branch. Ask before any repository rule requires confirmation. Run the rebase only after the required confirmation.

If conflicts occur:

1. Run `git status --short` and list the conflicted files.
2. Stop and ask the user to resolve the conflicts.
3. Continue only after the user confirms resolution.
4. Never auto-resolve code conflicts.

**Completion criterion**: the branch is based on the required base branch, or a conflict is explicitly handed back to the user.

### 3. Prepare the branch and commit if needed

When the worktree is dirty, use the repository's required commit format. If none is documented, propose a concise message based on the change brief and use the format `<issue-or-ticket>: <summary>` only when the repository already uses identifiers in commits.

Before any commit:

- Show the files that will be committed.
- Show the proposed commit message.
- Ask for confirmation.
- Stage only the intended files. Do not stage secrets, environment files, generated artifacts, or unrelated changes.

When on a non-feature branch, propose a branch name using the repository's convention. If none exists, use `feature/<short-kebab-summary>`.

**Completion criterion**: the current branch has the intended committed delta and the worktree is clean, or the user has declined the required commit action.

### 4. Build the change brief

Use `docs/agents/issue-tracker.md` to locate the authoritative issue, specification, or task files. Read all files that the tracker workflow identifies as part of the change brief. Also read linked design or implementation notes when repository guidance requires them.

If the tracker identifies multiple plausible sources, list them and ask the user to choose. If the tracker source is missing or does not explain the branch, ask the user for the issue or specification path rather than inventing requirements.

Compare the change brief with:

- The branch delta and commit messages.
- The complete diff, including renamed and deleted files.
- Tests, documentation, configuration, and infrastructure changes.

Record every changed theme as either described by the change brief or a supporting change requiring rationale.

**Completion criterion**: the change brief, issue identifier, intended implementation areas, tests, documentation, and every supporting change are accounted for.

### 5. Check repository conventions and security

Apply the repository's coding, testing, documentation, and Git conventions to the branch delta. Flag likely violations and ask the user to fix or explicitly override each one before drafting the final pull request.

At minimum, check for:

- Required verification commands and their results.
- New or changed tests corresponding to behavior changes.
- Public API, schema, migration, infrastructure, or configuration impact.
- Unrelated changes or generated files.
- Secrets, credentials, tokens, passwords, private keys, environment contents, or sensitive URLs in the diff.
- New dependencies, if the repository requires approval or existing-use evidence.

Stop and warn the user before creating the pull request if the diff contains likely secrets or sensitive material. Do not print secret values.

**Completion criterion**: every flagged convention or security concern is resolved, explicitly overridden, or blocks pull-request creation.

### 6. Collect evidence

Run the smallest relevant verification commands required by the repository. Prefer execution-based evidence. Capture concise before-and-after evidence when the change fixes an existing behavior:

- **Before**: failing test, reproduced output, or previous observable behavior.
- **After**: passing test, corrected output, or new observable behavior.

For a new feature, use the relevant test or command proving the new behavior. For documentation or configuration changes, use the validation command, rendered result, or structural check. If no meaningful executable evidence exists, say so and name the remaining verification gap.

Do not claim evidence that was not observed.

**Completion criterion**: each behavior claim in the pull-request body has concrete evidence or an explicit verification gap.

### 7. Draft the pull request

Use the repository pull-request template when present. Preserve its headings and checklist semantics. When no template exists, use this structure:

```markdown
## Summary

<the smallest useful visual: a diff sketch, pseudocode block, call tree, file tree, or Mermaid diagram>

<brief explanation in the repository's domain language>

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
- Merge danger with reversibility and blast radius.
- Template checkboxes that the diff and verification can actually prove.

**Completion criterion**: the title and body follow the repository template or generic structure, use the repository's domain language, and account for the entire branch delta.

### 8. Confirm with the user

Print the final title and body. Ask:

```text
Create pull request? (ready / draft / edit / abort)
```

- `ready` or `draft`: continue.
- `edit`: accept inline changes, regenerate the body, and ask again.
- `abort`: stop without pushing or creating anything.

**Completion criterion**: the user has approved the exact title and body and selected ready or draft.

### 9. Push and create the pull request

After confirmation:

1. Follow repository guidance for the remote and branch push.
2. Write the approved body to a temporary file when the CLI supports a body-file option.
3. Use the repository's documented pull-request command. If none exists, use `gh pr create` with the approved title, body, discovered base branch, and `--draft` when requested.
4. If the CLI is unavailable, unauthenticated, or a pull request already exists, print the approved title, body, and an equivalent manual command without exposing secrets.
5. Remove temporary files created by this workflow.

**Completion criterion**: a pull-request URL is returned, or a complete manual fallback is printed. Never claim that a pull request was created without a confirmed result.
