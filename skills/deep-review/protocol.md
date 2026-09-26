# Deep Review Protocol

The public review state machine is:

`hypothesis → finding | disproved | unresolved`

The operational validation flow is:

`hypothesis → static adjudication → finding | disproved | unresolved | needs probe → writable probe → finding | disproved | unresolved`

`Needs probe` is an internal transitional state only and is never exposed in reports or publication.

## Gate and resolve

1. Resolve the repository root with `git rev-parse --show-toplevel`; stop outside Git.
2. Resolve the target: current branch when omitted, otherwise a PR, branch, or commit range. Stop for a detached omitted target or standalone commit/file target.
3. Define caller-checkout overlap as an omitted/current-branch target, an explicitly named current branch, or a PR whose source branch is the caller's current branch. Require `git status --porcelain` to be empty only when the target overlaps. A different target excludes caller working-tree changes.
4. For a PR, capture repository, number, base, head ref, head SHA, state, diff, and merge ref. For branches/ranges, resolve base, head SHA, diff, and any associated open PR without replacing the requested target. A branch or range without a unique open PR is local and non-posting; require an explicit PR number or URL before publication.
5. Echo target, base/head, associated PR or lack of one, publication eligibility, and review mode. Obtain confirmation before fetching refs or creating workspaces.

Review only a resolved committed target. Never modify or depend on unrelated caller working-tree state.

## Select reviewers and preflight the runtime

Classify the target as production source, tests, docs, config/build, or other. Recommend valuable review dimensions, explain each inclusion and exclusion, and present the complete catalog:

- `bugs`: behavior and coverage review of executable code or behavior-bearing configuration.
- `structural`: structural maintainability review of changed production logic or control flow.
- `conventions`: project conventions and documented standards review.
- `history`: regression-risk review using relevant history for modified code or configuration.
- `docs`: accuracy review of changed comments, TODOs, documentation, and behavior claims.

Obtain a non-empty confirmed set. Before analysis, verify the invocation-specific runtime contract:

- the exact selected scout count is known;
- enough simultaneous scout capacity exists for the complete set;
- the common scout and selected lens contracts are available;
- an independent validator can launch when hypotheses survive;
- scouts can inspect the pinned worktree read-only;
- the validator can inspect it read-only during static adjudication and receive writable access for bounded probes;
- every role can access the same pinned worktree and its bounded context manifests.

If `N` scouts are selected and fewer than `N` simultaneous slots are available, report required and available capacity and stop before analysis. Never launch a partial set, run sequentially, use bounded waves, or change global harness concurrency policy.

## Capture context and create one worktree

1. Capture one immutable target-bound context snapshot with `manifest`, `core-manifest`, and one `reviewers/<scout>-manifest` per selected scout. Apply each in-scope `deep-review-context` declaration from the governing tracked instruction chain only when it names one exact relative path or bounded glob using `required:` or `optional-glob:`; active-work and selected-artifact references must be explicit relative paths.
2. Preserve repository-relative source path, bundle path, target-binding reasons, repository identity, base/head SHAs, capture metadata, SHA-256, size, required/optional status, and selection reasons in canonical provenance. Accept regular files only; reject symlinks, special files, traversal, external paths, and normalized collisions. Limit artifacts to 2 MiB and the bundle to 16 MiB, check size/mtime before and after copying with one retry, stop on required failures, omit optional failures with a warning, and create an explicit empty bundle when nothing is selected.
3. After an artifact passes validation, copy its bytes exactly once with the fixed direct filesystem operation selected before the run. Manifests reference that snapshot entry and never trigger another copy or rewrite. Do not reconstruct contents with model-authored writes or per-run generated capture machinery. Make the snapshot read-only after capture. Do not create a validator manifest yet.
4. Create exactly one uniquely named coordinator-owned Git worktree under the run directory. Materialize the pinned target as the established merge result: PR merge ref when available, otherwise the existing fallback; for branches/ranges, merge head into base when clean or use resolved head otherwise. Leave the caller checkout untouched.
5. Record and verify the exact baseline. Give every scout the same worktree plus the context root and its bounded manifests. Obtain narrowly scoped authorization for the exact worktree creation operation and path.

## Scout concurrently

Launch every selected scout simultaneously. The generic scout role executes `bugs`, `conventions`, `history`, and `docs` with the corresponding file under `reviewers/lenses/`; `structural` may use its specialized native execution profile but still follows `reviewers/SCOUT.md` and `reviewers/lenses/structural.md`.

Wait for every selected scout. Allow already-running scouts to finish after one fails so diagnostic evidence is preserved. A launch failure, timeout, or missing required context marks the run incomplete. An incomplete run cannot claim PASS or `No findings` and cannot publish.

If every scout succeeds and emits zero hypotheses, do not create validator state or launch a validator. Report that all selected dimensions completed and there was nothing to validate.

## Hypotheses

A **Hypothesis** is an admission-qualified concern about the committed target awaiting independent adjudication. A scout emits either hypotheses or no hypotheses; it does not settle them.

Each hypothesis uses this Markdown shape:

```markdown
### Hypothesis <reviewer-slug>-H<number>
- **Origin:** <reviewer slug>
- **Title:** <concise behavioral concern>
- **File/line:** <repository-relative path>:<line>
- **Potential severity:** blocker | high | medium | low
- **Source evidence:** <concrete changed-code or behavior-path evidence>
- **Expected impact:** <reachable consequence>
- **Falsification condition:** <specific evidence that would reject the concern>
- **Suggested validation:** <cheapest decision-relevant check; no remediation>
- **Context references:** <relevant manifest entries, or none>
```

A hypothesis must be grounded in changed code or a changed behavior-bearing path, identify a plausible consequence, and state how it could be falsified. Discarded or internal speculation is not emitted. Scout severity is only potential severity.

Scouts assign reviewer-local IDs such as `bugs-H1` or `structural-H1`. After deduplication, the coordinator assigns canonical run-local IDs (`H1`, `H2`, …). Canonical IDs are stable for that run; the coordinator retains every original ID and origin slug for provenance.

## Deduplication

The coordinator merges hypotheses only when they describe the same behavioral failure and materially the same causal mechanism. Similar titles or the same file/line are signals, not sufficient keys. Merged hypotheses retain all materially distinct evidence and all origin slugs. When equivalence is uncertain, keep hypotheses separate and validate both.

## Validation outcomes

The validator follows `reviewers/validator.md` and receives exactly one canonical hypothesis per invocation. Every hypothesis enters one logical concurrent static adjudication phase against the same pinned worktree under a read-only contract. The coordinator queues hypotheses in canonical ID order (`H1`, `H2`, …), fills the maximum safe validator capacity exposed by the harness, and launches the next queued hypothesis whenever an invocation finishes and frees a slot, including after failure or timeout. Capacity-constrained batching, including sequential execution with one slot, is valid and does not make the review incomplete. Completion order may be arbitrary, and static invocations remain independent: no invocation depends on or consumes another validator's outcome. A static invocation returns exactly one of:

- **Finding**: decisive static evidence independently establishes the hypothesis, including final severity and evidence of actual reachability and impact.
- **Disproved**: concrete static evidence such as an invariant, guard, contract, or test rejects the hypothesis. It is not user-visible.
- **Unresolved**: static adjudication cannot establish or reject the hypothesis and no meaningful writable check can settle it. It maps to `discuss`.
- **Needs probe**: static evidence cannot settle the hypothesis, but a bounded writable check can materially answer a specific unresolved factual question. It must include the unresolved question, why static evidence is insufficient, and the cheapest decisive check. This is an internal transition only.

Only after every canonical hypothesis has been attempted and all static invocations have finished may the coordinator enter the writable phase. If the static phase remains complete, it queues `Needs probe` hypotheses for sequential writable validation, ordered by canonical hypothesis ID rather than static completion order. Each writable invocation receives exactly one canonical hypothesis plus its unresolved question and proposed check, independently adjudicates the full hypothesis, and returns exactly one final `Finding`, `Disproved`, or `Unresolved` outcome.

Static validators may read/search repository files and use read-only Git inspection. They must not run builds, tests, linters, typecheckers, scripts, probes, package-manager commands, or other commands that can create filesystem artifacts. Writable probes use the existing exact-baseline restoration and contamination protections.

Every validator first tries to falsify, checks callers, guards, invariants, contracts, tests, configuration, instructions, and relevant context, and reports no unrelated issue. A hypothesis not attempted because of operational failure is **not validated due to review failure**, not Unresolved.

## Context capture and persisted run state

Context capture is deterministic protocol machinery, not a task for the model to reimplement during a run. Once an artifact has passed path, type, size, target-binding, and race checks, the coordinator copies it exactly once with the fixed direct `cp` filesystem operation (or the harness's byte-for-byte equivalent selected before the run). Every manifest references that existing snapshot entry; a manifest lookup never triggers another copy or rewrite. The operation must preserve bytes exactly and must not use model-authored writes to reconstruct contents or generate an ad-hoc executable capture script. Existing pre/post size and mtime checks, retry behavior, SHA-256 and metadata verification, provenance, privacy, size limits, and snapshot immutability remain mandatory.

The coordinator persists protocol state in one coordinator-owned `run-state.json` (or an equivalent single run-state record when the harness requires another serialization) rather than one file per pipeline stage. That state records the exact pinned baseline identity and restoration status; scout completion and provenance; canonical hypotheses, original IDs, origins, deduplication evidence, and context references; every completed validator outcome and evidence; incomplete-run and unattempted-hypothesis status; runtime acceptance receipt; final report data; cleanup status; and, when publication occurs, the exact publication payload. The context snapshot remains separate because it is an immutable evidence bundle with manifests. A user-facing `final-report.md` may be preserved when useful, and a `publication-receipt.json` is created only when publication occurs and contains the exact payload together with its publication receipt. Separate intermediate files for scout output, canonical hypotheses, or individual validator outcomes are not created unless a concrete runtime constraint requires them and that constraint is recorded in the run state.

## Runtime acceptance receipt

Every real review emits a passive runtime acceptance receipt from coordinator-observed state. The coordinator records the harness identity and version; the shared receipt also records the reviewed skill commit or version, selected roles, and one status for every acceptance scenario: `PASS`, `FAIL`, or `NOT EXERCISED`.

Record only observed behavior. Never perturb a real review to exercise a row, infer a pass from static configuration, or convert an unobserved path into a pass. Preserve concise evidence for each exercised row in `run-state.json` and the final report:

- zero hypotheses: whether validation was correctly skipped;
- surviving hypotheses: whether every canonical hypothesis received independent static adjudication;
- capacity-bounded static validation: whether hypotheses exceeding available validator slots were queued in canonical ID order, launched as slots freed, and completed without capacity alone making the run incomplete;
- multiple selected scouts: whether the complete selected set launched in one simultaneous wave;
- insufficient scout capacity: whether analysis stopped before any partial launch;
- validator probes: whether the static wave completed and the exact baseline was restored and verified before each sequential probe;
- scout failure: whether running scouts finished, the run became incomplete, and publication/PASS were blocked;
- validator partial failure: whether completed outcomes survived, queued static hypotheses were still attempted, and writable probing was blocked;
- PR head change: whether stale reviewed/current SHAs were reported and publication was blocked;
- cleanup: whether removal was confined to the current run and exact leftovers were reported.

Rare failure and transition paths remain `NOT EXERCISED` until they occur naturally or a targeted smoke run observes them. The receipt is conformance evidence for this run, not proof of unexercised behavior.

## Pipeline invariants

- All selected scouts inspect one pinned coordinator-owned worktree concurrently and read-only. Static validators later inspect that same disposable worktree with capacity-bounded concurrency under a read-only contract; writable probes receive access sequentially.
- Every deduplicated hypothesis enters the static adjudication queue exactly once in canonical ID order, and no validator runs when successful scouting produces zero hypotheses. The coordinator keeps the maximum safe harness capacity occupied until the queue is drained, refilling a slot whenever an invocation finishes regardless of outcome; one available slot is sufficient for a valid static phase, and capacity limits alone never make a run incomplete.
- Exactly one late-bound `reviewers/validator-manifest` is created when hypotheses survive; it is derived from those hypotheses and reused for all static and writable invocations.
- The coordinator waits for the static queue to drain and all active invocations to finish, then verifies the shared worktree is still at the exact recorded pinned baseline. Any static validator failure/timeout, unexpected contamination, or baseline mismatch marks the review incomplete and prevents the entire writable phase.
- Only completed `Needs probe` outcomes enter the writable queue, ordered by canonical hypothesis ID. Before every writable probe, including the first, the coordinator restores, cleans, and verifies the exact recorded pinned baseline.
- Static validators never execute artifact-producing commands. A static validator failure or timeout preserves completed outcomes and marks the review incomplete, but the coordinator continues launching queued static hypotheses until each has been attempted exactly once.
- Once each context artifact passes validation, it is copied exactly once with the fixed direct `cp` operation or selected harness equivalent; manifests reference the existing snapshot entry, and the model does not reconstruct artifact contents or generate capture machinery during a run.
- Coordinator-owned protocol state is consolidated in one run state, including the exact publication payload when applicable, with final-report and publication-receipt artifacts created only under the conditions above.
- Every final report and run state contains the passive runtime acceptance receipt with no inferred passes.
- Once the coordinator-owned worktree and exact baseline are established, restoration authorization is obtained once for that exact path or encapsulated in a coordinator-only helper that rejects other paths; no blanket `git reset` or `git clean` permission is granted. The coordinator preserves each outcome and evidence outside probe state, automatically restores the exact pinned baseline, cleans tracked, untracked, and ignored artifacts only in that worktree, and verifies `HEAD`, the tree, and `git status` before the next invocation. Restoration failure stops validation and marks the run incomplete.
- Any scout, static validator, writable validator, or restoration failure makes the run incomplete, prevents PASS/`No findings`, and prevents publication. Unattempted hypotheses remain explicitly not validated due to review failure.
- A changed PR head makes the pinned result stale. Report reviewed and current SHAs, and rerun before current-gate use or publication.
- A Finding may be presented assertively. An Unresolved item may be published only with explicit approval and only as a question describing evidence and remaining uncertainty.

## Present, decide, and publish

Use `references/output-template.md`. Report hypotheses discovered, hypotheses after dedupe, and outcome counts. Apply the deterministic action policy: every Finding with a small, unambiguous fix of about 20 changed lines or fewer is `fix-now`; every Finding with a larger or cross-module fix is `follow-up`; every Unresolved outcome is separate and always `discuss`. Keep scout provenance in run state rather than normal Finding prose.

Before presenting a result as current/actionable or publishing, re-check target freshness. If the PR head changed, report reviewed and current SHAs, mark the result stale, and require a rerun.

Use `references/pr-review-comments.md` for publication. Findings may be drafted as established defects. User-selected Unresolved items require explicit per-item approval and must be questions describing evidence and remaining uncertainty. Preserve semantic anchors, changed-line validation, exact payload validation, privacy boundaries, freshness, comment-count verification, and per-comment approval.

## Cleanup

After every exit path, preserve final report and evidence, obtain narrowly scoped authorization for the exact coordinator-created worktree cleanup path, remove only that worktree with the narrowest Git worktree mechanism, and verify its registration is gone. Remove the matching context snapshot and run directory only after preservation checks pass. Report exact leftovers when cleanup is interrupted.
