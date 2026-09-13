## What it does

`design-review` checks a spec's proposed modules before they become tickets. It looks for shallow seams, circular seams, test surfaces that leak past the interface, and flows split across too many public modules.

It runs while the design is still cheap to change. An approved review records the durable verdict and validated module contracts in the spec. The approved spec is a self-contained restart point: a fresh session can continue from it without the original grilling transcript. A rework verdict names the failing check and leaves the design change to you, rather than guessing at a rewrite.

## When to reach for it

You invoke this by typing `/design-review`, and the agent won't reach for it on its own.

Reach for it after [to-spec](https://aihero.dev/skills-to-spec) and before [to-tickets](https://aihero.dev/skills-to-tickets), passing the exact spec issue number, issue URL, or local spec path. For a design question that is not yet captured in a spec, use [grill-with-docs](https://aihero.dev/skills-grill-with-docs) first.

## The five checks

The review uses the deep-module vocabulary from [codebase-design](https://aihero.dev/skills-codebase-design):

- **Deletion test:** deleting the module should make complexity disappear; if complexity reappears across callers, the seam earns its keep.
- **Adapter reality:** one adapter is hypothetical; two adapters make a real seam.
- **Interface-as-test-surface:** externally promised behavior should be verified through the public interface; private internal seams used by the module's own tests are allowed.
- **Circular seam:** a module should not take its owner or caller as a parameter.
- **Bounce check:** one complete action should not require unnecessary traversal across shallow public seams.

An approved spec records the reviewed modules, end-to-end ownership, public interfaces and seams, justified adapters, interface-level testing decisions, relevant constraints or ADRs, and the domain concepts or call sites that locate the affected code. It also adds or updates a durable `Design Review` section containing the verdict and evidence.

For each module, record every check as `Pass`, `Fail`, or `N/A` with evidence. Then record a whole-design fit pass covering the highest suitable existing seam, one clear end-to-end owner, dependency cycles or mutual ownership, and duplicate abstractions for existing domain concepts. Approval requires no `Fail` results; it also removes both `needs-triage` and `ready-for-agent` from the parent spec. `ready-for-agent` is reserved for executable tickets produced by `to-tickets`.

## Common questions

**Does it replace `to-spec`?**

No. `to-spec` captures the decisions and proposed seams. `design-review` checks those proposals against the codebase before ticket breakdown.

**Does it create a separate review document?**

No. An approved review updates the exact spec artifact in place, preserving `Implementation Decisions` and adding or updating its durable `Design Review` section. A rework verdict gives you options without rewriting the spec on a guess.

## It's working if

- Every proposed module has a result for all five checks.
- An approved spec states what each module owns end to end and which adapters justify its seams.
- A rework verdict identifies the failing result, explains why it failed, and gives concrete alternatives.
- `to-tickets` is not started until the spec has an approved verdict.

## Where it fits

`design-review` is a user-invoked chain step between [to-spec](https://aihero.dev/skills-to-spec) and [to-tickets](https://aihero.dev/skills-to-tickets). It applies the canonical seam-review checks supplied by [codebase-design](https://aihero.dev/skills-codebase-design) as a validator; it does not invoke [improve-codebase-architecture](https://aihero.dev/skills-improve-codebase-architecture). [grilling](https://aihero.dev/skills-grilling) is the better choice when fixing a failed seam would change the feature's shape or intent. [ask-matt](https://aihero.dev/skills-ask-matt) routes you through the whole set.
