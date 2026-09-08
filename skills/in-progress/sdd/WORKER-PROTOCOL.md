# Worker protocol

The coordinator constructs a fresh prompt for each chunk. A worker receives no parent conversation history and no unrelated ticket bodies.

## Brief

Include every field:

```text
Run ID:
Chunk ID:
Worktree: <absolute path>
Expected branch:
Base SHA:
Integration SHA containing all external blockers:
Included tickets, in order: <full bodies and acceptance criteria>
Applicable PRD constraints:
Direct-blocker outcomes and integrated SHAs:
Context manifest: <absolute path>
Setup command and coordinator evidence:
Baseline command and coordinator evidence:
Baseline classification: GREEN | AUTHORIZED_BASELINE_REPAIR
Authorized baseline failure, owning ticket, and quoted owning requirement: <evidence or NONE>
Focused verification commands:
Required deterministic validators:
Commit-message rule and ticket ID:
Report path:
```

State that the worker owns only the listed worktree and tickets. The coordinator owns branches, worktrees, integration, ticket files, and the ledger.

## Start gate

Before editing, the worker uses the execution tool's `workdir` field rather than a shell `cd`, then reports:

```text
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
```

Return `WRONG_WORKTREE` without editing when root, branch, or base differs. Return `NEEDS_CONTEXT` when the packet or governance manifest is missing, contradictory, or insufficient to choose a defensible seam.

Verify the recorded setup and baseline evidence belongs to this exact worktree and HEAD. Run any pending repository-prescribed setup, then recheck root, branch, HEAD, and tracked status. When the baseline is `GREEN`, return `BASELINE_FAILED` without editing if it is now red. When the packet records `AUTHORIZED_BASELINE_REPAIR`, rerun the smallest failing selection and continue only when it reproduces the same recorded symptom and the quoted explicit owning requirement directly owns it; treat that red result as the first failing test of the ticket. A different failure or missing ownership evidence returns `BASELINE_FAILED` without editing.

## Scope

The worker may:

- read and edit files beneath its assigned worktree;
- run repository-prescribed setup and verification;
- use `git status`, `diff`, `log`, `show`, and `rev-parse`;
- stage its own work and create ticket commits or ticket-targeted fixup commits.

The worker leaves branch creation/switching, worktree management, merging, rebasing, resetting, stashing, cleaning, pushing, and publication to the coordinator. It does not edit canonical tickets, the parent ledger, another checkout, or `.sdd-context/`.

Use raw `git <subcommand>` with the execution tool's workdir so narrow permission prefixes apply. Do not wrap Git in `cd`, `sh -c`, or `git -C`.

## Implement tickets

Read the governance inventory, scan every ADR entry for applicability, and read every possibly applicable decision in full. Read the supplied `/tdd` and `/codebase-design` references.

For each ticket, in order:

1. Reconcile the ticket with its PRD constraints and blocker outcomes.
2. Name the existing or ticket-authorized public seams under test. If no defensible seam exists, return `NEEDS_CONTEXT`.
3. Work red → green in vertical slices: one behavioral test, minimal implementation, repeat.
4. Apply deep-module vocabulary when changing an interface, seam, adapter, or ownership boundary.
5. Run the smallest relevant verification until green.
6. Run every required deterministic validator applicable to the changed artifacts. If a tool or permission denial blocks one, preserve the exact command and denial as coordinator work; manual inspection does not satisfy it.
7. Self-review the ticket diff against every acceptance criterion, governance rule, and scope boundary.
8. Stage only the ticket's implementation and commit it with the required repository ticket ID.
9. Record the ticket commit SHA and verification evidence.
10. Measure raw and reviewable chunk churn.
11. Return `CONTINUE` or `SEAL_CHUNK` before starting the next ticket.

Do not start a ticket after `SEAL_CHUNK`. Return its complete unstarted suffix to the coordinator.

## Review repairs

The coordinator supplies findings after the chunk review. For each accepted finding:

1. Identify the owning ticket commit.
2. Reproduce the issue where possible.
3. Make the smallest complete correction and run focused verification.
4. Split changes by ticket when findings span tickets.
5. Commit each repair with `git commit --fixup=<owning-ticket-sha>`.

Do not amend or autosquash. The coordinator owns history normalization. If one correction genuinely has no single owning ticket, return `NEEDS_RULING` with the competing ownership choices and cost of each.

## Report

Write the full report to the assigned report path and return a short structured summary:

```text
STATUS: COMPLETE | COMPLETE_WITH_BLOCKED_VALIDATORS | SEALED | BASELINE_FAILED | NEEDS_CONTEXT | NEEDS_RULING | FAILED
WORKTREE: <absolute path>
BRANCH: <name>
BASE: <sha>
HEAD: <sha>
TICKETS_COMPLETED: <ids>
TICKETS_UNSTARTED: <ids>
COMMITS:
  - <sha> <subject> [ticket id]
SETUP: <command or NONE>: PASS | FAIL
BASELINE: <command>: PASS | AUTHORIZED_RED | FAIL
AUTHORIZED_BASELINE_RESULT: FIXED | UNCHANGED | NONE
VERIFY:
  - <command>: PASS | FAIL
VALIDATORS:
  - <name>: <exact command>: <artifact hash>: <tree SHA>: <executable/runtime fingerprint>: <exit code>: PASS | FAIL: <output path/hash>
BLOCKED_VALIDATORS:
  - <name>: <exact command>: <artifact hash>: <tool or permission denial> | NONE
RAW_CHURN: <number>
REVIEWABLE_CHURN: <number>
DECISION: CONTINUE | SEAL_CHUNK
DECISION_REASON: <one line>
STATUS_PORCELAIN: <exact output or CLEAN>
REPORT: <absolute path>
```

Never claim `COMPLETE` with uncommitted implementation changes, a failing or blocked required check, or an unchecked acceptance criterion. Use `COMPLETE_WITH_BLOCKED_VALIDATORS` only when implementation and all runnable checks are complete and every blocked validator is precisely handed to the coordinator.
