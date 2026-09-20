## What it does

`evaluate-model` recommends the starting model, reasoning effort, and, when the current context is visible, whether an upcoming task belongs in the current or a fresh session. It routes by the expected cost of reaching a correct result: semantic and boundary novelty, verification locality, determinism, plausible-wrong risk, and the blast radius of rework.

It is an advisor only. It may inspect the named target skill, issue, spec, or code far enough to classify the task, then it reports the route and stops. It does not run the skill, begin the work, change the selected model, create another session, or dispatch an agent.

## When to reach for it

Invoke it explicitly as `/evaluate-model <next-task>` before starting work whose route is not obvious. When `<next-task>` names another skill, the evaluator reads that skill's current `SKILL.md` rather than routing from a remembered summary.

The default routes are:

| Route | Best fit |
| --- | --- |
| **GPT-5.6 Luna: Medium** | Bounded application of explicit semantics inside established boundaries with deterministic, cheap local verification |
| **GPT-5.6 Sol: High** | Important new abstractions, ownership decisions, lifecycle protocol design, ambiguous domain contracts, architecture, design, or deep review |
| **GPT-6 Astra: High** | Consequential uncertainty across independently complex systems, late verification, or subtle semantic errors with expensive downstream rework |

Task length, file count, and invariant count do not move a task upward by themselves. Many acceptance criteria, identity fields, stable hashing, fail-closed behavior, property tests, validation, ordering constraints, or domain types within one adapter boundary can all remain Luna when their semantics are explicit and directly testable. A small probabilistic update whose errors look plausible can require Astra.

Before promoting from Luna, the evaluator asks whether semantics or boundaries must be discovered, whether important behavior is locally and deterministically verifiable, how far rework would propagate, and whether a wrong implementation could pass local checks and still look correct.

## Session recommendation

Session placement follows the canonical phase-boundary tree. A phase change alone does not require a fresh session: report `Session: current` when the tree selects Continue, and `Session: fresh` when it selects a new session boundary such as `/clear`, `/handoff-doc`, or `/compact`. For Codex, if the recommended model differs from the observable current model, report `Session: fresh`; if the current model is unknown, state that condition instead of guessing. When the evaluator cannot see enough phase or model state, it gives a conditional instead of pretending to know.

## Examples

| Invocation | Expected direction |
| --- | --- |
| `/evaluate-model /implement a bounded candidate normalizer for a known GRE envelope with explicit identity and completeness semantics, stable IDs and hashes, and fixture/property tests behind an established adapter` | Luna Medium. The work applies explicit deterministic invariants with local oracles and localized rework. Escalate if repository-owned identity semantics conflict, GRE semantics are unresolved, or the established seam must change. |
| `/evaluate-model /implement a profile lifecycle whose content identity, activation, lineage, stale completion, retries, supersession, and reuse semantics define a new protocol` | Sol High. The task must reason about ownership and how lifecycle invariants compose; local checks do not prove the abstraction as a whole. |
| `/evaluate-model /implement a probabilistic belief updater combining multiple evidence sources, open-world uncertainty, reversible corrections, and late calibration` | Astra High |
| `/evaluate-model /improve-codebase-architecture after the first bounded domain pipeline` | Normally Sol High |
| `/evaluate-model independent architecture review of the complete end-to-end production loop after implementation` | Potentially Astra High in a fresh session |

## Common questions

**Does a different recommended model always mean a fresh session?**

For Codex, yes when the current model is observable: the evaluator reports a fresh session because the main model is not switched inside an existing session. When the current model is unknown, it states the condition instead of guessing. The canonical phase-boundary policy still decides the session boundary when the model already matches.

**Does a phase change always require a fresh session?**

No. The evaluator follows the canonical phase-boundary tree, which checks whether the next phase needs the current session as a primary source or still fits the smart zone before considering `/clear`, `/handoff-doc`, a subagent, or `/compact`.

## Prior-art boundary

The design borrows the useful expected-rework signals from [LunarXuan/task-model-router](https://github.com/LunarXuan/task-model-router): uncertain early choices, dependency coupling, verification timing, and recovery cost. This skill deliberately leaves out that project's automatic launcher, child-agent delegation, scripts, scoring, and runtime replay. The result is a small SKILL.md policy for user-owned pre-task selection.

## It's working if

- The recommendation names a concrete model and reasoning effort and gives 2–4 task-specific reasons.
- Sol and Astra recommendations explain why the nearest weaker route is insufficient.
- The target skill's `SKILL.md` is inspected before making skill-specific claims.
- The final line preserves the exact next invocation when it can be derived safely.
- Nothing from the target workflow has started when the response ends.

## Where it fits

`evaluate-model` is a standalone pre-task router. [ask-matt](https://aihero.dev/skills-ask-matt) answers which skill or flow fits; `evaluate-model` answers which model, effort, and session boundary should run the already identified task. Runtime capability escalation remains governed by the user's global instructions rather than this skill.
