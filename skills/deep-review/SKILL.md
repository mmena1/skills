---
name: deep-review
description: Run a strict PR-gate review of a committed PR, branch, or commit range with parallel read-only scouts and independent hypothesis validation, or use `follow-up` to revalidate selected concerns from a preserved earlier review.
disable-model-invocation: true
triggers:
  - user
argument-hint: "[follow-up] [PR number | PR URL | branch | commit range] [record=<run ID | path>] [all | published | H<n>,... | comment URLs or IDs]"
---

# Deep Review

Read `protocol.md` completely, then execute that protocol with the harness's native subagent mechanism and the installed deep-review agents. `GLOSSARY.md` defines the review vocabulary. Review only committed targets; uncommitted working-tree review is out of scope.

`/deep-review [target]` runs the full review. `/deep-review follow-up [target] [selection]` runs follow-up revalidation, which revalidates selected concerns from a preserved earlier review record against a newly pinned head and is not a full PR review. Only a leading literal `follow-up` token selects it; every other invocation is the unchanged full review, and a branch named `follow-up` is reviewed through `refs/heads/follow-up`. `protocol.md` defines both modes and the argument grammar.

The coordinator runs on the session's model. Only the roles below pin their own model and limits.

## Roles

The protocol uses seven roles. Every role runs as the native agent named `deep-review-<role>`, and that name is the same on every harness. Each scout role embeds the common scout contract followed by exactly its own lens, so a scout receives no lens at runtime.

| Role | Native agent | Runs |
| --- | --- | --- |
| scout-bugs | `deep-review-scout-bugs` | The `bugs` scout. |
| scout-conventions | `deep-review-scout-conventions` | The `conventions` scout. |
| scout-history | `deep-review-scout-history` | The `history` scout. |
| scout-docs | `deep-review-scout-docs` | The `docs` scout. |
| structural | `deep-review-structural` | The `structural` scout. |
| validator-static | `deep-review-validator-static` | One static adjudication per canonical hypothesis. |
| validator-probe | `deep-review-validator-probe` | One sequential writable probe per `Needs probe` outcome. |

`harnesses/roles.toml` pins each role's model, reasoning effort, and supported tool lists, and the installer generates the agents from it for Codex, Devin, and Claude Code. Codex agents use marked regular-file copies because Codex refuses symlinked role configuration files at launch. Claude Code and Devin retain their links, junctions, and copy fallback. Rerun the installer after repository updates to regenerate and refresh the agents. No Claude Code agent sets `permissionMode`, so the user's own permission settings still apply to every role.

Codex native agents inherit the parent's effective sandbox and approval policy. This cannot be overridden per role and applies to the writable probe too. Scouts and static validators obey their read-only instructions; the probe has no additional permissions and can write only as far as the inherited coordinator policy allows. On Codex, reports and runtime acceptance receipts describe the boundary as instruction-enforced plus the inherited session policy. An inherited sandbox that differs from a role's read-only or writable behavior contract is not a review failure.

Before analysis, confirm that the native agent for every selected lens and both validator agents are installed on the active harness; a follow-up run selects no lens and confirms both validator agents. If any is missing, stop and name the missing agent. Never substitute the coordinator, a generic agent, another scout, or another model for it.

## Orchestration

- Apply the scout capacity gate declared by the harness mechanism below, using the exact number of selected scouts. Strict preflight verifies capacity for the complete set before analysis; launch-time admission attempts the complete set concurrently and handles any refusal as specified by that mechanism.
- Launch the native agent of every selected scout, and only those, in one concurrent wave, giving each the same pinned target, worktree, and context root plus its own lens slug and bounded manifest. Wait for the complete wave. Preserve completed scout evidence when one invocation fails and mark the run incomplete.
- When hypotheses survive deduplication, queue canonical hypotheses in `H1`, `H2`, … order and launch one `deep-review-validator-static` invocation per hypothesis using the static validator capacity below. Refill a slot whenever an invocation finishes, including after failure or timeout, until every queued hypothesis has been attempted exactly once. Static failures mark the run incomplete but do not stop queue drainage.
- After every static invocation has finished, verify the baseline and launch `deep-review-validator-probe` sequentially only when the static phase completed without failure. Any static failure or timeout blocks the entire writable phase.
- Capture the harness identity and version, the native agent used for each selected lens, and the validator agents that ran, for the runtime acceptance receipt described in `runtime-acceptance.md`. Mark only coordinator-observed paths as `PASS` or `FAIL`; leave every other row `NOT EXERCISED`.
- Never substitute the coordinator, a built-in generic agent, another scout, or another model for a deep-review role. Never change the user's global harness concurrency settings.
- In follow-up mode, skip reviewer selection, the scout capacity check, and the scout wave, and state in the report that no scouts ran. Discover the source record and confirm the selection once, then queue the selected concerns in canonical ID order through the same `deep-review-validator-static` capacity and sequential `deep-review-validator-probe` rules, giving each invocation exactly one original concern record and never GitHub discussion. Deferred concerns launch no validator.
- At cleanup, preserve the run's records under the record root with the mechanism below. A preservation failure never changes a review's outcomes, report, or publication and never blocks worktree cleanup: report it, keep the run directory, and name the exact retained paths.

## Harness mechanisms

Harnesses differ only in these mechanisms. The protocol's semantics are identical on each.

| Mechanism | Codex | Devin | Claude Code |
| --- | --- | --- | --- |
| Scout capacity check | Inspect the active subagent capacity, including `agents.max_concurrent_threads_per_session`. | Verify that the native agent for every selected lens and both validator agents is installed, then attempt to launch every selected scout concurrently in one wave. Do not query, guess, assume, estimate, infer, or record a numeric available capacity. Treat any refused launch as insufficient capacity observed at launch: do not retry it or launch a replacement, reduce or substitute the set, or fall back to sequential scouting. Let already-started scouts finish and preserve their evidence in run state and report; launch no validator or probe; mark the run incomplete, block PASS, `No findings`, and publication, and run cleanup. | Read the concurrent subagent cap from `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (20 when unset) and subtract the subagents this session already has running. When the selected scouts exceed that, stop before launching any scout and report required and available counts. Otherwise dispatch every selected scout before waiting for any scout to complete. Slots occupied outside the session are visible only at launch: a `Concurrent subagent limit reached` refusal or another non-starting scout launch counts as insufficient capacity, stops the run, and marks it incomplete, and the receipt records that part of the gate as observed at launch. |
| Static validator capacity | The maximum safe capacity found by the capacity check. | A fixed upper bound of at most 4 concurrent slots, filled in canonical hypothesis order; this ceiling does not assume that 4 slots are available and is not derived from a capacity read. A refused launch returns that hypothesis to the head of the queue and it is relaunched only when one of this run's validator invocations finishes, never as an immediate retry. A refusal while none of this run's validator invocations is running, including for the sequential writable probe, means no slot can free: stop validation and report every unattempted hypothesis as not validated due to review failure. | At most 4 slots, and never more than the scout capacity check's available count, refilled in canonical hypothesis order. A `Concurrent subagent limit reached` refusal is backpressure, not an adjudication: return that hypothesis to the head of the queue and relaunch it when one of this run's validator invocations finishes, which is not an immediate retry. A refusal while none of this run's validator invocations is running, including for the writable probe, means no slot can free: stop validation and report every unattempted hypothesis as not validated due to review failure. |
| Read-only scouts and static validators | Instruction-enforced. Their no-write and no-probe contract relies on the reviewer instructions and the coordinator's inherited sandbox and approval policy. | Instruction-enforced. These roles keep `exec` for read-only Git inspection, so their no-write and no-probe contract relies on the reviewer instructions. | Instruction-enforced. These roles have `Read`, `Grep`, `Glob`, and `Bash`. Claude Code does not confine an agent's `Bash` to the patterns in its tool list: a pattern entry such as `Bash(git log:*)` only feeds permission decisions, so a session whose permissions allow `Bash` lets the role run any command. Their no-write and no-probe contract therefore relies on the reviewer instructions and the user's own permission settings. |
| Writable probe | Runs under the inherited coordinator policy with no probe-specific permission. It can write only as far as that policy allows. | `write` and `edit` tools. | `Edit` and `Write` tools, with `Bash`. |
| Record preservation | Documented, not observed: under `workspace-write`, the macOS Seatbelt sandbox keeps `.git` (directory or pointer file), the resolved `gitdir:` target, and `.codex` read-only (`codex-rs/core/README.md`); the Linux and Windows sandboxes are not documented there and are inferred to match. Expect the copy into `<git-common-dir>` to be refused under `workspace-write` unless the user approves that exact command outside the sandbox; `danger-full-access` permits it. A refusal follows the protocol's preservation failure path. | Inferred, neither observed nor documented: no Devin restriction specific to the Git common directory was found, so the copy runs under Devin's ordinary command permissions and prompts. A refusal follows the protocol's preservation failure path. | Documented: `.git` is a protected directory. Writes there are prompted in `default` and `acceptEdits` modes, routed to the classifier in `auto` mode, denied in `dontAsk` mode, and allowed in `bypassPermissions` mode, and settings allow rules do not pre-approve them. Observed on 2026-10-15 (Claude Code 2.1.300, Linux, `auto` mode): a Bash `mkdir` and `cp` from a linked worktree into `<git-common-dir>/deep-review/records/<run-id>/` ran without a prompt, and `cmp` confirmed byte equality. A refusal follows the protocol's preservation failure path. |

A harness mechanism that cannot preserve a protocol invariant stops the review rather than degrading it. The shared protocol owns target resolution, state meanings, failure behavior, reporting, publication, and cleanup.
