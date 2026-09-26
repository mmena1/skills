# Glossary

## Review run

- **Review run**: One coordinated execution of multiple read-only scouts, capacity-bounded static hypothesis adjudications, and sequential writable probe adjudications.
- **Review workspace**: The coordinator-owned disposable area belonging to one review run.
- **Review target**: The committed PR, branch, or commit range being reviewed. When no target is supplied, the caller's current branch is the target; a detached caller has no implicit target.
- **Caller checkout**: The repository and checked-out branch from which a run starts. It is launch context, not necessarily the review target.
- **PR gate review**: A review that requires a clean caller checkout only when the checkout overlaps the review target. A different target may be reviewed from a dirty checkout, but working-tree changes never become review input.
- **Run state**: The consolidated coordinator-owned record of baseline, provenance, hypotheses, validation outcomes, report data, incomplete status, and cleanup status that must survive disposable worktree changes.
- **Operational instructions**: Instructions from the materialized target that govern behavior. Ignored context is supplemental evidence unless supported repository configuration explicitly designates it otherwise.

## Context

- **Ignored context artifact**: Local material excluded from Git tracking that may provide supplemental intent, requirements, architecture, standards, or decision context.
- **Context snapshot**: One immutable, coordinator-owned collection of selected ignored artifacts.
- **Reviewer context manifest**: The list of core and bounded snapshot entries a scout or validator should read. It does not copy artifacts.
- **Mechanical context capture**: The fixed coordinator or harness operation that copies validated artifact bytes without model-authored reconstruction or generated per-run capture machinery.

## Outcomes

- **Hypothesis**: An admission-qualified scout concern about the committed target, grounded in changed code or a changed behavior-bearing path, awaiting independent adjudication.
- **Finding**: A hypothesis independently established by the validator with final severity and evidence of actual reachability and impact.
- **Disproved**: A hypothesis rejected by validation; it is not user-visible.
- **Unresolved**: Validation was attempted but could not establish or reject a hypothesis; it is not a Finding and maps to `discuss`.
- **Static adjudication**: A capacity-bounded read-only validation phase that queues canonical hypotheses in ID order and may return a final outcome or the internal `Needs probe` transition.
- **Writable probe**: A bounded, sequential validation check performed only after static adjudication returns `Needs probe`.
- **Needs probe**: An internal transition stating that static evidence cannot settle a hypothesis and identifying the unresolved question and cheapest decisive writable check; it is never user-visible.
- **Not validated due to review failure**: A hypothesis the validator could not attempt because the run failed; it makes the review incomplete and is distinct from Unresolved.
- **Stated intent**: The change goal expressed by the target PR or commits; `unknown` when neither source provides it.
- **Action**: The recommended next step: `fix-now`, `discuss`, or `follow-up`.
- **fix-now**: A Finding with a small, unambiguous fix based on final severity and fix size.
- **discuss**: An Unresolved item or a Finding needing author context or a tradeoff decision.
- **follow-up**: A Finding that is real but too large or out of scope for the current change.

## Publication

- **Publication boundary**: The line separating private or local context from team-visible evidence suitable for a GitHub review comment. Ignored context does not cross it automatically.
- **Publication payload**: The exact team-visible review content approved for publication, preserved with its publication receipt when publication occurs.
- **Comment scope**: Whether a comment addresses a point, a method or design, or a compact range.
- **Source anchor**: The smallest semantically representative code location for a comment. Publication coordinates must be mechanically valid for the current head as well as semantically representative.

The protocol is defined in `protocol.md` and follows:

`hypothesis → static adjudication → finding | disproved | unresolved | needs probe → writable probe → finding | disproved | unresolved`
