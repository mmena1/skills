# Ledger

The ledger is the coordinator's durable memory. Worker reports are inputs; Git and canonical tracker files remain authoritative.

## Workspace

Use:

```text
.scratch/<feature>/sdd/
├── lock/
└── <run-id>/
    ├── ledger.md
    ├── ticket-graph.md
    ├── chunk-graph.md
    ├── packets/
    ├── reports/
    └── reviews/
```

Create the feature lock atomically before changing ticket state. Its owner record contains run ID, repository identity, caller branch, starting SHA, and session identity when available. Never take over a lock whose run can still be verified; stop and report it.

The first line of `ledger.md` identifies the canonical feature path and run ID. Never trust another feature's ledger.

## Required state

Record:

- exact invocation directory, caller worktree root/classification, canonical common Git directory, caller branch, and starting SHA;
- target common Git directory and proof it matches the caller repository;
- selected worktree root, creation owner/mechanism, integration branch/worktree/head, and cleanup mechanism;
- canonical PRD and ticket paths plus source hashes;
- validated ticket DAG and completed-blocker evidence;
- derived chunk DAG, grouping rationale, architectural seam, and forecast size;
- ticket and chunk status;
- worker/subagent identity, worktree, branch, base/head, and packet hash;
- worker commit to ticket mapping;
- raw/reviewable churn and every `CONTINUE`/`SEAL_CHUNK` decision;
- review rounds, findings, fixup commits, approvals, and parked findings;
- source commit to final integrated commit mapping;
- setup command/outcome, baseline command/outcome/classification, and post-setup tracked status for every integration, probe, and chunk worktree;
- every authorized baseline repair with exact failure evidence, owning ticket, quoted explicit owning requirement, and final green evidence;
- focused and broad verification commands and outcomes;
- every required deterministic validator's artifact scope and hash, execution tree SHA, exact command, resolved executable path, validator/runtime version fingerprint, worker or coordinator executor, exit code, PASS/FAIL/BLOCKED result, output path, and output hash;
- rulings in `Ruling: <decision> — <why> — <cost if wrong>` form;
- retained resources and cleanup state.

Run states:

```text
preflight | running | final-review | completed
stopped:<hard-gate-reason>
```

Write the current run state whenever a phase changes or a hard gate stops execution; never leave `preflight` after workers dispatch. A stopped run remains resumable while its verified lock and resources exist.

Ticket states:

```text
ready | assigned | implemented | reviewing | approved | integrated | completed
needs-info | ready-for-human | dependency-blocked
```

Chunk states:

```text
planned | running | sealed | reviewing | approved | integrated
parked | dependency-blocked
```

Canonical ticket files remain `ready-for-agent` while the ledger holds the exclusive claim. Write `completed`, checked acceptance criteria, and final SHA only after final history is stable and verification passes. Use `needs-info` for missing product/source decisions and `ready-for-human` after bounded technical repair fails.

## Resume

Run this procedure immediately after caller/repository identity verification and before selecting or creating any run resource. On repeated invocation:

1. Locate the matching unfinished ledger and verify repository identity, feature path, caller branch, and starting SHA.
2. Verify every recorded branch, worktree, base/head relationship, commit, clean/dirty state, and integrated mapping directly from Git. A worktree that predates the ledger or lacks recorded creation evidence is external and never run-managed.
3. Re-hash source tickets, PRD, context packets, and governance snapshots.
4. Verify every deterministic-validator output path exists and matches its recorded hash. Invalidate stale packets, reviews, and validator evidence when output is missing or mismatched, or when the source tree, artifact, exact command, resolved executable, or validator/runtime fingerprint changed. Re-run every invalidated required validator before approval.
5. Reattach to running subagents when the harness supports it; otherwise classify their worktree from verified Git state.
6. Recompute the frontier from integrated tickets, never from optimistic worker status.
7. When the prior stop was a baseline failure, rerun its exact command and smallest failing selection, then reclassify it against the current chunk's full ticket under the current protocol. If a quoted acceptance criterion or other explicit normative requirement directly owns the exact failure, record `AUTHORIZED_BASELINE_REPAIR`, reuse the verified clean run-owned chunk worktree, and include the requirement plus red evidence in its new packet. Otherwise preserve `stopped:unrelated-baseline-failure`.
8. Verify whether the recorded isolation/permission probe is valid for the current harness, session, worker permissions, and repository state. If it is missing or stale, remain in `preflight` and run a new disposable probe. Transition the run to `running` only after the probe and every other applicable hard gate pass.

Do not redispatch a ticket with verified committed work. Do not mark uncommitted or unreviewed work complete.

## Partial completion

When one chunk parks, mark only its transitive dependents `dependency-blocked`. Continue every chunk whose external blockers remain integrated. After no more chunks are runnable, final-review the successfully integrated scope before publishing final ticket SHAs.

## Cleanup

After final success, retain a compact ledger summary containing final graph, commits, verification, rulings, and any incomplete work. Remove bulky packets and reports only when their content is represented by stable Git history and the summary.

Remove only clean worktrees and temporary branches created by this run whose commits are proven integrated. A native manager removes worktrees it owns. For Git-owned worktrees, remove the worktree before deleting its checked-out branch. Preserve failed, dirty, external, unreviewed, or unintegrated worktrees and report exact paths and recovery commands. Release the lock last.
