---
name: design-review
description: Check a spec's proposed modules for shallow seams before ticket breakdown.
disable-model-invocation: true
---

# Design Review

Run after `to-spec` produces a spec, before `to-tickets` breaks it into issues. Catch shallow seams, modules whose interface is nearly as complex as their implementation, in the spec's "Implementation Decisions" section, while changing them is still a paragraph edit instead of a follow-up refactor ticket.

Call the Skill tool with "codebase-design" now for the glossary (module, interface, seam, depth, adapter) and its four principles (deletion test, interface-is-the-test-surface, one-adapter-is-hypothetical, depth-is-a-property-of-the-interface). Every check below applies one of those principles. Use the glossary terms exactly, never "component," "service," "API," or "boundary."

## Process

### 1. Gather the design

Read the spec's "Implementation Decisions" section, including the modules to be built or modified, their interfaces, and any architectural decisions. Read `CONTEXT.md` and the ADRs under `docs/adr/` for the area the spec touches, so a proposed module is not re-litigating a settled decision without saying so. This step is complete when every proposed module and relevant decision has been listed.

### 2. Read the seam it lands on

For each proposed module, read the existing code at or near where it will sit. A design reviewed only against prose invents problems that do not exist and misses ones that do. The current call sites, existing collaborators, and sibling modules doing something similar are load-bearing context. This step is complete when each proposed module has been checked against its surrounding code.

### 3. Check every proposed module against depth

For each module in the spec, run all five checks. A module that fails any one is a candidate for rework. Note which check it failed and why. This step is complete when every proposed module has a result for all five checks.

- **Deletion test.** Imagine inlining the module's logic at its call site. If complexity would concentrate into one place, it earns its seam. If it would just relocate, such as a switch statement moved one file over or a pass-through method, cut it and fold the logic into the caller or the module it delegates to.
- **One adapter is hypothetical, two is real.** If the spec proposes an interface, such as a `Strategy`, `Policy`, or pluggable abstraction, with exactly one implementation in scope and no second implementation on the visible roadmap, the seam is not earning its keep yet. Collapse it to a straight-line method and revisit it if a second implementation actually shows up.
- **Interface is the test surface.** Check the spec's "Testing Decisions" against the proposed interface. If a test needs to reach past the module's public interface to verify behavior, the interface is drawn in the wrong place.
- **Circular seam.** If a proposed module's interface takes the module that owns it, or calls back into its own caller, as a parameter, the two are really one module wearing two names. Fold them together. This is the deletion test's sharpest failure mode: the abstraction cannot be deleted without also rewriting the thing it calls back into.
- **Bounce check.** If understanding the feature's flow requires a reader to jump across more than two or three public modules to follow one complete action, the spec is prescribing the same friction an architecture review would surface post-implementation. Let one module own the end-to-end sequence and keep helpers internal to it. Do not split the sequence into separately testable modules just to make tests easier.

### 4. Verdict

State one of:

- **Approved**: every proposed module passed all five checks. Edit the spec's "Implementation Decisions" section in place to record the validated module contract: what each module owns end to end, its public interface, and which adapters justify any seam. This is the only artifact. Do not create a separate design-review file.
- **Rework**: at least one module failed a check. Present the failing module, the check it failed, why it failed, and one or two concrete alternatives for fixing the seam. Let the user decide the next step: apply a local seam adjustment directly to the spec, call the Skill tool with "grilling" if the fix changes the feature's shape or intent, or run `to-spec` if the spec's solution itself needs to change. Do not rewrite the spec on a guess.

Do not hand off to `to-tickets` until the verdict is Approved and the spec reflects it.
