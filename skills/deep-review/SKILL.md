---
name: deep-review
description: Run a strict PR-gate review of a committed PR, branch, or commit range with parallel read-only scouts and independent hypothesis validation.
disable-model-invocation: true
triggers:
  - user
argument-hint: "[PR number | PR URL | branch | commit range]"
---

# Deep Review

Read `protocol.md` completely, then execute that protocol with the harness's native subagent mechanism and the installed deep-review agents. `GLOSSARY.md` defines the review vocabulary. Review only committed targets; uncommitted working-tree review is out of scope.

The coordinator runs on the session's model. Only the roles below pin their own model and limits.

## Roles

The protocol uses four roles. Every role runs as the native agent named `deep-review-<role>`, and that name is the same on every harness.

| Role | Native agent | Runs |
| --- | --- | --- |
| scout | `deep-review-scout` | The `bugs`, `conventions`, `history`, and `docs` scouts. Pass the matching `reviewers/lenses/<slug>.md`. |
| structural | `deep-review-structural` | The `structural` scout. |
| validator-static | `deep-review-validator-static` | One static adjudication per canonical hypothesis. |
| validator-probe | `deep-review-validator-probe` | One sequential writable probe per `Needs probe` outcome. |

`harnesses/roles.toml` pins each role's model, tools, and sandbox, and the installer links the agents generated from it. Agents are generated for Codex, Devin, and Claude Code. No Claude Code agent sets `permissionMode`, so the user's own permission settings still apply to every role. If the active harness has no installed `deep-review-*` agent for a required role, stop and report the missing role.

## Orchestration

- Check scout capacity with the harness mechanism below before analysis. Stop with required and available counts when the complete selected scout set cannot launch simultaneously. Capacity already occupied outside the run may only become visible at launch; the harness mechanism says how such a refusal is handled.
- Launch every selected scout in one concurrent wave and wait for the complete wave. Preserve completed scout evidence when one invocation fails and mark the run incomplete.
- When hypotheses survive deduplication, queue canonical hypotheses in `H1`, `H2`, … order and launch one `deep-review-validator-static` invocation per hypothesis using the static validator capacity below. Refill a slot whenever an invocation finishes, including after failure or timeout, until every queued hypothesis has been attempted exactly once. Static failures mark the run incomplete but do not stop queue drainage.
- After every static invocation has finished, verify the baseline and launch `deep-review-validator-probe` sequentially only when the static phase completed without failure. Any static failure or timeout blocks the entire writable phase.
- Capture the harness identity and version and the native agent names for the runtime acceptance receipt described in `runtime-acceptance.md`. Mark only coordinator-observed paths as `PASS` or `FAIL`; leave every other row `NOT EXERCISED`.
- Never substitute the coordinator or a built-in generic agent for a deep-review role. Never change the user's global harness concurrency settings.

## Harness mechanisms

Harnesses differ only in these mechanisms. The protocol's semantics are identical on each.

| Mechanism | Codex | Devin | Claude Code |
| --- | --- | --- | --- |
| Scout capacity check | Inspect the active subagent capacity, including `agents.max_concurrent_threads_per_session`. | Determine the available concurrent background subagent capacity. | Read the concurrent subagent cap from `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (20 when unset) and subtract the subagents this session already has running. When the selected scouts exceed that, stop before launching any scout and report required and available counts. Otherwise launch every selected scout as parallel agent calls in one message. Slots occupied outside the session are visible only at launch: a `Concurrent subagent limit reached` refusal or another non-starting scout launch counts as insufficient capacity, stops the run, and marks it incomplete, and the receipt records that part of the gate as observed at launch. |
| Static validator capacity | The maximum safe capacity found by the capacity check. | The maximum safe capacity found by the capacity check. | At most 4 slots, and never more than the scout capacity check's available count, refilled in canonical hypothesis order. A `Concurrent subagent limit reached` refusal is backpressure, not an adjudication: return that hypothesis to the head of the queue and relaunch it when one of this run's validator invocations finishes, which is not an immediate retry. A refusal while none of this run's validator invocations is running, including for the writable probe, means no slot can free: stop validation and report every unattempted hypothesis as not validated due to review failure. |
| Read-only scouts and static validators | Enforced by the `read-only` sandbox. | Instruction-enforced. These roles keep `exec` for read-only Git inspection, so their no-write and no-probe contract relies on the reviewer instructions. | Instruction-enforced. These roles have `Read`, `Grep`, `Glob`, and `Bash`. Claude Code does not confine an agent's `Bash` to the patterns in its tool list: a pattern entry such as `Bash(git log:*)` only feeds permission decisions, so a session whose permissions allow `Bash` lets the role run any command. Their no-write and no-probe contract therefore relies on the reviewer instructions and the user's own permission settings. |
| Writable probe | `workspace-write` sandbox. | `write` and `edit` tools. | `Edit` and `Write` tools, with `Bash`. |

A harness mechanism that cannot preserve a protocol invariant stops the review rather than degrading it. The shared protocol owns target resolution, state meanings, failure behavior, reporting, publication, and cleanup.
