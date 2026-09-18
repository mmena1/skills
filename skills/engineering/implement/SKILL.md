---
name: implement
description: "Implement one approved issue or spec through verification, fixed-point review, commit, and tracker closeout."
disable-model-invocation: true
triggers:
  - user
---

# Implement

Implement exactly one approved issue or spec. The requested ticket defines the delivery scope; its directly referenced approved parent or spec defines the architectural authority.

This is a self-contained worker. Finish the ticket through commits, review, and tracker closeout, but never pull downstream tickets into the change. A parallel orchestrator must give each worker one ticket and an isolated working copy; frontier selection and scheduling stay outside this skill.

## 1. Resolve the work and its authority

Read the repository instructions first. Then read `docs/agents/issue-tracker.md`, `docs/agents/domain.md` when present, the applicable `CONTEXT.md`, and ADRs governing the area.

For a ticket-driven run, require `docs/agents/issue-tracker.md` to define all six implementation operations: implementation-ready state, direct parent or spec lookup, blocker checks, claim, resolve, and frontier promotion. If the file is missing or predates this contract, stop and tell the user to re-run `/setup-matt-pocock-skills` to migrate it. Do not infer missing tracker behavior.

Resolve the user's reference through the configured tracker workflow. For a ticket:

- Fetch its current body, comments, state, labels or status, blockers, and parent relationship.
- Follow the ticket's direct parent or spec reference and read that source completely, including its approval record.
- Treat the ticket's acceptance criteria and boundaries as scope. Treat the approved parent or spec as authority for architecture, public seams, and settled decisions.

For a directly requested spec, read the complete spec and its approval record. If a required source cannot be resolved unambiguously, stop before making changes and report exactly what is missing.

## 2. Pass the start gates

Before any write to the tracker or worktree:

1. Verify the governing parent or spec carries the approval required by the upstream workflow.
2. For a ticket, verify it is open, every blocker is resolved, and it is in the implementation-ready state defined by `docs/agents/issue-tracker.md`. A user may explicitly override a failed ticket-state gate.
3. Require `git status --porcelain` to be empty. Continue from a dirty worktree only when the user explicitly authorizes that exact starting state.
4. Capture `git rev-parse HEAD` as `BASELINE`. Keep this exact commit SHA fixed for the whole run.
5. Resolve the repository's default branch before changing the worktree or tracker. Use this chain: the local symbolic remote `HEAD` for the repository's configured primary remote; the provider/tracker's authoritative default branch (for GitHub, `gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'`); the repository's explicitly documented default branch; then stop if none resolves. A failed or empty provider lookup proceeds to the next fallback; it does not weaken the stop condition. Then inspect the current branch with `git branch --show-current`.
   - If the current branch is the default branch, create and switch to a new branch following the repository's naming and branching conventions before claiming, editing, or committing; never commit implementation work on a default branch such as `main` or `master`.
   - If the current branch is detached, empty, or branch creation fails, stop before changing the worktree or tracker and report the exact Git state and failure.
6. Claim the ticket using the configured tracker workflow when claiming is supported. Claiming is the first write and happens only after the preceding gates pass.

## 3. Separate implementation choices from contradictions

Resolve ordinary deferred implementation choices from existing code patterns and the simplest design that satisfies the ticket. Examples include local naming, private helper shape, or choosing between equivalent established utilities.

Stop when implementation would require changing an approved public seam, contradicting the ticket, parent spec, repository instructions, `CONTEXT.md`, or an ADR, inventing a product or architecture decision, passing an unresolved external gate, or satisfying acceptance criteria that are impossible as written. Leave the ticket open and record a precise report on it through the configured tracker workflow when supported.

## 4. Implement one vertical slice at a time

Apply the `tdd` skill for behavior that can be exercised at a public seam. Public test seams explicitly established by the approved ticket or spec are already confirmed for this run. Record those seams and proceed without asking again. Ask the user only when the implementation materially requires a new or changed public seam.

Stay inside the requested ticket. Do not implement downstream tickets, adjacent cleanup, future extension points, or speculative abstractions. Use each red-green cycle to add only the behavior needed for the current acceptance criterion.

Run the repository's configured targeted checks during development. At the end, run every required check and the full verification the repository or ticket defines. Discover commands from repository instructions and tool configuration. Do not add a typechecker, linter, test runner, or other tooling merely because a generic workflow mentions one.

## 5. Commit, review, and converge

After the implementation and required verification pass:

1. Inspect the diff and stage only files belonging to this ticket.
2. Confirm `git branch --show-current` is non-empty and is not the resolved default branch. If this invariant is false, stop without committing and report it.
3. Commit the implementation to the current non-default branch, referencing the ticket or spec. The commit must exist before review so `<BASELINE>...HEAD` contains the work.
4. Explicitly compose the `code-review` workflow with `BASELINE` and the originating source bundle: the ticket plus its approved parent or spec, or the directly requested spec. If the harness cannot invoke an explicit-only skill as a dependency, read `code-review/SKILL.md` from the active skill root and follow it directly. This instruction authorizes only this named review step; it does not make code review implicitly invokable.
5. Treat documented-standards violations and every missing, partial, incorrect, or out-of-scope Spec finding as blocking. Smell-baseline findings are advisory unless they demonstrate a documented or correctness violation.
6. Fix every blocking finding that is within the approved scope, rerun the affected targeted checks and required final verification, commit the fixes on the same non-default branch, then repeat review against the same `BASELINE` and source bundle.

Continue the loop while findings produce actionable, in-scope progress. If a finding exposes a product or architecture decision, external gate, impossible criterion, or contradiction, use the stop path in step 3 instead of improvising.

## 6. Close out

Success requires all acceptance criteria satisfied, required verification passing, no blocking review findings, and a clean worktree containing only committed ticket work.

For a ticket run, perform the configured tracker closeout exactly as `docs/agents/issue-tracker.md` describes. Local tickets may be resolved and their frontier refreshed. For GitHub issues, record the implementation commit and verification evidence, leave the issue open, and record the PR/merge handoff obligation, including the issue number and required `Closes #<issue>` reference. The separately authorized PR/merge owner owns adding and verifying that reference and, after merge, running the tracker's post-merge reconciliation to confirm auto-closure and refresh the frontier. Do not promote GitHub-dependent frontier tickets before that reconciliation. Report the ticket or spec, approved authority, `BASELINE`, commits, verification, review result, and any newly available frontier work.

If the run stops, leave the ticket open and report the completed work, current commits, failed or unrun checks, and the precise decision, gate, contradiction, or impossible criterion. Never claim completion from partial evidence.

Do not push, merge, or create a pull request without separate user authorization.
