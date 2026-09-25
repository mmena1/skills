---
name: evaluate-model
description: Recommend task capability, reasoning depth, and session boundary for one upcoming task, then stop.
disable-model-invocation: true
triggers:
  - user
---

# Evaluate Model

Recommend the task capability, reasoning depth, and session boundary needed for one specific upcoming task. This is a pre-task advisor: inspect only far enough to classify the work, give the recommendation, and stop. The user decides how to map these requirements to a model or harness and whether to start a new session.

## Evaluate the task

1. Identify the exact task and preserve the next invocation or prompt.
2. When the request names another skill, locate and read that skill's current `SKILL.md` before classifying it. Its actual workflow supplies the baseline task class; a remembered summary does not. If the file cannot be inspected, state that limitation and lower confidence rather than inventing its behavior.
3. Read referenced issues, specs, repository instructions, context, or code only when a concrete unknown could change the recommendation. Gather task-classification evidence, not a solution. Stop inspecting once more detail is unlikely to change the recommendation.
4. Assess the task using these dimensions:
   - **Semantic novelty:** whether the task must define how its invariants compose or apply a defined composition.
   - **Boundary novelty:** whether it creates or changes responsibility boundaries or stays inside an established one.
   - **Verification locality:** whether checks directly prove the important behavior or correctness only emerges across the system.
   - **Determinism:** whether a strong, repeatable correctness check exists.
   - **Rework radius:** whether a wrong result stays localized or invalidates downstream work.
   - **Plausible-wrong risk:** whether an incorrect result can pass local checks and remain convincing.

Interpret interacting requirements through these dimensions. Their number is not an independent capability signal. Do not use task size, duration, file count, line count, prompt length, or invariant count as direct capability signals.

## Choose task capability

Choose the tier that supplies the judgment the task needs. These tiers describe task properties, not model families or harness controls.

- **Execution:** The semantics are settled, responsibility boundaries are established, and correct work mainly applies the defined behavior. Verification is direct and rework is bounded. More judgment would not materially reduce uncertainty.
- **Judgment:** The task must settle important semantics, ownership, or lifecycle behavior, or coordinate interactions where local correctness alone cannot establish system correctness. A locally plausible answer could violate a deeper requirement.
- **Frontier:** Reserve this for exceptional work where consequential uncertainty remains, multiple difficult systems interact, verification is weak or late, and a mistake could cause substantial rework. Complexity or duration alone does not qualify.

Choose **Frontier** only when the combined risk warrants it. Do not promote a task because it has many criteria or touches many files.

## Choose reasoning depth

Choose one depth separately from capability. Depth describes how much sustained reasoning, search, and verification the task needs. It does not change the capability tier or map to a harness setting.

- **Medium:** Normal depth when semantics are clear and the work can be completed with a bounded reasoning and verification loop.
- **High:** Use when correctness requires sustained analysis across dependent questions, evidence, or interacting constraints.
- **Max:** Use when the task needs an extended autonomous loop of reasoning, search, and verification, or when a failed first pass would cause materially costly rework.

Many steps or a long task do not automatically require **Max**. **Execution / Max** is appropriate when the semantics are settled but the execution loop itself is unusually sustained. Apply the same depth criteria at every capability tier.

## Choose the session boundary

After selecting capability and depth, apply the ordered policy in [`PHASE-BOUNDARIES.md`](PHASE-BOUNDARIES.md). Report `Session: current` when that policy selects Continue or a subagent that leaves this session intact. Report `Session: fresh` when it selects a boundary that starts work in a new session, such as `/clear`, `/handoff-doc`, or `/compact`; name the boundary in the reasons.

If a required context fact for applying the policy cannot be observed, do not guess. Omit the `Session` field and state the condition that prevents the recommendation. Do not add a model, vendor, or harness overlay.

## Output

Keep the recommendation compact:

```text
Capability: Execution
Reasoning depth: Medium
Confidence: High
Session: current

Why:
* Capability: task properties that require this tier
* Depth: why normal or extended reasoning is appropriate
* Session: how the phase-boundary policy applies

Tier comparison:
* For Execution, explain why Judgment is unnecessary. For Judgment, explain why Execution is insufficient and, when useful, why Frontier is unnecessary. For Frontier, explain why Judgment is insufficient.

Escalate if:
* Evidence that would change the capability or depth during the work

Next:
`/implement issue 21`
```

Qualitative confidence reflects evidence completeness, not tier. Explain capability and depth separately. When recommending **Judgment** or **Frontier**, explain why the nearest weaker tier is insufficient. When useful, explain why the nearest stronger tier would not reduce expected rework enough to justify it. End with the exact next invocation or prompt after removing `/evaluate-model` when it can be derived safely.

Escalation triggers are task-specific signs that the starting assumptions failed, such as newly discovered cross-system ownership, irreconcilable invariants, or loss of local verification. Keep them concise; global runtime policy owns capability-ceiling handling.

## Calibration examples

- **Mechanical local edit:** Change one documented display field with an exact expected value and a direct check. This is **Execution / Medium** because semantics are settled and verification is local.
- **Bounded specified implementation:** Normalize a known input, preserve specified identity fields, reject stale or ambiguous input, and produce a stable result inside an established boundary. This is **Execution / Medium** when the specification and fixtures settle the semantics. Several interacting requirements do not promote the capability tier by themselves.
- **Long-horizon settled implementation:** Complete several specified slices across established boundaries with local checks for their interactions. This can be **Execution / Max** when the autonomous search and verification loop is sustained. Duration raises depth only when the loop warrants it; it does not create a need for more judgment.
- **Short ownership decision:** Decide which of two components owns an invariant when the specification leaves that boundary unresolved. This is **Judgment / High** despite the short task because architectural judgment determines correctness.
- **Lifecycle protocol:** Define or implement identity, activation, stale completion, retries, supersession, and reuse when their interactions determine the protocol's semantics. This is **Judgment / High** for a bounded design or implementation. Use **Max** if the work requires a sustained reasoning and verification loop or a failed first pass would cause costly rework.
- **Foundational cross-system probabilistic work:** Combine evidence across difficult systems when consequential uncertainty remains, calibration is late, and a plausible semantic error could invalidate substantial downstream work. This may warrant **Frontier / Max**.
- **Architecture review:** Review responsibility boundaries, dependency direction, and whether a proposed seam owns its behavior. This is normally **Judgment / High**; raise the tier only when the exceptional Frontier conditions hold.
- **End-to-end review:** Reviewing a complete production loop can be **Judgment / High** when its invariants and checks are clear. Use **Frontier / Max** only when difficult subsystem interactions, weak late verification, consequential uncertainty, and substantial rework risk occur together.

## Stop boundary

Read-only inspection for routing is the full scope. Do not invoke the target skill, begin its workflow, solve the task, edit its artifacts, select a concrete model or harness, create a session, dispatch an agent, call an external model, or persist a routing record. Return the recommendation and stop.
