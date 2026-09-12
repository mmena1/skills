---
name: design-review
description: Check a spec's proposed modules for shallow seams before ticket breakdown.
disable-model-invocation: true
---

# Design Review

Run after `to-spec` produces a spec, before `to-tickets` breaks it into issues. Invoke it with an exact spec reference: an issue number, issue URL, or local spec path. Catch shallow seams, modules whose interface is nearly as complex as their implementation, in the spec's "Implementation Decisions" section, while changing them is still a paragraph edit instead of a follow-up refactor ticket.

Call the Skill tool with "codebase-design" now for the glossary and shared seam-review checks. That skill owns the definition of good depth, deletion, test-surface, adapter, circular-seam, and bounce design; this skill applies those checks to a spec. Use the glossary terms exactly, never "component," "service," "API," or "boundary."

## Process

### 1. Resolve and gather the design

Resolve the supplied issue number, issue URL, or local spec path and update that exact artifact; do not select a spec from conversation memory. Read its "Implementation Decisions" section, including the modules to be built or modified, their interfaces, and any architectural decisions. Read `CONTEXT.md` and the ADRs under `docs/adr/` for the area the spec touches, so a proposed module is not re-litigating a settled decision without saying so. This step is complete when the exact artifact, every proposed module, and every relevant decision have been listed. If no exact reference was supplied, ask for one and stop.

### 2. Read the seam it lands on

For each proposed module, read the existing code at or near where it will sit. A design reviewed only against prose invents problems that do not exist and misses ones that do. The current call sites, existing collaborators, and sibling modules doing something similar are load-bearing context. This step is complete when each proposed module has been checked against its surrounding code.

### 3. Check every proposed module against depth

For each module in the spec, run all five checks. Record a result for each check as `Pass`, `Fail`, or `N/A`, with evidence from the spec or codebase. A module that has any `Fail` result is a candidate for rework. This step is complete when every proposed module has a result and evidence for every check.

Apply all five shared checks from `codebase-design`: deletion, adapter reality, interface-as-test-surface, circular seam, and bounce. For the test-surface check, evaluate externally promised behavior through the public interface; private internal seams used by the module's own tests are allowed. Quote the relevant decision or code evidence for every result.

### 4. Check whole-design fit

After the per-module checks, run the shared whole-design fit checks from `codebase-design`: highest suitable seam, end-to-end ownership, dependency direction, and concept singularity. Record each result as `Pass`, `Fail`, or `N/A`, with evidence.

### 5. Verdict

State one of:

- **Approved**: every per-module and whole-design result is `Pass` or justified `N/A`, with no `Fail` results. Edit the exact spec artifact in place so it becomes a self-contained restart point. Preserve the existing decisions and add a durable `Design Review` section containing: `Verdict: Approved`; the reviewed modules and what each owns end to end; each public interface and seam; the adapters that justify each seam; the per-module and whole-design results with evidence; the testing decisions and interface-level test surfaces; relevant architectural constraints or ADRs; and the domain concepts, call sites, or codebase area needed to locate the implementation without the original conversation. On approval, remove the temporary `needs-triage` label from the parent spec. Do not apply `ready-for-agent` to it. This is the only artifact. Do not create a separate design-review file.
- **Rework**: at least one per-module or whole-design result is `Fail`. Present the failing result, why it failed, and one or two concrete alternatives for fixing the design. Let the user decide the next step: apply a local seam adjustment directly to the spec, call the Skill tool with "grilling" if the fix changes the feature's shape or intent, or run `to-spec` if the spec's solution itself needs to change. Do not rewrite the spec on a guess.

Do not hand off to `to-tickets` until the verdict is Approved and the spec reflects it. The Approved spec must be sufficient for a fresh session or another harness to continue without the original grilling transcript.
