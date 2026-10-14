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
- **Ticket set**: the tickets the branch delta implements, established from admissible evidence, validated commit attribution or supporting-change rationales, and tracker checks. A branch may carry one ticket or several tickets implemented sequentially on it, for example by successive `/implement` runs.
- **Admissible evidence**: what establishes that the branch delta implements a ticket. Either (a) a tracker implementation record of a successful closeout, such as a completed `/implement` closeout, whose complete recorded commit set is present in the branch delta, or (b) commits in the branch delta that reference the ticket, verification output this workflow observes, and explicit user confirmation that those commits implement that ticket. A stop report, a failed or partial record, or a closeout with any recorded commit missing from the branch delta only makes the ticket a candidate, as does a commit-message reference alone; neither is admissible evidence. When history was rewritten, use route (b).
- **Change brief**: the authoritative explanation of the work, assembled for each ticket in the ticket set from the configured issue tracker, linked issue or specification files, repository guidance, commits, and the diff.
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

**Completion criterion**: the configured primary remote, base branch, current branch, clean worktree, committed branch delta, behind/ahead state, existing pull-request status, repository obligations, and candidate ticket references are known.

### 2. Build the ticket set and change brief

Use `docs/agents/issue-tracker.md` to locate the authoritative issue, specification, or task files. Collect candidate tickets from tracker implementation records and from ticket references in the branch delta's commit messages. Read each candidate's files that the tracker workflow identifies as part of the change brief, its state, its blockers, and its implementation records. Also read linked design or implementation notes when repository guidance requires them.

Admit a candidate to the ticket set only with admissible evidence. For a candidate without such a successful closeout, run the repository's relevant verification now, show its output with the referencing commits, and ask the user to confirm that those commits implement that ticket; without that confirmation, the candidate is not admitted. List every candidate that still lacks admissible evidence, such as a referenced ticket with nothing that establishes its implementation, as an unclear source for the user to resolve, include, or exclude. Resolve every unclear source before drafting: inclusion requires admissible evidence, and exclusion requires an explicit user decision; excluded commits still need supporting-change rationales. Missing evidence or user silence never admits a candidate. If no candidate is admitted, or the tracker source is missing or does not explain the branch, ask the user for the issue or specification path rather than inventing requirements.

Attribute every commit in the branch delta to the admitted tickets whose admissible evidence names it. Report a commit attributed to more than one ticket and ask the user to confirm that attribution explicitly. Report every unattributed commit as a supporting change with a stated rationale, asking the user for the rationale when the delta and change briefs do not supply one.

Validate closure across the whole pull request. For every admitted ticket, every unresolved blocker must itself be in the ticket set: on GitHub, unresolved means open; on a local tracker, it means not in its resolved state. Otherwise, stop before drafting and report the ticket, the unresolved blocker, and that merging would resolve a dependent before its blocker. Continue only when the user explicitly overrides that blocker, and report the override in the body. Because each ticket's own blockers are checked, a chain such as A, then B, then C validates only when every earlier ticket is in the set or already resolved.

Re-validate every branch-satisfied relation in the pull request against the final head, in addition to that closure validation. A relation is a blocker that an admitted ticket's implementation record lists as branch-satisfied. Each such blocker that is still unresolved must itself be in the ticket set, and no blocker override applies to it. Validate it as the tracker's branch-satisfied blockers operation defines, including ancestry, intactness, and revert detection, counting the recorded commits of the admitted tickets linked through these relations as in-chain. This catches a blocker reverted or rewritten after a later ticket was built on it, even when each direct check passed when it ran. When any relation fails, stop before drafting and report the dependent, the blocker, the failed condition, and the commits involved; do not repair it here.

Present the established ticket set, each ticket's admissible evidence, commit attribution, supporting changes, and any explicit source exclusions. When admissible evidence, attribution or supporting-change rationales, and tracker checks unambiguously establish the set, proceed without ticket-set confirmation, for both single-ticket and multi-ticket branches. Request targeted input only for unresolved evidence, attribution, or rationale; once resolved, proceed without another acknowledgment of the set. These checks do not authorize pushing or creating a pull request; step 6 still requires approval of the exact title and body.

Capture the tracker-defined PR/merge lifecycle for each ticket, including required issue references, close directives, and handoff or post-merge reconciliation steps. Do not close an issue directly unless the configured tracker workflow explicitly assigns that action to this workflow.

- **GitHub**: carry one independent closing keyword per issue, preferably on separate lines, such as `Closes #<a>` and `Closes #<b>`, because GitHub applies a shared keyword such as `Closes #<a>, #<b>` only to the first issue.
- **Local Markdown**: generate no GitHub closing directive. Reference each ticket by its tracker identifier or path, as the tracker requires; resolution stays wherever the local tracker defines it.

Closure is never assumed. Prepare the closure handoff for the PR/merge owner as the tracker defines it:

- **GitHub**: when the base branch is not the repository's default branch, state that closing keywords will not close the issues on merge, and that closure needs a later default-branch merge or the tracker's explicit close step. When the repository's automatic issue closure cannot be confirmed as enabled, mark auto-closure as unverified. In every case, instruct the PR/merge owner to verify each issue's closed state after merge, close any issue that did not close through the tracker's lifecycle, and invoke `/reconcile <ticket-ref>` once per ticket only after that ticket is verified closed.
- **Local Markdown**: state each ticket's current tracker status and leave its resolution and frontier refresh to the tracker's configured resolve and frontier rules, which may already have run at implementation closeout. The merge carries no closed-state, auto-closure, or post-merge `/reconcile` requirement.

With one admitted GitHub issue, the body keeps its single-ticket shape: one close directive, one closure verification, and one `/reconcile`.

Compare each ticket's change brief with:

- The branch delta and commit messages.
- The complete diff, including renamed and deleted files.
- Tests, documentation, configuration, and infrastructure changes.

Record every changed theme under the ticket whose change brief describes it, or as a supporting change requiring rationale.

**Completion criterion**: the ticket set established from admissible evidence, every unclear source resolved, each ticket's admissible evidence and change brief, every commit's attribution or supporting-change rationale, PR-wide blocker validation or each reported override, every branch-satisfied relation re-validated at the final head, each ticket's tracker-defined PR/merge lifecycle and closure handoff, intended implementation areas, tests, documentation, and every supporting change are accounted for.

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

<tracker-required PR/merge references and closure handoff from step 2>

## Evidence

- **Before:** <failing or previous result, when meaningful>
- **After:** <passing or current result>

## Merge Danger

**Door:** <one-way or two-way>

**Blast Radius:** <one-word classification>

<brief explanation when the change is hard to reverse, destructive, changes a public contract, or has broad impact>
```

When the ticket set has more than one ticket, group the changed themes and evidence under one subheading per ticket within these sections.

Keep prose brief. Place each visual next to the text it supports. Choose the smallest representation that makes ownership, order, state, or data flow clear:

- Pseudocode for algorithms or state transitions.
- A call tree for runtime control flow.
- A shallow file tree for ownership or broad refactors.
- Mermaid for component interaction or data flow.
- A diff sketch when the surrounding shape already exists and the change itself is the point.

Include:

- A title using the repository's required format, based on the change briefs of the ticket set.
- A concise summary of the intended result.
- Grouped changed themes from the diff.
- Every supporting change with its rationale and appropriate depth.
- Verification evidence and gaps.
- The tracker-required PR/merge references and closure handoff from step 2.
- Every confirmed multi-ticket commit and every explicit blocker override.
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
