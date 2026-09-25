# Model-invoked vs user-invoked

Every `SKILL.md` in this repo is a skill. The one axis that splits them is **invocation**, who can reach it:

- **User-invoked**: reachable **only by the human typing its name**. Set `disable-model-invocation: true` and Devin `triggers: [user]` in the `SKILL.md` frontmatter, and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. The `description` is **human-facing**: a one-line summary read by a person browsing slash-commands. Strip trigger lists such as "Use when the user says...".
- **Model-invoked**: reachable by **model or user**. The default: omit `disable-model-invocation`, Devin `triggers`, and Claude `user-invocable` from the `SKILL.md` frontmatter, and the `policy` block from `agents/openai.yaml`. The `description` is **model-facing** and keeps rich trigger phrasing ("Use when the user wants…, mentions…, asks for…") so auto-invocation fires. The test for whether a skill should stay model-invoked: _could the model usefully reach for this autonomously?_ (Reuse is the reason to extract a skill, not the test.)

Each harness excludes a user-invoked skill from the model's reach in its own way, so nothing but the human can fire it: no other skill can. A user-invoked skill may invoke model-invoked skills, but it can never reach another user-invoked skill.

Every skill also carries an `agents/openai.yaml` beside its `SKILL.md`. It holds Codex UI metadata: `interface.display_name` and `interface.short_description` for the skill picker, and, for user-invoked skills, the `policy.allow_implicit_invocation: false` that pairs with `disable-model-invocation`. Keep the two in sync: a skill is user-invoked in both harnesses or neither.

The top-level `README.md` groups catalog entries into **User-invoked** and **Model-invoked**.

## Dependencies between them

Dependencies are expressed as an explicit instruction to **apply the named skill** (`Apply the "grilling" skill now`), not deep `../other-skill/FILE.md` cross-references, and not a bare `/skill`-style mention left for the model to interpret. Use the current harness's native skill invocation or loading mechanism when it provides one. If the harness exposes the skill catalog or files but no explicit invocation primitive, load and follow the named skill's `SKILL.md`. Never claim that a tool call occurred when the harness does not expose one. Shared reference docs live inside the skill that owns them; other skills reach that material by applying the named model-invoked skill, not by linking across folders.

This is about **operative** instructions: a skill's own steps telling the agent to go run another skill right now. Catalog prose that names skills for a human to pick from is not invoking anything, so it may keep `/skill`-style names as plain labels.

Apply one skill at a time. A step that needs two skills must apply each one separately: say so (`Apply the "grilling" skill, then apply "domain-modeling"`), not "apply X and Y" as if they were one combined skill.

This whole convention only holds when the named skill is **model-invoked**. A user-invoked skill can never be reached as a dependency. When a step's precondition is a user-invoked skill such as `setup-skills`, phrase it as an instruction for the human to act on: "tell the user to run `/setup-skills`".

## Passive vs active domain work

Merely _reading_ `CONTEXT.md` for vocabulary is a one-line prose pointer, not the `domain-modeling` skill. Only the active build/sharpen discipline (challenge terms, edge-case scenarios, write ADRs, update `CONTEXT.md` inline) is `domain-modeling`.
