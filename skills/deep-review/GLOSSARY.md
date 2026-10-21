# Glossary

## Review run

- **Review run**: One coordinated execution of multiple static scouts, capacity-bounded static hypothesis adjudications, and sequential writable probe adjudications. A follow-up revalidation run executes only the validation phases.
- **Review workspace**: The coordinator-owned disposable area belonging to one review run.
- **Review target**: The committed PR, branch, or commit range being reviewed. When no target is supplied, the caller's current branch is the target; a detached caller has no implicit target.
- **Caller checkout**: The repository and checked-out branch from which a run starts. It is launch context, not necessarily the review target.
- **PR gate review**: A review that requires a clean caller checkout only when the checkout overlaps the review target. A different target may be reviewed from a dirty checkout, but working-tree changes never become review input.
- **Run state**: The consolidated coordinator-owned record of baseline, provenance, hypotheses, validation outcomes, report data, incomplete status, and cleanup status that must survive disposable worktree changes.
- **Run ID**: The unique name of a run's directory, which also names its preserved record.
- **Record identity**: The header of a run state that lets a later session match it to a target: format version, run ID, mode (`full` or `follow-up`), repository identity, target kind and key, base and reviewed head SHAs, completion time, completeness status, and, for a follow-up, its lineage.
- **Record root**: `<git-common-dir>/deep-review/records/`, where `<git-common-dir>` is the canonical absolute path of the caller repository's Git common directory. Every worktree of a clone shares it, and it is never tracked.
- **Preserved record**: A run's `run-state.json`, and its `final-report.md` and `publication-receipt.json` when produced, copied byte for byte under the record root before the run directory is removed.
- **Pre-preservation snapshot**: The run state and final report as copied into a preserved record. It is frozen when the run-state copy starts, holds only what is knowable before preservation, and is never updated to claim or revise a preservation outcome.
- **Preservation closeout**: The coordinator's report to the user, after the copies and their byte-equality verification have finished, of what preservation actually achieved: the verified record path, or the precise limitation and retained paths. It is separate from the pre-preservation snapshot.
- **Operational instructions**: Instructions from the materialized target that govern behavior. Ignored context is supplemental evidence unless supported repository configuration explicitly designates it otherwise.

## Context

- **Ignored context artifact**: Local material excluded from Git tracking that may provide supplemental intent, requirements, architecture, standards, or decision context.
- **Context snapshot**: One immutable, coordinator-owned collection of selected ignored artifacts.
- **Reviewer context manifest**: The list of core and bounded snapshot entries a scout or validator should read. It does not copy artifacts.
- **Mechanical context capture**: The fixed coordinator or harness operation that copies validated artifact bytes without model-authored reconstruction or generated per-run capture machinery.

## Outcomes

- **Hypothesis**: An admission-qualified scout concern about the committed target, grounded in changed code or a changed behavior-bearing path, awaiting independent adjudication.
- **Finding**: A hypothesis independently established by the validator with final severity and evidence of actual reachability and impact, or for a structural finding evidence meeting the structural evidence standard.
- **Disproved**: A hypothesis rejected by validation; it is not user-visible.
- **Unresolved**: Validation was attempted but could not establish or reject a hypothesis; it is not a Finding and maps to `discuss`.
- **Static adjudication**: A capacity-bounded source-level validation phase that queues canonical hypotheses in ID order and may return a final outcome or the internal `Needs probe` transition.
- **Scratch file**: A disposable intermediate analysis file that a scout or static validator keeps in the run's `scratch/` directory beside the pinned worktree. It is ordinary review activity, is never evidence or part of a preserved record, and is removed at cleanup even when the run directory is retained.
- **Writable probe**: A bounded, sequential validation check performed only after static adjudication returns `Needs probe`.
- **Needs probe**: An internal transition stating that static evidence cannot settle a hypothesis and identifying the unresolved question and cheapest decisive writable check; it is never user-visible.
- **Not validated due to review failure**: A hypothesis the validator could not attempt because the run failed; it makes the review incomplete and is distinct from Unresolved.
- **Stated intent**: The change goal expressed by the target PR or commits; `unknown` when neither source provides it.
- **Action**: The recommended next step: `fix-now`, `discuss`, or `follow-up`.
- **fix-now**: A Finding with one clearly correct remedy and a small, unambiguous fix.
- **discuss**: An Unresolved item or a Finding whose remedy needs the author's design or tradeoff judgment.
- **follow-up**: A Finding with one clearly correct remedy that is too large or out of scope for the current change.

## Follow-up revalidation

- **Follow-up revalidation**: A `/deep-review follow-up` run that independently revalidates selected concerns from a preserved prior review record against a newly pinned head. It runs no scouts and is not a full PR review. It is unrelated to the `follow-up` Action, which classifies a Finding.
- **Source record**: The preserved full-review record whose concerns a follow-up revalidates: the latest full-review record matching the target, or one the user selects explicitly. A follow-up record is never a source record.
- **Lineage**: The source full-review run ID and every earlier follow-up run ID a follow-up record built on. Follow-up records in a source's lineage supply prior status and provenance only, including the comments they published and the concerns those comments map to.
- **Concern**: A Finding or Unresolved outcome in the source record. Disproved hypotheses and hypotheses not validated due to review failure are never concerns.
- **Concern inventory**: Every concern in the source record, keyed by canonical ID. A follow-up record never narrows it.
- **Canonical hypothesis record**: A hypothesis exactly as the run state persists it after deduplication: canonical ID, original scout IDs and origins, title, source location, potential severity, source evidence, expected impact, falsification condition, suggested validation, and context references. Merging keeps all materially distinct evidence and provenance.
- **Original concern record**: One concern exactly as the source record preserves it: canonical ID, canonical hypothesis record, original outcome and evidence, and original reviewed head SHA. It is the only concern input a follow-up validator receives.
- **Incomplete coverage**: A requested concern or comment with no preserved original concern, or with incomplete or ambiguous original evidence, decided per concern before validator dispatch. It is reported with a specific reason, never reconstructed, and never invalidates the source record's complete concerns.
- **Follow-up validator capacity**: The static validator concurrency a harness declares for follow-up revalidation, from a validator-only capacity read or a fixed conservative bound, because follow-up runs no scout capacity check.
- **Follow-up adjudication**: The validator's judgment of one original concern record from fresh evidence at the new head, returning Addressed, Not addressed, Incomplete, or the internal `Needs probe` transition.
- **Addressed**: Fresh evidence establishes that the original failure or structural cost no longer applies and cites the change responsible.
- **Not addressed**: Fresh evidence establishes that the original failure or structural cost still applies, with current severity and, for a partial fix, what changed and what remains.
- **Incomplete**: Fresh evidence cannot establish Addressed or Not addressed; the status names the missing evidence or operational limitation. It is a per-concern follow-up status, distinct from an incomplete run and from incomplete coverage.
- **Deferred**: A selected concern the user explicitly chose not to revalidate in one follow-up run. It is never reported as addressed; a later follow-up shows it as prior context and does not apply it automatically.
- **Thread state**: The GitHub state of a concern's recorded comment (open, resolved, outdated, not published, or unknown). It is reported separately and never changes a follow-up status.

## Structural review

- **Responsibility scan**: The structural reviewer's inspection of a substantial changed function or flow for responsibility mixing.
- **Responsibility mixing**: At least two independently nameable responsibilities with separate reasons to change combined in one function or flow. A loop, nested loop, conditional, or long function is not responsibility mixing on its own.
- **Structural cost**: A reasoning or maintenance cost that an identifiable task bears in the reviewed code: understanding a behavior or invariant, locating relevant knowledge, determining affected callers or states, or making a coherent change without scattered edits or hidden consequences. A count of lines, helpers, layers, or abstractions is not a structural cost.
- **Behavior-preserving alternative**: A concrete structural alternative that keeps behavior, contracts, invariants, and constraints and demonstrably reduces a structural cost without introducing an equal or greater reasoning or maintenance burden. It is proof that the cost is incidental, not a remedy. One that only renames or relocates the cost, hides relevant policy, obscures an invariant, or scatters knowledge is not one. It may add or remove abstractions, indirection, helpers, adapters, explicit state types, seams, boundaries, or code; neither direction is inherently better.
- **Structural evidence standard**: The one threshold for admitting, validating, and reporting a structural concern: a demonstrated structural cost plus a behavior-preserving alternative. A preference for another design, technique, fewer lines, fewer helpers, or fewer layers does not meet it. No architectural or programming paradigm, technique, or abstraction count is evidence for admission, validation, rejection, severity, or remedy, and conformity to or departure from any design philosophy neither establishes nor disproves a structural concern.
- **Structural finding**: A Finding about maintainability rather than runtime behavior, established under the structural evidence standard. Correct behavior does not refute it, and it stays distinct from correctness findings about the same code.

## Publication

- **Publication boundary**: The line separating private or local context from team-visible evidence suitable for a GitHub review comment. Ignored context does not cross it automatically.
- **Publication payload**: The exact team-visible review content approved for publication, preserved with its publication receipt when publication occurs.
- **Submission outcome**: What the review submission call established: `submitted`, `rejected`, or `ambiguous`. It is recorded independently of read-back verification and an `ambiguous` outcome is never replayed automatically.
- **Read-back verification**: The comparison of the comments published under a submitted review against the publication payload, with outcome `verified`, `mismatch`, or `verification incomplete`. Omitted fields yield `verification incomplete`, never `mismatch`, and no verification outcome authorizes resubmission.
- **Comment scope**: Whether a comment addresses a point, a method or design, or a compact range.
- **Source anchor**: The smallest semantically representative code location for a comment. Publication coordinates must be mechanically valid for the current head as well as semantically representative.

The protocol is defined in `protocol.md` and follows:

`hypothesis → static adjudication → finding | disproved | unresolved | needs probe → writable probe → finding | disproved | unresolved`
