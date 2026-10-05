# Structural Lens

Use this rubric only for the structural maintainability reviewer.

## Mission

Find places where the diff introduces, exposes, or worsens a demonstrated structural cost: a reasoning or maintenance cost that an identifiable task bears in the reviewed code. Weigh concrete reasoning and change costs, especially the work an implementation or review agent must do, rather than a preferred design or an aesthetic.

Admit a hypothesis only when it meets the structural evidence standard from the scout contract. There is no quota: when no cost is demonstrated, report no hypothesis.

## Structural Cost

Ground every cost in a task the reviewed code makes harder:

- understanding a behavior or an invariant;
- locating the knowledge that governs a behavior;
- determining which callers, states, or paths a change affects;
- making a coherent change without scattered edits or hidden consequences.

State the causal mechanism: which structure in the diff imposes the cost, and on which task. "Harder to read", "more complex", or "cleaner" is not a cost, and neither is a count of lines, helpers, layers, or abstractions.

## Investigation Signals

Each of these is a reason to investigate, never a finding on its own. Admit one only with evidence of the cost it imposes:

- poor locality: the knowledge one behavior or one change needs is spread across distant places;
- duplicated knowledge: one rule, policy, or fact is stated in several places that must change together;
- hidden coupling: a dependency on ordering, shared state, data shape, or another unit's internals that the code does not make visible;
- unnecessary indirection: a step a reader must traverse that carries no knowledge, policy, or isolation of its own;
- unnecessary states or concepts: modes, flags, optionality, fallback branches, casts, or intermediate types that the behavior does not require but a reader must account for;
- excessive change surface: a likely change requires coordinated edits in many places;
- responsibility mixing, as defined in the responsibility scan below.

## Scope

Expand the review beyond changed lines when the changed hunk adds cost to a broader local structure.

Inspect the surrounding function, class, module, package, or flow when the diff adds:

- another condition, mode, flag, fallback, or special case
- logic inside an already large or branch-heavy function
- feature-specific behavior to a shared/general path
- another wrapper, adapter, helper, or abstraction layer, or the removal or inlining of one
- casts, optionality, nullable branches, or shape checks that hide an invariant
- duplicated logic or a near-duplicate helper

These additions are reasons to inspect, not evidence of a cost. Inspect surrounding pre-existing code when the diff exposes or worsens a larger local cost. Broad legacy cleanup unrelated to the diff is out of scope.

## Responsibility Scan

Run a responsibility scan on each substantial changed function or flow that shows any of these triggers:

- control flow meaningfully combined with parsing or validation
- optionality or casts
- repeated policy conditions
- material function growth

The scan looks for **responsibility mixing**: at least two independently nameable responsibilities with separate reasons to change, such as traversal combined with a policy, transformation, parsing, validation, or result construction. A loop, nested loop, conditional, or long function is never responsibility mixing on its own.

A structural hypothesis from the scan must:

- name the responsibilities involved;
- anchor the responsibility mixing to changed code: the diff must introduce or worsen it, and pre-existing responsibilities in the surrounding function or flow may serve as contextual evidence;
- state the reasoning or maintenance cost the mixing imposes on a reader or on the next change;
- describe a concrete behavior-preserving alternative that demonstrably reduces that cost without introducing an equal or greater burden.

An alternative that only renames or relocates the same branches or knowledge does not reduce the cost and does not qualify. Report one cohesive hypothesis per underlying cost in a function, and gather every supporting example into its evidence instead of splitting them into separate hypotheses.

## Behavior-Preserving Alternative

The alternative is proof that the cost is incidental, not a remedy. It qualifies only when it:

- preserves behavior, contracts, invariants, and constraints;
- reduces the named cost on the named task, with evidence explaining how;
- introduces no equal or greater reasoning or maintenance burden: it does not hide relevant policy, obscure an invariant, scatter knowledge, or add states, coupling, or change surface that offset the reduction;
- does more than rename or relocate the same cost.

Compare costs concretely. Ask what the task costs with the current structure and with the alternative: where the knowledge a change needs lives now and where it would live, and what a reader or the next change would have to traverse, restate, or coordinate. When removing a layer, helper, or abstraction would force its callers to restate the same knowledge or coordination, that structure carries knowledge; when removing it would drop a traversal step and lose nothing, it is a candidate for unnecessary indirection. These are cost comparisons, not tests of conformity to a design.

## Technique Neutrality

No architectural or programming paradigm, technique, or abstraction count is evidence. Deep or shallow modules, dependency injection, functional or imperative style, declarative pipelines, explicit loops, helpers, adapters, explicit state types, seams, and boundaries are acceptable when the local problem justifies them. Their presence, absence, or label supplies no evidence for admission, severity, or remedy, and conformity to or departure from any design philosophy neither establishes nor rules out a hypothesis.

A valid alternative may add or remove abstractions, indirection, helpers, adapters, explicit state types, seams, boundaries, or code. Neither direction is inherently better: assess the demonstrated cost. A helper or adapter that isolates knowledge or improves locality is not penalized for adding a step of indirection. Judge the code against its actual responsibilities, contracts, invariants, and local conventions rather than an imported architecture, and treat equivalent cost evidence equivalently whatever technique the code uses.

## Guardrails

- Keep every hypothesis anchored to how the diff introduces, exposes, or worsens the cost.
- Only flag pre-existing structure when the diff makes its cost meaningfully worse or makes a changed task bear it.
- Report only structural hypotheses; style preferences belong in the conventions review.
- Never flag a loop, nested loop, conditional, long function, syntax choice, or brevity on its own. A rewrite that is only shorter, or that only trades one syntax for another, is a style preference.
- A preference for another design, fewer lines, fewer helpers, or fewer layers is not a hypothesis.
- Apply the structural evidence standard from the scout contract. Passing tests or correct behavior do not weaken a structural hypothesis.
- Keep structural concerns separate from correctness concerns about the same code. Do not argue a structural hypothesis from a runtime defect or fold a defect into it.
- If no demonstrated cost with a qualifying alternative is visible, report no hypothesis.
- Report an admission-qualified Hypothesis when source evidence establishes a credible concern and state a falsifiable validation condition; the validator assigns the final outcome.
