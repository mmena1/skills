# Deep Review Protocol

The public review state machine is:

`hypothesis → finding | disproved | unresolved`

The operational validation flow is:

`hypothesis → static adjudication → finding | disproved | unresolved | needs probe → writable probe → finding | disproved | unresolved`

`Needs probe` is an internal transitional state only and is never exposed in reports or publication.

## Entry point

`/deep-review [target]` runs the full review this protocol defines. `/deep-review follow-up [target] [record=<run ID | path>] [selection]` runs follow-up revalidation as defined in "Follow-up revalidation" below. A leading literal `follow-up` token selects follow-up mode. Every invocation without it is the unchanged full review, and a branch literally named `follow-up` is reviewed through an unambiguous ref such as `refs/heads/follow-up`.

After the `follow-up` token, an argument that is `all`, `published`, a comma-separated list of canonical IDs such as `H2,H5`, or a PR review comment URL is the selection; `record=` names the source record explicitly; any other first argument is the target. A bare comment ID is a selection only after an explicit target, because a bare number before it is a PR number.

## Gate and resolve

1. Resolve the repository root with `git rev-parse --show-toplevel`; stop outside Git.
2. Resolve the target: current branch when omitted, otherwise a PR, branch, or commit range. Stop for a detached omitted target or standalone commit/file target.
3. Define caller-checkout overlap as an omitted/current-branch target, an explicitly named current branch, or a PR whose source branch is the caller's current branch. Require `git status --porcelain` to be empty only when the target overlaps. A different target excludes caller working-tree changes.
4. For a PR, capture repository, number, base, head ref, head SHA, state, diff, and merge ref. For branches/ranges, resolve base, head SHA, diff, and any associated open PR without replacing the requested target. A branch or range without a unique open PR is local and non-posting; require an explicit PR number or URL before publication.
5. Keep existing PR review discussion out of review inputs: do not retrieve it until validation finishes or include it in context snapshots, manifests, scout prompts, canonical hypotheses, or static/writable validator prompts. PR metadata and stated intent remain available as before.
6. Echo target, base/head, associated PR or lack of one, publication eligibility, and review mode. Obtain confirmation before fetching refs or creating workspaces.

Review only a resolved committed target. Never modify or depend on unrelated caller working-tree state.

## Select reviewers and preflight the runtime

Classify the target as production source, tests, docs, config/build, or other. Recommend valuable review dimensions, explain each inclusion and exclusion, and present the complete catalog:

- `bugs`: behavior and coverage review of executable code or behavior-bearing configuration.
- `structural`: structural maintainability review of changed production logic or control flow.
- `conventions`: project conventions and documented standards review.
- `history`: regression-risk review using relevant history for modified code or configuration.
- `docs`: accuracy review of changed comments, TODOs, documentation, and behavior claims.

Obtain a non-empty confirmed set. Before analysis, verify the invocation-specific role and access prerequisites:

- the exact selected scout count is known;
- the harness declares which scout capacity gate applies;
- the native scout agent for every selected lens is installed: `deep-review-scout-<lens>` for `bugs`, `conventions`, `history`, and `docs`, and `deep-review-structural` for `structural`, each embedding the common scout contract and exactly its own lens;
- the static and writable validator agents are installed;
- the harness declares its static-validator concurrency ceiling and launch-refusal/backpressure behavior. A fixed limit is an upper bound, not evidence that those slots will be available when validators launch;
- scouts and static validators can read the pinned worktree and write scratch files outside it;
- the writable probe has only the harness-authorized access needed for bounded checks;
- every role can access the same pinned worktree and its bounded context manifests.

Apply the declared scout capacity gate at its defined point. Strict preflight, used when reliable available-slot observation exists, confirms enough slots for the complete set before any scout launches. Launch-time admission, used when no reliable observation exists, makes no advance slot claim; admission happens while dispatching the complete concurrent wave, with refusal behavior defined below.

Static and writable describe role behavior contracts; their enforcement follows the active harness mechanisms in `SKILL.md`. A writable probe stays within the coordinator's effective permissions and gains no permissions from its phase.

Scouts and static validators analyze the pinned worktree statically and keep disposable scratch files in the supplied scratch directory. Scratch files are ordinary review activity: they never make a run incomplete while the worktree stays at its pinned baseline and the caller checkout stays untouched. Executing the target belongs to the writable probe.

If a required native agent is missing, stop before analysis and name it; never substitute the coordinator, a generic agent, another scout, or another model. Under strict preflight, if `N` scouts are selected and fewer than `N` simultaneous slots are available, report required and available capacity and stop before analysis. Under launch-time admission, attempt every selected scout in the same concurrent wave without querying, guessing, assuming, estimating, inferring, or recording a numeric available capacity. If any launch is refused, do not retry it or launch a replacement, reduce or substitute the set, or fall back to sequential scouting or bounded waves. Let already-started scouts finish and preserve their evidence in run state and report, launch no validator or probe, mark the run incomplete, block PASS, `No findings`, and publication, and still run cleanup. Never launch a deliberately partial set or change global harness concurrency policy.

## Capture context and create one worktree

1. Capture one immutable target-bound context snapshot with `manifest`, `core-manifest`, and one `reviewers/<scout>-manifest` per selected scout. Apply each in-scope `deep-review-context` declaration from the governing tracked instruction chain only when it names one exact relative path or bounded glob using `required:` or `optional-glob:`; active-work and selected-artifact references must be explicit relative paths.
2. Preserve repository-relative source path, bundle path, target-binding reasons, repository identity, base/head SHAs, capture metadata, SHA-256, size, required/optional status, and selection reasons in canonical provenance. Accept regular files only; reject symlinks, special files, traversal, external paths, and normalized collisions. Limit artifacts to 2 MiB and the bundle to 16 MiB, check size/mtime before and after copying with one retry, stop on required failures, omit optional failures with a warning, and create an explicit empty bundle when nothing is selected.
3. After an artifact passes validation, copy its bytes exactly once with the fixed direct filesystem operation selected before the run. Manifests reference that snapshot entry and never trigger another copy or rewrite. Do not reconstruct contents with model-authored writes or per-run generated capture machinery. Make the snapshot read-only after capture. Do not create a validator manifest yet.
4. Create exactly one uniquely named coordinator-owned Git worktree under the run directory, and beside it one `scratch/` directory for the run's scratch files. Materialize the pinned target as the established merge result: PR merge ref when available, otherwise the existing fallback; for branches/ranges, merge head into base when clean or use resolved head otherwise. Leave the caller checkout untouched.
5. Record and verify the exact baseline. Give every scout the same worktree plus the context root and its bounded manifests. Every role invocation receives the worktree's absolute path and the reviewed base and head SHAs, and every scout and static validator also receives the scratch directory's absolute path. Every role invocation roots every repository read and Git command at that worktree and at history reachable from the reviewed head, never at the caller checkout or later refs. Obtain narrowly scoped authorization for the exact worktree creation operation and path.

## Scout concurrently

Launch the native agent of every selected scout, and only those, as one concurrent wave: `deep-review-scout-<lens>` for `bugs`, `conventions`, `history`, and `docs`, and `deep-review-structural` for `structural`. Each scout agent embeds `reviewers/SCOUT.md` followed by its own file under `reviewers/lenses/`, so the coordinator passes each scout its lens slug, never a lens file. The structural scout and validators apply the structural evidence standard below; no design-guidance skill is a prerequisite, a supplied contract, or an adjudication authority for structural review.

Dispatch every selected scout before waiting for any scout to complete. Launches may occur in separate parent messages or model responses; receiving a launch acknowledgment before dispatching the next scout is allowed.

Wait for every selected scout. Allow already-running scouts to finish after one fails so diagnostic evidence is preserved. A launch failure, timeout, or missing required context marks the run incomplete. An incomplete run cannot claim PASS or `No findings` and cannot publish.

If the scout wave is complete and every scout succeeds and emits zero hypotheses, do not create validator state or launch a validator. Report that all selected dimensions completed and there was nothing to validate.

## Hypotheses

A **Hypothesis** is an admission-qualified concern about the committed target awaiting independent adjudication. A scout emits either hypotheses or no hypotheses; it does not settle them.

Each hypothesis uses this Markdown shape:

```markdown
### Hypothesis <reviewer-slug>-H<number>
- **Origin:** <reviewer slug>
- **Title:** <concise behavioral concern, or the structural cost>
- **File/line:** <repository-relative path>:<line>
- **Potential severity:** blocker | high | medium | low
- **Source evidence:** <concrete changed-code or behavior-path evidence>
- **Expected impact:** <reachable consequence, or the structural cost, its causal mechanism, and the task it burdens>
- **Falsification condition:** <specific evidence that would reject the concern>
- **Suggested validation:** <cheapest decision-relevant check; no remediation>
- **Context references:** <relevant manifest entries, or none>
```

A hypothesis must be grounded in changed code or a changed behavior-bearing path, identify a plausible consequence, and state how it could be falsified. Discarded or internal speculation is not emitted. Scout severity is only potential severity.

A **structural hypothesis** concerns maintainability rather than runtime behavior. Its consequence is a reasoning or maintenance cost that an identifiable task bears, such as understanding a behavior or invariant, locating relevant knowledge, determining affected callers or states, or making a coherent change without scattered edits or hidden consequences. It follows the **structural evidence standard**: a demonstrated cost of that kind in the reviewed code plus a concrete behavior-preserving alternative that demonstrably reduces it without introducing an equal or greater reasoning or maintenance burden establishes it. A preference for another design, technique, fewer lines, fewer helpers, or fewer layers does not meet it, and no paradigm, technique, or abstraction count is evidence for admission, validation, rejection, severity, or remedy. Passing tests or correct behavior do not falsify it. It is rejected when the identified task does not bear the cost, the structure is essential to the behavior or its constraints, the alternative would change behavior, only rename or relocate the cost, or introduce an equal or greater burden, or the concern is only a style or design preference. The scout contract, deduplication, the validator, and reporting apply this same standard.

Scouts assign reviewer-local IDs such as `bugs-H1` or `structural-H1`. After deduplication, the coordinator assigns canonical run-local IDs (`H1`, `H2`, …). Canonical IDs are stable for that run; the coordinator retains every original ID and origin slug for provenance.

Each canonical hypothesis is persisted complete, in one record (or an equivalent single-record serialization) that retains its canonical ID, original scout IDs and origins, title, source location, potential severity, source evidence, expected impact, falsification condition, suggested validation, and context references. This **canonical hypothesis record** is what a later follow-up reads directly as the original hypothesis, so a title, summary, or validator outcome never stands in for it.

## Deduplication

The coordinator merges hypotheses only when they describe the same behavioral failure and materially the same causal mechanism. Structural hypotheses merge only when they describe the same structural cost on the same task and materially the same mechanism under the structural evidence standard; a shared technique, pattern, or proposed alternative is not a merge key. A structural hypothesis and a correctness hypothesis are never merged, even when they concern the same code. Similar titles or the same file/line are signals, not sufficient keys. Merged hypotheses retain all materially distinct evidence and all origin slugs. A merged hypothesis stays one complete canonical hypothesis record: it keeps every materially distinct source evidence, expected impact, falsification condition, suggested validation, and context reference of its constituents, with every original scout ID and origin, and is never replaced by a title, summary, or validator outcome. When equivalence is uncertain, keep hypotheses separate and validate both.

## Validation outcomes

The validator follows `reviewers/validator.md` and receives exactly one canonical hypothesis per invocation. Every hypothesis enters one logical concurrent static adjudication phase against the same pinned worktree under a static contract. The coordinator queues hypotheses in canonical ID order (`H1`, `H2`, …) and launches up to the maximum concurrent validator capacity declared by the active harness. A declared fixed capacity is a ceiling, not a guarantee that those slots are available at launch; any measured available capacity reported by the harness further bounds concurrency. A refused launch follows the harness's declared backpressure behavior. The coordinator launches the next queued hypothesis whenever an invocation finishes and frees a slot, including after failure or timeout. Capacity-constrained batching, including sequential execution with one slot, is valid and does not make the review incomplete. Completion order may be arbitrary, and static invocations remain independent: no invocation depends on or consumes another validator's outcome. A static invocation returns exactly one of:

- **Finding**: decisive static evidence independently establishes the hypothesis, including final severity and evidence of actual reachability and impact, or for a structural hypothesis evidence meeting the structural evidence standard.
- **Disproved**: concrete static evidence such as an invariant, guard, contract, or test rejects the hypothesis, or for a structural hypothesis evidence establishes one of the structural evidence standard's rejection grounds. Passing tests or correct behavior never disprove a structural hypothesis. It is not user-visible.
- **Unresolved**: static adjudication cannot establish or reject the hypothesis and no meaningful writable check can settle it. It maps to `discuss`.
- **Needs probe**: static evidence cannot settle the hypothesis, but a bounded writable check can materially answer a specific unresolved factual question. It must include the unresolved question, why static evidence is insufficient, and the cheapest decisive check. This is an internal transition only.

Only after every canonical hypothesis has been attempted and all static invocations have finished may the coordinator enter the writable phase. If the static phase remains complete, it queues `Needs probe` hypotheses for sequential writable validation, ordered by canonical hypothesis ID rather than static completion order. Each writable invocation receives exactly one canonical hypothesis plus its unresolved question and proposed check, independently adjudicates the full hypothesis, and returns exactly one final `Finding`, `Disproved`, or `Unresolved` outcome.

Static validators read and search repository files, inspect Git history, and keep scratch files outside the pinned worktree. Executable checks belong to the writable phase, whose probes use the existing exact-baseline restoration and contamination protections.

Every validator first tries to falsify, checks callers, guards, invariants, contracts, tests, configuration, instructions, and relevant context, and reports no unrelated issue. A hypothesis not attempted because of operational failure is **not validated due to review failure**, not Unresolved.

## Writable probe environment

Before each writable invocation, apply `references/probe-environment.md` completely. The coordinator supplies the validator its environment contract and this reference, after exact-baseline restoration and within the existing owned disposable boundary. Pass that contract's process execution gate before target-controlled setup, imports, or checks, recording the verified effective policy or exact user authorization and residual risk separately from path ownership. The contract establishes target-native dependency setup, actual runtime/dependency and code-origin verification, substitution limits, evidence qualification, and environment disposal or invalidation. It applies equally to follow-up probes. No bounded check supplies executable evidence until verification succeeds.

Preserve each invocation's environment provenance, commands, verification and check results, limitations, outcome, and restoration status in the existing consolidated run state outside mutable probe state before restoration. Setup or verification limitations do not turn failed execution into Finding/Disproved evidence; distinguish a completed inconclusive attempt from operational failure preventing validation using the shared environment contract.

## Context capture and persisted run state

Context capture is deterministic protocol machinery, not a task for the model to reimplement during a run. Once an artifact has passed path, type, size, target-binding, and race checks, the coordinator copies it exactly once with the fixed direct `cp` filesystem operation (or the harness's byte-for-byte equivalent selected before the run). Every manifest references that existing snapshot entry; a manifest lookup never triggers another copy or rewrite. The operation must preserve bytes exactly and must not use model-authored writes to reconstruct contents or generate an ad-hoc executable capture script. Existing pre/post size and mtime checks, retry behavior, SHA-256 and metadata verification, provenance, privacy, size limits, and snapshot immutability remain mandatory.

The coordinator persists protocol state in one coordinator-owned `run-state.json` (or an equivalent single run-state record when the harness requires another serialization) rather than one file per pipeline stage. That state records the exact pinned baseline identity and restoration status; scout completion and provenance; every complete canonical hypothesis record and its deduplication evidence; every completed validator outcome and evidence; PR discussion retrieval completeness, timestamps, and per-item overlap dispositions with reasons and links; incomplete-run and unattempted-hypothesis status; runtime acceptance receipt; final report data; cleanup status; and, when publication occurs, the exact publication payload with the submission outcome and its identifiers, and the read-back verification outcome with its source, time, and diagnostic evidence. The context snapshot remains separate because it is an immutable evidence bundle with manifests. A user-facing `final-report.md` may be preserved when useful, and a `publication-receipt.json` is created only when publication occurs and contains the exact payload together with its publication receipt, which records the submission outcome and the verification outcome separately. Separate intermediate files for scout output, canonical hypotheses, or individual validator outcomes are not created unless a concrete runtime constraint requires them and that constraint is recorded in the run state.

The run directory has a unique name, for example a UTC timestamp followed by a short random suffix, and that name is the run's **run ID**. `run-state.json` begins with a **record identity** so a later session can match it against a resolved target:

```json
"record": {
  "format_version": 1,
  "run_id": "<run directory name>",
  "mode": "full | follow-up",
  "repository": "<owner/name of the primary remote, or the canonical record root when there is none>",
  "target": {"kind": "pr | branch | range", "key": "<owner/name#number | refs/heads/<name> | <base SHA>..<head SHA>>"},
  "base_sha": "<base SHA>",
  "reviewed_head_sha": "<reviewed head SHA>",
  "completed_at": "<UTC ISO 8601 time the run finished>",
  "completeness": "complete | incomplete | stale",
  "lineage": {"source_run_id": "<source full-review run ID>", "follow_up_run_ids": ["<earlier follow-up run ID>"]}
}
```

`lineage` is present only in a follow-up record. It names the source full-review run ID and every earlier follow-up run ID the follow-up built on. Each approved publication payload entry records the canonical concern ID it publishes, and the publication record keeps the created comment identifiers whenever the submission response or a read-back provides them, as `references/pr-review-comments.md` describes.

## Runtime acceptance receipt

Every real review emits a passive runtime acceptance receipt from coordinator-observed state. The coordinator records the harness identity and version; the shared receipt also records the reviewed skill commit or version, each selected lens with the native agent used for it, the validator agents that ran, and one status for every acceptance scenario: `PASS`, `FAIL`, or `NOT EXERCISED`.

Record the enforcement mechanism specified by the active harness in `SKILL.md` and the observed inherited session policy when available. Role behavior contracts alone are not evidence of mechanical isolation or additional probe permissions.

Record only observed behavior. Never perturb a real review to exercise a row, infer a pass from static configuration, or convert an unobserved path into a pass. Preserve concise evidence for each exercised row in `run-state.json` and the final report:

- zero hypotheses: whether validation was correctly skipped;
- surviving hypotheses: whether every canonical hypothesis received independent static adjudication;
- capacity-bounded static validation: whether hypotheses exceeding available validator slots were queued in canonical ID order, launched as slots freed, and completed without capacity alone making the run incomplete;
- multiple selected scouts: whether the complete selected set was dispatched before waiting for any scout to complete;
- insufficient scout capacity: whether strict preflight stopped before any scout launched, or launch-time refusal stopped the run as incomplete; for launch-time refusal, whether any scouts started, those scouts finished with their evidence preserved, and no retry, reduction, or substitution occurred;
- validator probes: whether the static wave completed and the exact baseline was restored and verified before each sequential probe; whether its process execution gate and environment contract were verified before execution, process-boundary evidence, environment provenance and qualified outcomes survived restoration, and environment artifacts could not contaminate later probes;
- scout failure: whether running scouts finished, the run became incomplete, and publication/PASS were blocked;
- validator partial failure: whether completed outcomes survived, queued static hypotheses were still attempted, and writable probing was blocked;
- PR-review-overlap: whether the coordinator retrieved complete discussion after independent validation, recorded semantic dispositions and links, and re-checked overlap before publication when that path was observed;
- PR head change: whether stale reviewed/current SHAs were reported and publication was blocked;
- cleanup: whether removal was confined to the current run and exact leftovers were reported.

Rare failure and transition paths remain `NOT EXERCISED` until they occur naturally or a targeted smoke run observes them. The receipt is conformance evidence for this run, not proof of unexercised behavior.

## Pipeline invariants

- All selected scouts inspect one pinned coordinator-owned worktree concurrently. Static validators later inspect that same disposable worktree with capacity-bounded concurrency under a static contract; writable probes receive access sequentially.
- Every deduplicated hypothesis enters the static adjudication queue exactly once in canonical ID order, and no validator runs when successful scouting produces zero hypotheses. The coordinator keeps the maximum safe harness capacity occupied until the queue is drained, refilling a slot whenever an invocation finishes regardless of outcome; one available slot is sufficient for a valid static phase, and capacity limits alone never make a run incomplete.
- Exactly one late-bound `reviewers/validator-manifest` is created when hypotheses survive; it is derived from those hypotheses and reused for all static and writable invocations.
- The coordinator waits for the static queue to drain and all active invocations to finish, then verifies the shared worktree is still at the exact recorded pinned baseline. Any static validator failure/timeout, unexpected contamination, or baseline mismatch marks the review incomplete and prevents the entire writable phase.
- Only completed `Needs probe` outcomes enter the writable queue, ordered by canonical hypothesis ID. Before every writable probe, including the first, the coordinator restores, cleans, and verifies the exact recorded pinned baseline.
- Static validators keep their scratch files in the supplied scratch directory. A static validator failure or timeout preserves completed outcomes and marks the review incomplete, but the coordinator continues launching queued static hypotheses until each has been attempted exactly once.
- Once each context artifact passes validation, it is copied exactly once with the fixed direct `cp` operation or selected harness equivalent; manifests reference the existing snapshot entry, and the model does not reconstruct artifact contents or generate capture machinery during a run.
- Coordinator-owned protocol state is consolidated in one run state, including the exact publication payload and its separately recorded submission and verification outcomes when applicable, with final-report and publication-receipt artifacts created only under the conditions above.
- Every final report and run state contains the passive runtime acceptance receipt with no inferred passes.
- Once the coordinator-owned worktree and exact baseline are established, restoration authorization is obtained once for that exact path or encapsulated in a coordinator-only helper that rejects other paths; no blanket `git reset` or `git clean` permission is granted. The coordinator preserves each outcome and evidence outside probe state, automatically restores the exact pinned baseline, cleans tracked, untracked, and ignored artifacts only in that worktree, and verifies `HEAD`, the tree, and `git status` before the next invocation. Restoration failure stops validation and marks the run incomplete.
- Any scout, static validator, writable validator, or restoration failure makes the run incomplete, prevents PASS/`No findings`, and prevents publication. Unattempted hypotheses remain explicitly not validated due to review failure.
- A changed PR head makes the pinned result stale. Report reviewed and current SHAs, and rerun before current-gate use or publication.
- A Finding may be presented assertively. An Unresolved item may be published only with explicit approval and only as a question describing evidence and remaining uncertainty.

## Compare existing PR review discussion

After all validation finishes and before presentation, apply `references/pr-review-overlap.md` when a confirmed PR is associated. The coordinator retrieves discussion and compares every completed Finding and Unresolved item, including preserved outcomes from incomplete runs. Runs without a uniquely associated PR skip this step and remain local and non-posting.

Overlap changes presentation and publication eligibility only. Preserve independent outcomes, severity, evidence, and action classification. Keep already-reported items visible with their prior links and overlap counts; a resolved thread cannot hide a defect still present in the pinned commit. Discussion retrieval failure leaves comparison incomplete and blocks publication, while retaining completed validation evidence.

## Present, decide, and publish

Use `references/output-template.md`. Report hypotheses discovered, hypotheses after dedupe, and outcome counts. Apply the deterministic action policy. A Finding with one clearly correct remedy is sized: a small, unambiguous fix of about 20 changed lines or fewer is `fix-now`, and a larger or cross-module fix is `follow-up`. A Finding whose remedy needs the author's design or tradeoff judgment, including a structural Finding with several acceptable remedies, is `discuss`. Take that remedy classification from the validator's Recommendation. Report a structural Finding by its demonstrated cost, the task that cost burdens, and how the behavior-preserving alternative reduces it, never by the technique the code uses or the alternative would adopt. Every Unresolved outcome is separate and always `discuss`. Keep scout provenance in run state rather than normal Finding prose.

Carry each Finding's remediation from the validator's Recommendation without compressing away its required outcome or the material constraints that distinguish an acceptable repair from a superficially valid one. The required outcome is authoritative; a proposed implementation is guidance unless the repository or finding requires that exact shape. The coordinator may simplify or clarify that wording and may re-inspect the relevant code to establish safer wording, but it must not invent a confident architectural prescription the finding or surrounding code does not support.

Before presenting a result as current/actionable or publishing, re-check target freshness. If the PR head changed, report reviewed and current SHAs, mark the result stale, and require a rerun.

For a confirmed associated PR, include the output template's optional audience note with the findings/publication invitation. Present it as information, not an extra confirmation gate. Audience resolution and drafting remain governed by `references/pr-review-comments.md`.

Use `references/pr-review-comments.md` for publication. Findings may be drafted as established defects. User-selected Unresolved items require explicit per-item approval and must be questions describing evidence and remaining uncertainty. Run the ambiguity check from that reference before presenting each comment for approval. Preserve semantic anchors, changed-line validation, exact payload validation, privacy boundaries, freshness, field-complete read-back verification, and per-comment approval. Verification failure or an ambiguous submission never authorizes posting the review or its comments again.

## Preserved review records

Every run that created a run state preserves its records under the **record root**, `<git-common-dir>/deep-review/records/<run-id>/`. The record root is shared by every worktree of the clone, survives worktree and run-directory removal, is never tracked, and follows the same rule in every environment.

`<git-common-dir>` is the canonical absolute path of the caller repository's Git common directory:

1. Run `git rev-parse --path-format=absolute --git-common-dir` from the caller checkout where that option is available. Otherwise run `git rev-parse --git-common-dir`; it may print a relative path such as `.git` or `../.git`, which is relative to the directory the command ran in, so resolve it against that directory.
2. Canonicalize the result: resolve symlinks, normalize separators and case to the platform's native form, and reject a result that is not an existing directory.

An ordinary checkout, any of its linked worktrees, and any subdirectory of either all resolve to the same record root. Never use the coordinator-owned review worktree's own Git directory or a path relative to the session's working directory.

A preserved record holds `run-state.json`, `final-report.md` when produced, and `publication-receipt.json` when produced. Preservation uses the fixed direct copy operation, the same `cp` operation (or selected byte-for-byte equivalent) that context capture uses, with narrowly scoped authorization for that exact record directory. It never overwrites an existing record directory. It runs only after worktree cleanup has finished and the run state and final report record the actual cleanup outcome, including a failed or interrupted cleanup, so the preserved record describes how the run really ended. Before copying, the run state records the intended record directory. Preservation copies `run-state.json` last, so a partial record has no run state, and verifies byte equality of every copied file before the run directory is removed.

Preservation never changes a review. A denied authorization, a write restriction on the Git common directory, or any other preservation failure leaves the run's analysis, outcomes, report, cleanup outcome, and publication unchanged. Worktree cleanup has already run by then, so preservation never blocks it. The coordinator then records the preservation failure in the retained run state, reports that records were not preserved and why, keeps the run directory with its records, and names the exact retained paths, including any partial record directory. It never removes unpreserved records and is never silent about a preservation failure.

## Cleanup

After every exit path, first remove the scratch directory at its exact path once every scout and static validator has finished, whether or not the run directory will be retained, under the same narrowly scoped authorization as the worktree. Record a failed removal and its exact path in the run state and final report; it never blocks the steps below, and the records that recovery needs stay intact. Then clean up in this order:

1. Obtain narrowly scoped authorization for the exact coordinator-created worktree cleanup path, remove only that worktree with the narrowest Git worktree mechanism, and verify its registration is gone. Keep the run directory.
2. Update the run state's cleanup status and the final report with the actual scratch and worktree cleanup outcomes, including a failed or interrupted cleanup and its exact leftovers.
3. Preserve the run's records as described in "Preserved review records". Worktree cleanup never waits on preservation, and a preservation failure never reverses or blocks it.
4. Remove the matching context snapshot and run directory only when both the worktree cleanup in step 1 and the record preservation in step 3 are verified. The worktree lives beneath the run directory, so a failed or interrupted worktree removal keeps the run directory, the leftover worktree path, and its Git registration exactly as they are for recovery, and the coordinator reports each exact path; it never deletes them outside the Git worktree mechanism. When preservation is not verified, keep the run directory and report its exact path. A failed worktree cleanup is still preserved to the record root independently, so the record carries the failure outcome.

Report the preserved record path, and exact leftovers when cleanup is interrupted.

## Follow-up revalidation

Follow-up revalidation independently revalidates selected concerns from a preserved prior review record against a newly pinned head. It is not a full PR review and never claims comprehensive coverage. It reports each selected concern as Addressed, Not addressed, Incomplete, or Deferred.

### Resolve and discover

Target resolution, caller-checkout overlap, the clean-status requirement, PR discussion isolation, and the confirmation gate are the full review's ("Gate and resolve"). The new head is the resolved target's head.

For a PR or branch target, read every `run-state.json` directly under the record root's run directories and match records whose record identity has the same repository and target kind and key. The **source record** is the latest matching record whose mode is `full`, never a newer follow-up record, so a focused follow-up that rechecked only a subset can never narrow the concern inventory. Latest means the greatest `completed_at`; when two matching full-review records tie, discovery is ambiguous and requires explicit selection. Report the source record's completeness status and how many older full-review records match. List unreadable, schema-invalid, and identity-less records as skipped, with reasons.

A commit-range target, no matching full-review record, or a user preference uses explicit selection by run ID (a run directory in the record root) or record path. Explicit selection may name a record without identity fields, such as one preserved before record identity existed; the confirmation shows the missing identity, and the user confirms it. Explicitly selecting a follow-up record resolves through its lineage to its source full-review record; when that source record cannot be read, stop and report it, because the concern inventory cannot be recovered.

Follow-up records whose lineage names the chosen source supply prior status and provenance only, including the comments they published and the concerns those comments map to. For each concern, the confirmation and report show its latest prior follow-up status, any prior deferral, and the run IDs that produced them, as context, never as evidence.

### Concerns and selection

The **concern inventory** is the source record's Finding and Unresolved outcomes, keyed by canonical ID. Disproved hypotheses and hypotheses not validated due to review failure are never concerns; they are listed as excluded, with reasons.

Selection is one of:

- omitted or `all`: every concern;
- `published`: every concern with a recorded published comment in the source record or in a follow-up record whose lineage names the source;
- explicit canonical IDs such as `H2,H5`;
- published comment URLs or IDs, mapped to concerns only through recorded comment identifiers: the source record's publication mapping and the mappings of follow-up records whose lineage names the source, each keyed by source run ID plus canonical ID.

A comment published by an earlier follow-up therefore selects the same source concern as one published by the full review. These mappings are provenance for selection and thread state, never validator evidence.

Completeness is decided for each requested concern, before any validator is dispatched. A concern is **complete** only when its source record preserves, each present and non-empty, the original hypothesis as a full canonical hypothesis record whose canonical ID equals the requested concern's ID (`none` is a valid value for context references), the original outcome and evidence, and the original reviewed head SHA. A requested ID or comment with no preserved original concern, with incomplete original evidence (any of those missing, empty, or a hypothesis ID that differs from the requested concern's), or with ambiguous evidence (a comment identifier recorded for more than one concern, or a run ID or record path that resolves to more than one record) is reported as incomplete coverage with a specific reason naming the concern and each missing, empty, mismatched, or ambiguous item. It is never reconstructed from a comment body, report prose, memory, or a fresh interpretation of the code, and it never widens the run into a full review.

Incomplete evidence invalidates only its own concern. A legacy source record that discovery accepts stays the source record even when some of its concerns lack complete original evidence, including a record preserved before the canonical hypothesis record was fully enumerated. Under `all`, `published`, or an explicit selection, its complete concerns remain eligible for selection and validation alongside the reported incomplete ones.

### Confirm once

One confirmation, with no separate scope question, shows the source record with its run ID, path, completeness, and reviewed head; the new head; the exact selected set; the excluded set and incomplete coverage with reasons; each selected concern's prior follow-up context; and the deferred set. If the new head equals the source record's reviewed head, say so and require explicit confirmation to continue.

At that confirmation, the user may mark selected concerns **deferred**, with an optional reason. Deferred concerns are not revalidated and are reported as deferred, never as addressed. A deferral applies only to that run; a later follow-up shows it as prior context and does not apply it automatically.

### Focused validation

Follow-up mode skips reviewer selection, the scout capacity check, and the scout wave, and the report states that no scouts ran. Preflight still verifies that both validator agents are installed. Because no scout capacity result exists, static validator concurrency comes from the **follow-up validator capacity** the active harness declares in `SKILL.md`: a validator-only capacity read or a fixed conservative bound, with no scout selection or admission. When it reports no available slot before any validator launches, stop validation and report every selected concern as Incomplete, not validated due to review failure. Every other mechanism runs unchanged against the new head: freshness, one immutable target-bound context snapshot with no scout manifests, one pinned coordinator-owned worktree with its exact baseline and scratch directory, workspace authorizations, one late-bound `reviewers/validator-manifest` derived from the selected concerns' context references, the static phase with its existing queue in canonical ID order and its existing backpressure and refusal rules, the sequential writable phase with baseline restoration, operational-failure handling, and cleanup.

Each `deep-review-validator-static` and `deep-review-validator-probe` invocation runs the follow-up adjudication in `reviewers/validator.md` and receives exactly one complete original concern record (canonical ID, hypothesis, original outcome and evidence, and original reviewed head SHA) exactly as the source record preserves it, the new pinned worktree, and the base and new head SHAs. It may inspect the diff from the original head to the new head when the original head object is present locally, and must not fetch it. Follow-up validators never receive GitHub discussion, thread state, author claims, or prior follow-up statuses.

The follow-up adjudication returns, from fresh evidence at the new head:

- **Addressed**: fresh evidence, such as a removed path, a new guard, invariant, contract, or test, or a bounded check, establishes that the original failure or structural cost no longer applies, and cites the change responsible.
- **Not addressed**: fresh evidence establishes that it still applies, with current severity and, for a partial fix, what changed and what remains.
- **Incomplete**: fresh evidence cannot establish either, and the outcome names the missing evidence or operational limitation.
- **Needs probe**: the existing internal transition and schema; it is never reported.

Statuses come only from the follow-up adjudication. The original outcome is context, never evidence: an original Finding is not presumed to persist, and an original Unresolved item is not presumed fixed. A concern not attempted because of operational failure is Incomplete as not validated due to review failure. A head change before presentation makes every status stale; report reviewed and current SHAs and require a rerun.

### Report, thread state, and publication

Use the follow-up variant in `references/output-template.md`, labeled "Follow-up revalidation: not a full PR review". It never shows PASS or a `No findings` headline and states that code outside the selected concerns was not reviewed.

GitHub thread state (open, resolved, outdated, not published, or unknown) is a separate column. Retrieve it only after validation finishes and only for recorded comment identifiers, from the source record and from follow-up records whose lineage names the source. A retrieval failure leaves it unknown without changing any code-level status, and a resolved thread never makes a concern addressed.

Follow-up is read-only toward GitHub by default. A new comment the user requests for a Not addressed concern is drafted from its fresh evidence and goes through the existing `references/pr-review-overlap.md` and `references/pr-review-comments.md` gates unchanged. Follow-up never replies to, edits, resolves, or reopens an existing thread.

The follow-up run state carries a record identity with mode `follow-up` and its full lineage, preserves each selected concern's complete original concern record verbatim, as the source record held it, and records each status, deferral, and thread state. It is preserved at cleanup like every other run.

### Follow-up runtime acceptance

The follow-up receipt keeps every full-review row and marks the full-review-only rows (zero hypotheses, surviving hypotheses, multiple selected scouts, insufficient scout capacity, and scout failure) as not run. It adds these rows, recorded under the same observed-only rules:

- fixed concern: whether fresh evidence citing the responsible change produced Addressed;
- persisting defect: whether fresh evidence produced Not addressed with current severity;
- partial fix: whether Not addressed named what changed and what remains;
- missing prior evidence: whether a requested concern without complete preserved original evidence became incomplete coverage with a specific reason and no reconstruction, while the source record's complete concerns still proceeded;
- explicitly deferred concern: whether the user's deferral skipped revalidation and was reported apart from Addressed;
- resolved thread with a persisting defect: whether the resolved thread state stayed separate and the concern stayed Not addressed;
- head change during revalidation: whether every status became stale with reviewed and current SHAs reported;
- multiple selected concerns: whether each selected concern received one independent follow-up adjudication in canonical ID order;
- follow-up validator capacity: whether static validator concurrency came from the harness's follow-up validator capacity without any scout capacity read, with refusals handled as backpressure;
- record discovery in a later session: whether a new session found the source record by repository and target;
- discovery when the newest record is a narrower follow-up: whether the latest full-review record stayed the source and the follow-up supplied only prior context;
- record preservation from a linked worktree: whether records reached the canonical record root of the clone's Git common directory;
- record preservation under a write restriction: whether outcomes stayed unchanged and the run directory was retained with exact paths reported.
