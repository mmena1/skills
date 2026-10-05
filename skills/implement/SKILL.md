---
name: implement
description: "Implement one approved issue or spec through verification, fixed-point review, commit, and tracker closeout."
disable-model-invocation: true
triggers:
  - user
---

# Implement

Implement exactly one approved issue or spec. The requested issue defines delivery scope and uses either its directly referenced approved parent/spec for architectural authority or, on a tracker that supports standalone authority, the issue itself when it carries a complete, trusted Agent Brief as `docs/agents/issue-tracker.md` defines.

This is a self-contained worker. Finish the ticket through commits, review, and tracker closeout, but never pull downstream tickets into the change. A parallel orchestrator must give each worker one ticket and an isolated working copy; frontier selection and scheduling stay outside this skill.

## 1. Resolve the work and its authority

Read the repository instructions first. Then read `docs/agents/issue-tracker.md`, `docs/agents/domain.md` when present, the applicable `GLOSSARY.md` (or the legacy `CONTEXT.md` when it is absent), and ADRs governing the area.

For a ticket-driven run, require `docs/agents/issue-tracker.md` to define all six implementation operations: implementation-ready state, direct parent or spec lookup, blocker checks, claim, resolve, and frontier promotion. If the file is missing or predates this contract, stop and tell the user to re-run `/setup-skills` to migrate it. Do not infer missing tracker behavior. The tracker's standalone authority mode matters only for a parentless ticket, as below; a parent-backed ticket never depends on it, even when that configuration is stale.

Resolve the user's reference through the configured tracker workflow. For a ticket:

- Fetch its current body with author identity, comments with author identity and creation time, state, labels or status, blockers, and parent relationship.
- If the issue has a direct parent/spec reference or native parent, follow it and read it completely, including its approval record. A missing, unapproved, or unresolvable referenced parent fails closed; never fall back to standalone authority, even when the issue carries an Agent Brief.
- If it has no parent/spec, apply the standalone authority mode `docs/agents/issue-tracker.md` states:
  - **Parent-only**: the file states that standalone authority is unsupported, or that every implementation ticket has or requires a parent/spec. Stop and report that this tracker requires a parent/spec and the ticket has none. Do not look for an Agent Brief, add one, or send the user to `/setup-skills`; the fix is to give the ticket its governing parent/spec.
  - **Stale**: the file still defines the retired standalone authority comment record (a `## Standalone implementation authority` comment), claims standalone support without the complete Agent Brief rule (completeness, trusted sources, precedence, and fail-closed parent handling), states no mode at all, or states both modes. Stop and tell the user to re-run `/setup-skills` to migrate it; do not guess which rule applies.
  - **Standalone-capable**: the file defines the complete Agent Brief rule. Resolve the issue's Agent Brief as that file defines: the newest complete trusted brief comment when one exists, otherwise the complete trusted issue-body brief. A brief is trusted only when its author (the comment author, or the issue author for the body) is a human account with effective `write` (including `maintain`) or `admin` repository permission; reject bots, lower permissions, and permission lookups that fail. `author_association` is supplemental context only. Recognize a brief by its completeness and author, never by a `/triage` disclaimer or other workflow marker. The issue is standalone-authoritative only when that brief exists and the issue is in the implementation-ready state; the ready label alone, an incomplete or untrusted brief, conversation history, or a historical standalone authority comment is not authority.
- Treat the issue's acceptance criteria and boundaries as scope. For parent-backed work, treat the approved parent/spec as authority for architecture, public seams, and settled decisions. For standalone work, the resolved Agent Brief is the authority; do not require or invent a synthetic spec.

For a directly requested spec, read the complete spec and its approval record. If a required source cannot be resolved unambiguously, stop before making changes and report exactly what is missing.

## 2. Pass the start gates

Before any write to the tracker or worktree:

1. Verify either that the governing parent/spec carries the approval required by the upstream workflow, or, on a standalone-capable tracker, that the parentless issue carries the complete, trusted Agent Brief required by `docs/agents/issue-tracker.md` and is in the implementation-ready state. A user override of the ticket-state gate below waives neither that brief nor the implementation-ready state standalone authority requires.
2. For a ticket, verify it is open, every blocker is resolved, and it is in the implementation-ready state defined by `docs/agents/issue-tracker.md`. A user may explicitly override a failed ticket-state gate.
3. Require `git status --porcelain` to be empty. Continue from a dirty worktree only when the user explicitly authorizes that exact starting state.
4. Capture `git rev-parse HEAD` as `BASELINE`. Keep this exact commit SHA fixed for the whole run.
5. Resolve the repository's default branch before changing the worktree or tracker. Use this chain: the local symbolic remote `HEAD` for the repository's configured primary remote; the provider/tracker's authoritative default branch (for GitHub, `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`); the repository's explicitly documented default branch; then stop if none resolves. A failed or empty provider lookup proceeds to the next fallback; it does not weaken the stop condition. Then inspect the current branch with `git branch --show-current`.
   - If the current branch is the default branch, create and switch to a new branch following the repository's naming and branching conventions before claiming, editing, or committing; never commit implementation work on a default branch such as `main` or `master`.
   - If the current branch is detached, empty, or branch creation fails, stop before changing the worktree or tracker and report the exact Git state and failure.
6. Claim the ticket using the configured tracker workflow when claiming is supported. Claiming is the first write and happens only after the preceding gates pass.

## 3. Separate implementation choices from contradictions

Resolve ordinary deferred implementation choices from existing code patterns and the simplest design that satisfies the ticket. Examples include local naming, private helper shape, or choosing between equivalent established utilities.

Stop when implementation would require changing an approved public seam, contradicting the ticket, parent spec, repository instructions, the domain glossary, or an ADR, inventing a product or architecture decision, passing an unresolved external gate, or satisfying acceptance criteria that are impossible as written. Leave the ticket open and record a precise report on it through the configured tracker workflow when supported.

## 4. Implement one vertical slice at a time

Apply the `tdd` skill for behavior that can be exercised at a public seam. Public test seams explicitly established by the approved ticket or spec are already confirmed for this run. Record those seams and proceed without asking again. Ask the user only when the implementation materially requires a new or changed public seam.

Stay inside the requested ticket. Do not implement downstream tickets, adjacent cleanup, future extension points, or speculative abstractions. Use each red-green cycle to add only the behavior needed for the current acceptance criterion.

Run the repository's configured targeted checks during development. At the end, run every required check and the full verification the repository or ticket defines. Discover commands from repository instructions and tool configuration. Do not add a typechecker, linter, test runner, or other tooling merely because a generic workflow mentions one.

## 5. Commit, review, and converge

After the implementation and required verification pass:

1. Inspect the diff and stage only files belonging to this ticket.
2. Confirm `git branch --show-current` is non-empty and is not the resolved default branch. If this invariant is false, stop without committing and report it.
3. Commit the implementation to the current non-default branch, referencing the ticket or spec. The commit must exist before review so `<BASELINE>...HEAD` contains the work.
4. Explicitly compose the `implementation-review` workflow with `BASELINE` and the originating source bundle: the issue plus its approved parent/spec, the issue plus its resolved Agent Brief, or the directly requested spec. If the harness cannot invoke an explicit-only skill as a dependency, read `implementation-review/SKILL.md` from the active skill root and follow it directly. This instruction authorizes only this named review step; it does not make implementation review implicitly invokable.
5. Treat documented-standards violations and every missing, partial, incorrect, or out-of-scope Spec finding as blocking. Smell-baseline findings are advisory unless they demonstrate a documented or correctness violation.
6. Fix every blocking finding that is within the approved scope, rerun the affected targeted checks and required final verification, commit the fixes on the same non-default branch, then repeat review against the same `BASELINE` and source bundle.

Continue the loop while findings produce actionable, in-scope progress. If a finding exposes a product or architecture decision, external gate, impossible criterion, or contradiction, use the stop path in step 3 instead of improvising.

## 6. Close out

Success requires all acceptance criteria satisfied, required verification passing, no blocking review findings, and a clean worktree containing only committed ticket work.

For a ticket run, perform the configured tracker closeout exactly as `docs/agents/issue-tracker.md` describes. Local tickets may be resolved and their frontier refreshed. For GitHub issues, record the implementation commit and verification evidence, leave the issue open, and record the PR/merge handoff obligation, including the issue number and required `Closes #<issue>` reference. The separately authorized PR/merge owner owns adding and verifying that reference, confirming auto-closure, and invoking `/reconcile <ticket-ref>` to refresh the frontier. Do not promote GitHub-dependent frontier tickets before that reconciliation. Report the ticket or spec, approved authority, `BASELINE`, commits, verification, review result, and any newly available frontier work.

If the run stops, leave the ticket open and report the completed work, current commits, failed or unrun checks, and the precise decision, gate, contradiction, or impossible criterion. Never claim completion from partial evidence.

Do not push, merge, or create a pull request without separate user authorization.
