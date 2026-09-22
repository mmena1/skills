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
4. Select the model capability needed for a correct result. Distinguish semantics that must be designed or discovered from semantics that are already specified, and assess:
   - **Semantic novelty:** whether the task must define how its invariants compose or apply a defined composition.
   - **Boundary novelty:** whether it creates or changes responsibility boundaries or stays inside an established one.
   - **Verification locality:** whether tests directly prove the important behavior or correctness only emerges across the system.
   - **Determinism:** whether a strong deterministic oracle exists.
   - **Rework radius:** whether a wrong implementation stays localized or invalidates downstream work.
   - **Plausible-wrong risk:** whether an incorrect result can pass local checks and remain convincing.

Interpret interacting invariants through these dimensions. Their number is not an independent promotion signal.

5. Select reasoning effort separately within the chosen model. Estimate the inference, search, and iteration needed to reach and verify a correct result in one run. More Luna reasoning can help execute settled semantics; it does not supply Sol-level judgment when the model capability is the limiting factor. Choose Sol directly when the task characteristics require it, without first trying every Luna effort.
6. Compare the expected cost of reaching a correct result. Account for API dollar cost and, when the user supplies it, Codex or ChatGPT subscription quota as distinct constraints. Do not infer quota use from API prices.

Raw task length, prompt length, file count, line count, and prestige are not model-tier signals. A sustained reasoning and verification loop can justify more effort. A supplied plan lowers uncertainty only when it settles the important choices instead of hiding them.

## Starting routes

Prefer the current GPT-6 Luna, Sol, and Astra models when the harness supports them. Use an older model only for a concrete compatibility constraint.

### Model capability: GPT-6 Luna

Choose Luna when the problem is already decomposed, acceptance criteria explicitly define the semantics, public responsibility boundaries and surrounding architecture already exist, behavior is deterministic and locally verifiable, and rework stays bounded. This includes nontrivial implementation of several interacting invariants when the task applies rather than invents their composition.

Many acceptance criteria, identity fields, canonicalization or stable hashing, fail-closed behavior, property tests, input validation, ordering constraints, a long ticket, or several domain types within one established adapter boundary do not justify Sol on their own. Treat them as implementation details whose significance depends on novelty, verification, and rework risk.

### Model capability: GPT-6 Sol

Choose Sol when the task establishes an important abstraction, decides ownership between components, designs how lifecycle or state-machine invariants compose, resolves ambiguous domain contracts, or coordinates components where local correctness does not prove system correctness. Concurrency, staleness, identity, ordering, retries, supersession, activation, and lineage support Sol when their interactions require substantial semantic reasoning, not merely because those concepts appear in the ticket. Architecture, design, and deep review also normally begin here. Prefer Sol when a locally plausible answer could violate deeper semantics, even if the task is short.

### Model capability: GPT-6 Astra

Reserve Astra for exceptional or frontier work where a Sol mistake would have unusually large downstream cost: consequential early choices remain uncertain; many downstream steps depend on them; multiple independently complex systems or domains interact; verification is late or end-to-end; or semantic, probabilistic, or statistical errors can look convincing while invalidating substantial later work. Astra is a risk route, not a synonym for complex.

### Reasoning effort within the selected model

- **Medium:** obvious local or mechanical work where a short reasoning loop and direct check suffice. This keeps a low-cost Luna path.
- **High:** bounded implementation or general-agent work that needs inference but has a local oracle or limited iteration.
- **Max:** long-horizon autonomous implementation with settled semantics when sustained inference, search, and verification make first-pass quality valuable. GPT-6 Luna Max is a normal starting candidate here.
- **xHigh:** choose when the selected model needs a deep reasoning run but the task evidence does not justify Max. It is an available choice, not a required step between High and Max.

Choose effort for the actual reasoning loop on any selected model. A short ownership decision can call for Sol High; a long, well-specified implementation can call for Luna Max. Neither route requires walking through a fixed effort ladder.

The [GPT-6 launch evidence](https://openai.com/index/introducing-gpt-6-sol-and-luna/) supports high-effort Luna for long-horizon engineering at low API cost, while the coding and mergeability results still show a Sol capability advantage; its general-agent results also show that Max is not universally optimal. Use these findings as calibration, not benchmark thresholds. Revisit the policy when new evidence materially changes the frontier. API dollar cost can favor high-effort Luna, while Codex or ChatGPT subscription quota may behave differently; apply explicit user-provided quota pressure independently.

## Skill baseline

Let the inspected target skill establish the baseline, then let the specific task shape both decisions. For `/implement`, start from GPT-6 Luna Max when the autonomous work is long-horizon and well specified; use Luna High for bounded work and Luna Medium for mechanical changes. Architecture, design, or deep-review work normally starts with Sol capability and an effort justified by its reasoning loop. A substantially specified lifecycle abstraction can stay Sol; a major cross-system evaluation with late verification can rise to Astra. These are tendencies, not a hardcoded name lookup.

## Session boundary

Choose the model and effort first. Then apply the canonical phase-boundary policy in [`PHASE-BOUNDARIES.md`](PHASE-BOUNDARIES.md). Its ordered tree owns the context decision: continue when the next phase needs the current session as a primary source or still fits the smart zone; otherwise choose the policy's least costly precise boundary such as `/clear`, `/handoff-doc`, a subagent, or `/compact`.

Report `Session: current` when that policy selects Continue. Report `Session: fresh` when it selects a new session boundary such as `/clear`, `/handoff-doc`, or `/compact`; name the boundary in the reasons. A subagent recommendation can remain current-session work because it leaves the main session intact.

Finally apply the harness overlay. For Codex, determine the current model when it is observable. If it differs from the recommended model, report `Session: fresh` and tell the user to select the recommended model in a new Codex session. If the current model is unknown, state that condition rather than guessing. This overlay takes precedence over Continue because Codex does not switch the main model inside an existing session.

When phase-boundary or current-model state is not observable, omit the `Session` field and give a short conditional sentence instead of inventing state.

## Output

Keep the recommendation compact:

```text
Recommended: GPT-6 Luna: Max
Confidence: High
Session: fresh

Why:
* Model: concrete task properties that require this capability
* Effort: concrete inference, search, iteration, and verification demands
* Cost or quota constraint, when relevant and known

Route comparison:
* Luna: explain why Sol is unnecessary when Luna is selected.
* Sol: explain why Luna is insufficient, and why Astra would not reduce expected rework enough when that distinction is useful.
* Astra: explain why Sol is insufficient.

Escalate if:
* concise evidence that would change the route during execution

Next:
`/implement issue 21`
```

Use qualitative confidence to reflect evidence completeness, not model prestige. Explain the model-tier choice and effort choice separately. When recommending Sol or Astra, explain why the nearest weaker route is insufficient. Explain why the nearest stronger route is unnecessary when that distinction is useful. End with the exact next invocation or prompt after removing `/evaluate-model` when it can be derived safely.

Escalation triggers are task-specific signs that the starting assumptions failed, such as newly discovered cross-system ownership, irreconcilable invariants, or loss of local verification. Keep them concise; global runtime policy owns capability-ceiling handling.

## Calibration examples

- **Mechanical local edit:** change one documented display field with an exact expected value and a direct check. This is GPT-6 Luna Medium because capability and inference demands are both limited.
- **Bounded candidate normalization:** correlate a known GRE envelope, preserve specified identity fields, reject stale, incomplete, or ambiguous input, normalize choices, and produce stable IDs and a deterministic hash behind an established adapter boundary. This is GPT-6 Luna High when fixtures and property tests directly prove the specified semantics and the implementation loop is bounded. Multiple invariants do not make it Sol because no architecture, ownership, or domain semantics need discovery. Choose Luna Max if the same settled work requires sustained autonomous iteration; choose Sol if implementation exposes missing or contradictory repository-owned identity semantics, unresolved GRE semantics, a required seam change, or loss of local completeness and correlation checks.
- **Long-horizon settled implementation:** build several specified slices across established boundaries, with local oracles for their interactions and a substantial autonomous search and verification loop. This is GPT-6 Luna Max because additional inference improves first-pass execution while capability demands stay within Luna's route.
- **Short ownership decision:** determine which of two components owns a new invariant when the spec leaves that boundary unresolved. This is GPT-6 Sol High despite the short task because architectural judgment, not more Luna iteration, determines correctness.
- **Lifecycle protocol:** define or implement content identity, activation, lineage, stale asynchronous completion, atomic transitions, retries, supersession, and cache reuse whose interactions determine the abstraction's semantics. This needs GPT-6 Sol capability because local correctness does not settle the protocol as a whole; choose High, xHigh, or Max from the expected reasoning and verification loop.
- **Foundational probabilistic belief protocol:** combine multiple evidence sources and meanings with late calibration and plausible semantic error, where a subtle Sol mistake would invalidate substantial downstream work. This can justify GPT-6 Astra; choose its effort from the depth of the actual reasoning loop.
- Running `/improve-codebase-architecture` after the first bounded domain pipeline: normally GPT-6 Sol High unless repository evidence makes it a major cross-system decision.
- Independently reviewing a complete end-to-end production loop after implementation: potentially GPT-6 Astra in a fresh session when subsystem interaction, late verification, and downstream rework make a Sol mistake unusually costly.

## Stop boundary

Read-only inspection for routing is the full scope. Do not invoke the target skill, begin its workflow, solve the task, edit its artifacts, switch models, create a session, dispatch an agent, call an external model, or persist a routing record. Return the recommendation and stop.
