---
name: design-review
description: Check a spec's proposed modules for shallow seams before ticket breakdown.
disable-model-invocation: true
---

# Design Review

Run after `to-spec` produces a spec, before `to-tickets` breaks it into issues. Catch shallow seams, modules whose interface is nearly as complex as their implementation, in the spec's "Implementation Decisions" section, while changing them is still a paragraph edit instead of a follow-up refactor ticket.

Call the Skill tool with "codebase-design" now for the glossary and shared seam-review checks. That skill owns the definition of good depth, deletion, test-surface, adapter, circular-seam, and bounce design; this skill applies those checks to a spec. Use the glossary terms exactly, never "component," "service," "API," or "boundary."

## Process

### 1. Gather the design

Read the spec's "Implementation Decisions" section, including the modules to be built or modified, their interfaces, and any architectural decisions. Read `CONTEXT.md` and the ADRs under `docs/adr/` for the area the spec touches, so a proposed module is not re-litigating a settled decision without saying so. This step is complete when every proposed module and relevant decision has been listed.

### 2. Read the seam it lands on

For each proposed module, read the existing code at or near where it will sit. A design reviewed only against prose invents problems that do not exist and misses ones that do. The current call sites, existing collaborators, and sibling modules doing something similar are load-bearing context. This step is complete when each proposed module has been checked against its surrounding code.

### 3. Check every proposed module against depth

For each module in the spec, run all five checks. A module that fails any one is a candidate for rework. Note which check it failed and why. This step is complete when every proposed module has a result for all five checks.

Apply all five shared checks from `codebase-design`: deletion, adapter reality, interface-as-test-surface, circular seam, and bounce. For the test-surface check, compare the spec's "Testing Decisions" with the proposed interface. Record the result for every module, and quote the relevant decision when a check fails.

### 4. Verdict

State one of:

- **Approved**: every proposed module passed all five checks. Edit the spec's "Implementation Decisions" section in place to record the validated module contract: what each module owns end to end, its public interface, and which adapters justify any seam. This is the only artifact. Do not create a separate design-review file.
- **Rework**: at least one module failed a check. Present the failing module, the check it failed, why it failed, and one or two concrete alternatives for fixing the seam. Let the user decide the next step: apply a local seam adjustment directly to the spec, call the Skill tool with "grilling" if the fix changes the feature's shape or intent, or run `to-spec` if the spec's solution itself needs to change. Do not rewrite the spec on a guess.

Do not hand off to `to-tickets` until the verdict is Approved and the spec reflects it.
