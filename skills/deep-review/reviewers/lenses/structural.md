# Structural Lens

Use this rubric only for the structural maintainability reviewer.

## Mission

Find cases where the diff makes the implementation harder to reason about and identify the concrete complexity it adds: concepts, branches, modes, wrappers, layers, coupling, or incidental state.

Be ambitious about structural simplification: look for changes that reduce concepts, branches, modes, wrappers, layers, or incidental complexity rather than only smoothing the changed lines, while keeping every finding anchored to how the diff introduces, exposes, or worsens concrete maintainability cost.

## Code Judo

A code-judo opportunity is evidence that a behavior-preserving restructuring could make complexity disappear instead of relocating it. Admit it only when the changed structure exposes a concrete simplification; leave the remedy to review closeout.

Good structural hypotheses explain why the current diff makes the surrounding structure harder to reason about and state the invariant that would disprove that concern.

## Scope

Expand the review beyond changed lines when the changed hunk adds complexity to a broader local structure.

Inspect the surrounding function, class, module, package, or flow when the diff adds:

- another condition, mode, flag, fallback, or special case
- logic inside an already large or branch-heavy function
- feature-specific behavior to a shared/general path
- another wrapper, adapter, helper, or abstraction layer
- casts, optionality, nullable branches, or shape checks that hide an invariant
- duplicated logic or a near-duplicate helper

Inspect surrounding pre-existing code when the diff exposes or worsens a larger local design problem. Broad legacy cleanup unrelated to the diff is out of scope.

## What to Flag Aggressively

Flag structural maintainability issues when there is concrete diff evidence of:

- ad-hoc conditionals bolted onto already busy flows
- repeated conditions that suggest a missing model, policy, dispatcher, or helper
- feature logic leaking into shared or general-purpose code
- wrong-layer logic that belongs in a different service, package, module, or boundary
- thin wrappers, identity helpers, pass-through abstractions, or indirection that does not buy clarity
- magical or overly generic handling that hides simple data-shape assumptions
- unnecessary casts, optionality, nullable modes, or fallback branches that obscure the real invariant
- duplicated concepts or bespoke helpers where a canonical utility or existing abstraction should own the behavior
- file, function, or component growth past a healthy size boundary
- refactors that move complexity around without reducing the number of concepts a reader must hold
- orchestration that serializes independent work or leaves related updates less atomic when a cleaner structure is visible

## Guardrails

- Keep every hypothesis anchored to how the diff introduces, exposes, or worsens the issue.
- Only flag pre-existing complexity when the diff makes it meaningfully worse or reveals a clear local simplification.
- Report only structural hypotheses; style preferences belong in the conventions review.
- If no concrete simplification is visible, report no hypothesis.
- Report an admission-qualified Hypothesis when source evidence establishes a credible concern and state a falsifiable validation condition; the validator assigns the final outcome.
