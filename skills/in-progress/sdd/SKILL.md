---
name: sdd
description: Implement a feature's ticket graph with fresh subagents in isolated worktrees.
disable-model-invocation: true
triggers:
  - user
argument-hint: "<feature-directory-or-ticket>"
permissions:
  allow:
    - Exec(git status)
    - Exec(git diff)
    - Exec(git log)
    - Exec(git show)
    - Exec(git rev-parse)
    - Exec(git branch --show-current)
    - Exec(git add)
    - Exec(git commit)
---

# Subagent-Driven Development

Execute local `/to-tickets` output as **chunks**: architecturally cohesive groups of tickets, each implemented by a fresh worker in an isolated worktree. Tickets remain the acceptance and commit unit; chunks are the context, worktree, and review unit.

**Continuous execution.** After preflight, work every runnable chunk without progress check-ins. Make reversible rulings where the sources are silent, record them in the ledger, and continue. Stop only for an irreversible operation, a security-sensitive action, an external side effect, failed isolation/permission preflight, or source material so broken that every path is a guess.

**Authority:** explicit user instruction → PRD → ticket → current behavior → recorded ruling.

**Hard gates are not rulings.** A missing sibling protocol, dirty caller checkout, detached caller HEAD, unrelated baseline failure, stale lock, unverified worktree, denied worker permission required for editing, committing, or non-delegable verification, unresolved required deterministic validator, changed caller branch/SHA, or load-bearing review finding stops the run. A denial limited to a delegable deterministic validator remains unresolved only when the coordinator's exact-command fallback also fails or is denied. Never record a ruling to bypass a hard gate.

The frontmatter permissions are additive grants for background workers, not the coordinator's complete command list. Coordinator-owned worktree, branch, rebase, integration, and cleanup operations inherit the session's normal permission policy and prompt when required.

Every linked protocol file is required. Resolve `CHUNKING.md`, `WORKER-PROTOCOL.md`, `REVIEW-PROTOCOL.md`, `CONTEXT-PACKET.md`, and `LEDGER.md` relative to this skill's reported source/base directory, never relative to the target repository. Read each before its phase; a missing or unreadable protocol stops preflight.

## 1. Resolve the run

Require exactly one feature directory or ticket path. A feature directory contains `PRD.md` and `issues/*.md`; a ticket path runs only that ticket. Read complete ticket bodies and comments.

For directory mode, parse the current blocker graph rather than trusting filenames or numbering. Reject missing blocker references, duplicate ticket IDs, and cycles. Treat a completed blocker as satisfied only when its recorded commit is an ancestor of the captured base. A focused ticket with incomplete blockers stops and reports them.

Read [CHUNKING.md](CHUNKING.md) and keep the validated ticket sources in memory. Do not generate a run ID, create a run workspace, contract a new chunk graph, or write a manifest until Step 2 determines whether this invocation resumes an existing ledger or starts a fresh run. A resume verifies and updates its recorded graph; a fresh run derives and writes a new graph. Do not rewrite or merge the source tickets.

## 2. Preflight

The **caller worktree** is `git rev-parse --show-toplevel` evaluated from the directory in which the user invoked `/sdd`. The target repository is the repository containing the canonical input path. Canonicalize both repositories' `git rev-parse --git-common-dir` values and stop unless they match. Record `--git-dir`, `--git-common-dir`, and `--show-superproject-working-tree` so the caller is classified as primary checkout, linked worktree, or submodule. Never select the first entry from `git worktree list`, the common Git directory, or this skill's source checkout as the caller. Capture caller root, branch, and starting SHA from that exact worktree. Require a named branch and a clean tracked caller checkout; expected ignored tracker files do not block the run.

Before selecting a worktree mechanism or creating any run resource, look for a matching unfinished ledger and verify its feature lock. When one exists, create no new persistent run branch, worktree, run ID, or ledger; follow [LEDGER.md](LEDGER.md)'s resume procedure using the recorded resources and rerun evidence that is missing or stale. A disposable isolation/permission probe may be recreated when its evidence is not valid for the current harness, session, permissions, and repository state. A lock without a verifiable matching ledger is a hard stop. For a fresh run, acquire the feature lock atomically and create the ledger with state `preflight` before creating any worktree, so every later failure has a durable record.

For a fresh run, choose one worktree creation mechanism. Prefer a harness-native manager only when it supports explicit paths, named branches, exact base SHAs, concurrent worktrees, coordinator verification, retained failures, and manager-owned cleanup; otherwise use Git. Record the mechanism and owner. Resolve one storage root from explicit user instruction, trusted repository governance, an existing approved `.worktrees/` or `worktrees/`, then `.worktrees/` by default. When the caller is linked, place the root outside that linked checkout so removing it cannot recursively remove SDD worktrees.

Before creating any worktree path, add the exact selected root and `.sdd-context/` to an existing project-local ignore mechanism or `.git/info/exclude`, then prove each selected path independently with `git check-ignore`; never let an ignored unselected candidate satisfy the check. Only then create a new unique `sdd/<run-id>/` child and dedicated integration branch/worktree from the starting SHA; leave the caller checkout untouched. A pre-existing child path or worktree is never run-managed unless the matching verified ledger proves this run created it.

Discover repository-prescribed setup and fast baseline commands from project guidance rather than a generic language matrix. Run setup and baseline inside the integration worktree, then verify root, branch, HEAD, and clean tracked status again. Repeat that gate in every probe and chunk worktree before edits. Setup changing tracked files is a hard stop.

Classify every red baseline before stopping:

1. Capture the exact command, failing tests, symptom, and report paths; rerun the smallest failing selection to confirm it is red-capable.
2. Compare the failure against the current chunk's full tickets and applicable PRD constraints, not merely the chunk title or the commit that introduced it.
3. Classify `AUTHORIZED_BASELINE_REPAIR` only when a quoted acceptance criterion or other explicit normative requirement in the owning ticket directly requires correcting that exact failure, replacing that exact flaky assertion, or making that exact behavior green. Record the owning ticket and quoted requirement, then continue the remaining preflight gates. Section 4 includes the red evidence in the worker packet when it dispatches the chunk; the worker must turn it green before completion.
4. Classify every other baseline failure `UNRELATED_BASELINE_FAILURE`, record `stopped:unrelated-baseline-failure`, and stop. Similar files, adjacent behavior, or a convenient cleanup opportunity do not establish authorization.

Before claiming a ticket, require isolation/permission probe evidence valid for the current harness, session, worker permissions, and repository state. A fresh run always probes; a resumed run probes when prior evidence is missing or stale. In a disposable worktree, dispatch one write-capable background worker to create, stage, commit, and report a probe file using only the granted Git commands, then independently verify its root, branch, commit, and status. Include the chosen worker verification command when practical. Remove only the probe worktree and branch created by this invocation. Any denied write, test, `git add`, or `git commit` stops preflight without changing ticket state. Set the run state to `running` only after every applicable preflight gate passes.

## 3. Build context packets

Read [CONTEXT-PACKET.md](CONTEXT-PACKET.md). Snapshot repository governance into each worktree, but seed a worker's active context only with its chunk: included tickets, applicable PRD and ADR constraints, direct-blocker outcomes, verification rules, and starting Git state. Never send the complete feature plan to every worker.

Load the `/tdd` and `/codebase-design` references into the packet. TDD governs the red-green implementation loop; codebase-design governs module interfaces, seams, adapters, and ownership boundaries. If the ticket and applicable context do not establish a pre-agreed test seam, stop with `NEEDS_CONTEXT` before writing a test; do not treat naming a seam as confirmation.

## 4. Work the chunk frontier

A chunk is runnable when every external blocker is successfully integrated. Dispatch at most three write-capable implementation workers concurrently, one branch and worktree per chunk, following [WORKER-PROTOCOL.md](WORKER-PROTOCOL.md).

Workers own their source commits. The coordinator creates and verifies branches/worktrees, but does not author implementation commits. Each ticket gets a distinct commit; review repairs get ticket-targeted fixup commits.

When a worker returns:

1. Verify the reported root, branch, base/head range, commits, changed paths, context snapshot, and worktree status from the coordinator.
2. Reject uncommitted work, writes outside the assigned worktree, unexpected branch movement, or unmapped changes.
3. Reconcile the coordinator-captured changed paths and artifact types against the packet's validator inventory. Extend the ledger inventory for any newly applicable validator omitted by prediction; when the worker needs another turn, send an immutable validator addendum rather than rewriting its original packet.
4. For every required deterministic validator without current PASS evidence, run the exact command from the coordinator in the assigned worktree and record its artifact hash, execution tree, executable/runtime fingerprint, exit code, and output. A failed check, unavailable validator, or denied coordinator permission leaves the chunk unapproved and stops its dependency path. Manual inspection never substitutes for a required executable validator.
5. Record actual raw and reviewable churn plus the worker's `CONTINUE` or `SEAL_CHUNK` decisions.
6. Return an unstarted suffix to the scheduler and recompute the chunk graph; early sealing is successful execution.
7. Run the chunk review before integration.

## 5. Review and repair

Follow [REVIEW-PROTOCOL.md](REVIEW-PROTOCOL.md). The root coordinator invokes `/code-review` against the immutable chunk base/head and the chunk manifest. This produces fresh Standards and Spec reviewers without requiring nested subagents.

Resume the original worker for repair rounds one and two. If a third is required, dispatch a fresh escalation worker with the packet, current diff, and unresolved findings. Every repair commit uses `git commit --fixup=<owning-ticket-commit>`; split cross-ticket repairs by owning ticket. After three rounds, park the chunk if any load-bearing finding remains.

Run no more than two chunk review pairs concurrently. Continue unrelated chunks when one fails; park only that chunk and its transitive dependents.

## 6. Integrate approved chunks

Before integration, the coordinator autosquashes ticket-targeted fixups on the temporary chunk branch and verifies that the tree content did not change. Integrate rewritten ticket commits into the integration branch in deterministic ticket order, preserving one final commit per ticket. A conflict goes to a fresh integration worker carrying both tickets' intent and both diffs; rerun affected verification afterward.

After every integration or conflict resolution, reconcile the integration head against the validator inventory. Invalidate and rerun every validator whose covered artifact, exact command, executable/runtime fingerprint, or execution tree changed, using coordinator fallback where needed. Run combined affected tests afterward. A downstream chunk unlocks only after every external blocker is integrated, frontier verification passes, and every affected deterministic validator has current executable PASS evidence.

Genuine prose-only terminal tickets use the closeout path in [CHUNKING.md](CHUNKING.md): one fresh worker on the integration worktree, separate ticket commits, no TDD or dedicated chunk review. Behavioral cleanup remains a normal chunk.

## 7. Final review and finish

After no more chunks are runnable, reconcile validators against the final changed paths and verify the ledger contains current executable PASS evidence for every required deterministic validator, then run repository-prescribed broad verification and one whole-integration `/code-review` from the captured starting SHA. Give all final findings to one aggregate fix worker in a dedicated repair worktree based on the integration head. It creates ticket-targeted fixups; the coordinator verifies the repair worktree and applies the commits to the integration branch, then autosquashes them and verifies unchanged tree content. Reconcile validators against the repaired head, invalidate and rerun every validator whose covered artifact, command, executable/runtime fingerprint, or execution tree changed, then rerun broad verification and perform one scoped re-review.

If a load-bearing final finding remains, preserve the integration branch and worktrees and stop. Otherwise:

1. Return to the exact captured caller worktree and verify its root, named branch, clean tracked status, and HEAD still match the captured values.
2. Fast-forward from inside that checkout with `git merge --ff-only <integration-branch>`. Never move a checked-out branch with `git update-ref`, reset, checkout, or a hard synchronization command. If the caller moved or is dirty, preserve the integration branch and stop without changing the caller ref or files.
3. Mark completed acceptance criteria, set each integrated ticket to `completed`, and append its final SHA.
4. Set tickets requiring product context to `needs-info`; set tickets that exhausted technical repair to `ready-for-human`.
5. Remove only clean, successfully integrated worktrees created by this run, using their recorded owner: a native manager removes its own worktrees; for Git-owned worktrees, remove the worktree first and then delete its temporary branch. Preserve and report failed, dirty, external, or unintegrated worktrees.
6. Compact the ledger to its durable summary and release the lock.

Report completed, failed, and dependency-blocked tickets; final commits; verification evidence; rulings; caller/integration heads; retained worktrees; and the exact next action for every incomplete ticket. Never push, open a PR, publish a branch, or mutate a remote tracker without a separate user request.
