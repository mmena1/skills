## What it does

`evaluate-model` recommends the starting model, reasoning effort, and, when the current context is visible, whether an upcoming task belongs in the current or a fresh session. It routes by the expected cost of reaching a correct result: uncertainty in early choices, interacting invariants, coupling, verification delay, and the blast radius of rework.

It is an advisor only. It may inspect the named target skill, issue, spec, or code far enough to classify the task, then it reports the route and stops. It does not run the skill, begin the work, change the selected model, create another session, or dispatch an agent.

## When to reach for it

Invoke it explicitly as `/evaluate-model <next-task>` before starting work whose route is not obvious. When `<next-task>` names another skill, the evaluator reads that skill's current `SKILL.md` rather than routing from a remembered summary.

The default routes are:

| Route | Best fit |
| --- | --- |
| **GPT-5.6 Luna — Medium** | Bounded application of established patterns with explicit acceptance criteria and cheap local verification |
| **GPT-5.6 Sol — High** | Important abstractions, interacting invariants, lifecycle or state semantics, architecture, design, or deep review |
| **GPT-6 Astra — High** | Consequential uncertainty across independently complex systems, late verification, or subtle semantic errors with expensive downstream rework |

Task length and file count do not move a task upward by themselves. A large deterministic migration can stay Luna; a small probabilistic update whose errors look plausible can require Astra.

## Session recommendation

`Session: current` means the task directly continues focused work and the accumulated evidence is coherent and useful. `Session: fresh` means independence matters, the objective or phase has changed, assumptions were superseded, or stale and abandoned approaches would bias the work. A different model does not automatically imply a fresh session. When the evaluator cannot see enough session state, it gives a conditional instead of pretending to know.

## Examples

| Invocation | Expected direction |
| --- | --- |
| `/evaluate-model /implement a narrowly scoped change to an established normalization path with explicit acceptance criteria and strong tests` | Luna Medium |
| `/evaluate-model /implement a specified lifecycle with content identity, stale-completion rejection, atomic activation, bounded retries, and lineage invariants` | Sol High |
| `/evaluate-model /implement a probabilistic belief updater combining multiple evidence sources, open-world uncertainty, reversible corrections, and late calibration` | Astra High |
| `/evaluate-model /improve-codebase-architecture after the first bounded domain pipeline` | Normally Sol High |
| `/evaluate-model independent architecture review of the complete end-to-end production loop after implementation` | Potentially Astra High in a fresh session |

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
