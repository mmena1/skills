# Skill mechanics

The skill-specific branch of [`writing-for-agents`](SKILL.md): what changes when the document is a skill (frontmatter, the invocation choice, and router skills). Everything else about writing it is the universal reference in `SKILL.md`.

## Invocation

Two choices, trading the two loads:

- A **model-invoked** skill keeps a `description`, so the agent can fire it autonomously, and other skills can reach it. Direct user invocation remains available by default. For a reference-only skill with no useful direct command, Claude may set `user-invocable: false` while keeping model invocation enabled; Codex and Devin still allow direct invocation. The description is the skill's top-level context pointer, forced to stay loaded at all times: permanent context load in exchange for discoverability. A model-invoked skill whose content is all reference is also one home for shared reference: another skill can invoke it, so reference needed by several skills lives in one place. Mechanics: omit `disable-model-invocation`, declare both Devin triggers, and write a model-facing description carrying the trigger branches (the pointer-writing rules in `SKILL.md` apply in full).
- A **user-invoked** skill strips the description from automatic discovery: a model cannot select it autonomously. The user can invoke it directly, and an already user-authorized workflow may explicitly compose it as a named dependency when that composition is part of its documented contract. This explicit dependency does not change the skill's user-only policy. Zero context load, but it spends cognitive load: the user is the index that must remember it exists. Mechanics: set `disable-model-invocation: true`; the `description` becomes human-facing: a one-line summary, trigger lists stripped.

Pick model-invocation when an agent must discover the skill autonomously, including as an eligible automatic dependency. An already authorized workflow can explicitly compose a user-invoked dependency when its documented contract requires it, without changing that dependency's invocation policy. If a skill only fires by hand or through documented composition, make it user-invoked and pay no context load.

Shared reference that multiple user-invoked skills need may live in a plain file outside the skill system, so each can point to it without adding a documented dependency between skills.

## Splitting by invocation

The invocation cut of splitting (the sequence cut lives in `SKILL.md`): split off a model-invoked skill when you have a distinct leading word that should trigger it on its own (a trigger word you actually use in your prompts), or another skill must reach it. You pay context load for the new always-loaded description, so that independent reach has to be worth it.

## Router skills

When user-invoked skills multiply past what you can remember, that piled-up cognitive load is cured by a **router skill**: one user-invoked skill that names the others and when to reach for each, so the human has one skill to remember instead of many. A router only hints at user-only skills; it does not invoke them. The explicit dependency exception above applies only when the already authorized workflow documents that dependency as a required step.
