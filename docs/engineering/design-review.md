## What it does

`design-review` checks a spec's proposed modules before they become tickets. It looks for shallow seams, circular seams, test surfaces that leak past the interface, and flows split across too many public modules.

It runs while the design is still cheap to change. An approved review records the validated module contracts in the spec. A rework verdict names the failing check and leaves the design change to you, rather than guessing at a rewrite.

## When to reach for it

You invoke this by typing `/design-review`, and the agent won't reach for it on its own.

Reach for it after [to-spec](https://aihero.dev/skills-to-spec) and before [to-tickets](https://aihero.dev/skills-to-tickets), when a spec has an `Implementation Decisions` section that proposes modules. For a design question that is not yet captured in a spec, use [grill-with-docs](https://aihero.dev/skills-grill-with-docs) first.

## The five checks

The review uses the deep-module vocabulary from [codebase-design](https://aihero.dev/skills-codebase-design):

- **Deletion test:** inlining should concentrate complexity, not merely move it.
- **One adapter is hypothetical, two is real:** a seam needs actual variation.
- **Interface is the test surface:** tests should verify behavior through the public interface.
- **Circular seam:** a module should not take its owner or caller as a parameter.
- **Bounce check:** one complete action should not require jumping across a chain of public modules.

## Common questions

**Does it replace `to-spec`?**

No. `to-spec` captures the decisions and proposed seams. `design-review` checks those proposals against the codebase before ticket breakdown.

**Does it create a separate review document?**

No. An approved review edits the spec's `Implementation Decisions` section in place. A rework verdict gives you options without rewriting the spec on a guess.

## It's working if

- Every proposed module has a result for all five checks.
- An approved spec states what each module owns end to end and which adapters justify its seams.
- A rework verdict identifies the failing module, the failed check, and concrete alternatives.
- `to-tickets` is not started until the spec has an approved verdict.

## Where it fits

`design-review` is a user-invoked chain step between [to-spec](https://aihero.dev/skills-to-spec) and [to-tickets](https://aihero.dev/skills-to-tickets). It sits on the design vocabulary supplied by [codebase-design](https://aihero.dev/skills-codebase-design), while [grilling](https://aihero.dev/skills-grilling) is the better choice when fixing a failed seam would change the feature's shape or intent. [ask-matt](https://aihero.dev/skills-ask-matt) routes you through the whole set.
