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

## Responsibility Scan

Run a responsibility scan on each substantial changed function or flow that shows any of these triggers:

- control flow meaningfully combined with parsing or validation
- optionality or casts
- repeated policy conditions
- material function growth

The scan looks for **responsibility mixing**: at least two independently nameable responsibilities with separate reasons to change, such as traversal combined with a policy, transformation, parsing, validation, or result construction. A loop, nested loop, conditional, or long function is never responsibility mixing on its own.

A structural hypothesis from the scan must:

- name the responsibilities involved;
- anchor each one to changed code;
- state the reasoning or locality cost the mixing imposes on a reader or on the next change;
- describe a concrete behavior-preserving simplification that passes the deletion, locality, and deep-module tests. Apply `codebase-design` for those tests rather than redefining them here.

A helper or stage that only renames or relocates existing branches does not qualify. Report one cohesive hypothesis per underlying design problem in a function, and gather every supporting example into its evidence instead of splitting them into separate hypotheses.

## Declarative Simplification

A declarative simplification, such as a stream or collection pipeline, qualifies only when it states intent more clearly, removes incidental control flow, preserves locality, and stays easy to read.

Do not propose one that needs mutable state, lookahead, index manipulation, or opaque collectors, or that hides domain policy. Keep explicit traversal or a dedicated internal helper when it makes the policy clearer than a declarative expression would. Never require a particular syntax: a rewrite that is only shorter is a style preference, not a simplification.

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
- Apply the structural evidence standard from the scout contract. Passing tests or correct behavior do not weaken a structural hypothesis.
- Keep structural concerns separate from correctness concerns about the same code. Do not argue a structural hypothesis from a runtime defect or fold a defect into it.
- If no concrete simplification is visible, report no hypothesis.
- Report an admission-qualified Hypothesis when source evidence establishes a credible concern and state a falsifiable validation condition; the validator assigns the final outcome.
