---
name: evaluate-model
description: Recommend a starting model, reasoning effort, and session boundary for one upcoming task, then stop.
disable-model-invocation: true
triggers:
  - user
---

# Evaluate Model

Recommend how to start one specific upcoming task. This is a pre-task advisor: inspect only far enough to classify the work, give the recommendation, and stop. The user owns model selection and whether to start a new session.

## Evaluate the task

1. Identify the exact task and preserve the next invocation or prompt.
2. When the request names another skill, locate and read that skill's current `SKILL.md` before classifying it. Its actual workflow supplies the baseline task class; a remembered summary does not. If the file cannot be inspected, state that limitation and lower confidence rather than inventing its behavior.
3. Read referenced issues, specs, repository instructions, context, or code only when a concrete unknown could change the route. Gather task-classification evidence, not a solution. Stop inspecting once more detail is unlikely to change the recommendation.
4. Route by the expected cost of reaching a correct result: consequential early uncertainty, interacting invariants, dependency depth and coupling, how late errors become visible, semantic difficulty, and the blast radius and recovery cost of a plausible wrong attempt.

Task length, prompt length, file count, line count, and prestige are not routing signals. A supplied plan lowers uncertainty only when it settles the important choices instead of hiding them.

## Starting routes

### GPT-5.6 Luna: Medium

Default to Luna Medium when acceptance criteria are explicit, the architecture and patterns already exist, the work mainly applies them, and tests or contracts expose mistakes locally and cheaply. Large deterministic or mechanical changes can remain here when rework stays bounded.

### GPT-5.6 Sol: High

Use Sol High when the task creates an important abstraction; composes multiple nontrivial invariants; depends on lifecycle, identity, concurrency, staleness, ordering, or state-machine semantics; or performs architecture, design, or deep review. The problem may span components, but its objective and boundaries are still substantially specified. Prefer Sol as the normal stronger route when a locally plausible answer could violate a deeper invariant.

### GPT-6 Astra: High

Reserve Astra High for unusually expensive reasoning mistakes: consequential early choices remain uncertain; many downstream steps depend on them; multiple independently complex systems or domains interact; verification is late or end-to-end; or semantic, probabilistic, or statistical errors can look convincing while invalidating substantial later work. Astra is a risk route, not a synonym for complex.

These are the v1 defaults. Recommend a different supported reasoning effort only when concrete task evidence makes a default mismatched, and explain the deviation.

## Skill baseline

Let the inspected target skill establish the baseline, then let the specific task raise it when justified. Typical starting points are `/implement` at Luna Medium and architecture, design, or deep-review work at Sol High. A substantially specified lifecycle abstraction can stay Sol; a major cross-system evaluation with late verification can rise to Astra. These are tendencies, not a hardcoded name lookup.

## Session boundary

Choose the model and effort first. Then apply the canonical phase-boundary policy in `ask-matt/PHASE-BOUNDARIES.md` when that file is available. Its ordered tree owns the context decision: continue when the next phase needs the current session as a primary source or still fits the smart zone; otherwise choose the policy's least costly precise boundary such as `/clear`, `/handoff-doc`, a subagent, or `/compact`.

Report `Session: current` when that policy selects Continue. Report `Session: fresh` when it selects a new session boundary such as `/clear`, `/handoff-doc`, or `/compact`; name the boundary in the reasons. A subagent recommendation can remain current-session work because it leaves the main session intact.

Finally apply the harness overlay. For Codex, determine the current model when it is observable. If it differs from the recommended model, report `Session: fresh` and tell the user to select the recommended model in a new Codex session. If the current model is unknown, state that condition rather than guessing. This overlay takes precedence over Continue because Codex does not switch the main model inside an existing session.

When phase-boundary or current-model state is not observable, omit the `Session` field and give a short conditional sentence instead of inventing state.

## Output

Keep the recommendation compact:

```text
Recommended: GPT-5.6 Sol: High
Confidence: High
Session: fresh

Why:
* 2–4 concrete task properties

Route comparison:
* Luna: explain why Sol is unnecessary when Luna is selected.
* Sol: explain why Luna is insufficient, and why Astra would not reduce expected rework enough when that distinction is useful.
* Astra: explain why Sol is insufficient.

Escalate if:
* concise evidence that would change the route during execution

Next:
`/implement issue 21`
```

Use qualitative confidence to reflect evidence completeness, not model prestige. When recommending Sol or Astra, explain why the nearest weaker route is insufficient. Explain why the nearest stronger route is unnecessary when that distinction is useful. End with the exact next invocation or prompt after removing `/evaluate-model` when it can be derived safely.

Escalation triggers are task-specific signs that the starting assumptions failed, such as newly discovered cross-system ownership, irreconcilable invariants, or loss of local verification. Keep them concise; global runtime policy owns capability-ceiling handling.

## Calibration examples

- Extending an established candidate-normalization path with explicit acceptance criteria and strong tests: Luna Medium.
- Implementing a specified profile-generation lifecycle with identity, stale-completion rejection, atomic activation, retries, and lineage: Sol High.
- Implementing a probabilistic opponent-belief updater across multiple evidence sources and meanings with late calibration: Astra High.
- Running `/improve-codebase-architecture` after the first bounded domain pipeline: normally Sol High unless repository evidence makes it a major cross-system decision.
- Independently reviewing a complete end-to-end production loop after implementation: potentially Astra High in a fresh session because independence, subsystem interaction, and late verification increase rework risk.

## Stop boundary

Read-only inspection for routing is the full scope. Do not invoke the target skill, begin its workflow, solve the task, edit its artifacts, switch models, create a session, dispatch an agent, call an external model, or persist a routing record. Return the recommendation and stop.
